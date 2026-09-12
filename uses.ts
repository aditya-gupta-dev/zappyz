import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { jwt, sign } from 'hono/jwt';
import { db } from './src/database';
import { users, categories, paymentModes, transactions, merchants } from './src/database/schemas';
import { eq, and, isNull, sql } from 'drizzle-orm';
import { alias } from 'drizzle-orm/sqlite-core';
import { tryCatch } from '@rothsva/utils';
import { requireEnvironmentVariables } from './src/env';

const app = new Hono();
const envVars = requireEnvironmentVariables();

type JwtPayload = { id: number; exp: number };
const port = Number(process.env.PORT ?? 3000);

if (!Number.isInteger(port) || port <= 0) {
  throw new Error('Invalid PORT environment variable');
}

app.use('*', cors({ 
  origin: envVars.frontend_url,
  allowHeaders: ['*'],
  allowMethods: ['GET', 'HEAD', 'PUT', 'POST', 'PATCH', 'DELETE', 'OPTIONS'],
  exposeHeaders: ['*'],
  credentials: true,
  maxAge: 86400,
}));

const JWT_SECRET = envVars.jwt_secret;

// Error helper for consistent responses
const errorResponse = (c: any, message: string, status: number = 400) => {
  return c.json({ data: null, err: message }, status);
};

// Registration
app.post('/auth/register', async (c) => {
  const bodyResult = await tryCatch(c.req.json());
  if (bodyResult.err) return errorResponse(c, 'Invalid JSON body', 400);
  
  const { name, email, password } = bodyResult.data;
  
  if (!name || !email || !password) {
    return errorResponse(c, 'Missing required fields: name, email, and password', 400);
  }

  const hashedPassword = await Bun.password.hash(password);

  // 1. Create User
  const userResult = await tryCatch(
    db.insert(users).values({
      name,
      email,
      passwordHash: hashedPassword,
    }).returning()
  );

  if (userResult.err) {
    console.error(userResult.err);
    return errorResponse(c, 'User with this email already exists', 409);
  }

  const newUser = userResult.data[0];
  if (!newUser) {
    return errorResponse(c, 'Database failed to return new user', 500);
  }

  // 2. Setup defaults (Global categories and payment modes)
  const setupResult = await tryCatch((async () => {
    return await db.transaction(async (tx) => {
      // Payment Modes
      const modes = ['UPI', 'Bank', 'Cash', 'Crypto', 'Other'];
      for (const mode of modes) {
        await tx.insert(paymentModes).values({ name: mode }).onConflictDoNothing();
      }

      // Main Categories (Global)
      const mainCats = ['Food', 'Travel', 'Fees', 'Misc', 'Rent'];

      for (const catName of mainCats) {
        let [existingCat] = await tx.select().from(categories).where(eq(categories.name, catName)).limit(1);
        
        if (!existingCat) {
          [existingCat] = await tx.insert(categories).values({ name: catName }).returning();
        }

        if (catName === 'Food' && existingCat) {
          const subCats = ['Breakfast', 'Lunch', 'Snacks', 'Dinner'];
          for (const sub of subCats) {
            const [existingSub] = await tx.select()
              .from(categories)
              .where(and(eq(categories.name, sub), eq(categories.parentId, existingCat.id)))
              .limit(1);
            
            if (!existingSub) {
              await tx.insert(categories).values({
                name: sub,
                parentId: existingCat.id
              });
            }
          }
        }
      }
      return true;
    });
  })());

  if (setupResult.err) {
    console.error('Setup error:', setupResult.err);
    return errorResponse(c, 'User created but default categories setup failed', 500);
  }

  return c.json({ 
    data: { 
        user: { id: newUser.id, name: newUser.name, email: newUser.email },
        message: 'Sign up completed'
    }, 
    err: null 
  });
});

// Login
app.post('/auth/login', async (c) => {
  const bodyResult = await tryCatch(c.req.json());
  if (bodyResult.err) return errorResponse(c, 'Invalid JSON body', 400);

  const { email, password } = bodyResult.data;

  if (!email || !password) {
    return errorResponse(c, 'Email and password are required', 400);
  }

  const userResult = await tryCatch(
    db.select().from(users).where(eq(users.email, email)).limit(1)
  );

  if (userResult.err || !userResult.data?.[0]) {
    return errorResponse(c, 'Invalid email or password', 401);
  }

  const user = userResult.data[0];
  const isPasswordValid = await Bun.password.verify(password, user.passwordHash);

  if (!isPasswordValid) {
    return errorResponse(c, 'Invalid email or password', 401);
  }

  const payload = {
    id: user.id,
    exp: Math.floor(Date.now() / 1000) + 60 * 60 * 24 * 30, // 1 month
  };
  
  const tokenResult = await tryCatch(sign(payload, JWT_SECRET, 'HS256'));

  if (tokenResult.err) {
    return errorResponse(c, 'Token generation failed', 500);
  }

  return c.json({
    data: {
        token: tokenResult.data,
        user: { id: user.id, name: user.name, email: user.email }
    },
    err: null
  });
});

// Auth Middleware Protected Routes
const auth = jwt({ secret: JWT_SECRET, alg: 'HS256' });

app.get('/me', auth, async (c) => {
  const payload = c.get('jwtPayload') as JwtPayload;
  
  const userResult = await tryCatch(
    db.select().from(users).where(eq(users.id, payload.id)).limit(1)
  );
  
  if (userResult.err || !userResult.data?.[0]) {
    return errorResponse(c, 'User session invalid or user not found', 404);
  }

  const user = userResult.data[0];
  return c.json({ 
    data: { user: { id: user.id, name: user.name, email: user.email } },
    err: null 
  });
});

// Categories
app.get('/categories/main', auth, async (c) => {
  const result = await tryCatch(
    db.select().from(categories).where(isNull(categories.parentId))
  );

  if (result.err) return errorResponse(c, 'Failed to fetch main categories', 500);
  
  return c.json({ data: result.data, err: null });
});

app.get('/categories/:parentId/sub', auth, async (c) => {
  const parentId = parseInt(c.req.param('parentId'));
  
  if (isNaN(parentId)) return errorResponse(c, 'Invalid parent category ID', 400);

  const result = await tryCatch(
    db.select().from(categories).where(eq(categories.parentId, parentId))
  );

  if (result.err) return errorResponse(c, 'Failed to fetch sub-categories', 500);
  
  return c.json({ data: result.data, err: null });
});

app.post('/categories', auth, async (c) => {
  const bodyResult = await tryCatch(c.req.json());
  if (bodyResult.err) {
    console.error('Invalid JSON in category creation:', bodyResult.err);
    return errorResponse(c, 'Invalid JSON body', 400);
  }

  const { name, parentId } = bodyResult.data;
  const normalizedName = typeof name === 'string' ? name.trim() : '';
  const normalizedParentId =
    parentId === null || parentId === undefined || parentId === ''
      ? null
      : Number(parentId);

  if (!normalizedName) {
    return errorResponse(c, 'Category name is required', 400);
  }

  if (
    normalizedParentId !== null &&
    (!Number.isInteger(normalizedParentId) || normalizedParentId <= 0)
  ) {
    return errorResponse(c, 'Valid parent category ID is required', 400);
  }

  if (normalizedParentId !== null) {
    const parentCategoryResult = await tryCatch(
      db.select().from(categories).where(eq(categories.id, normalizedParentId)).limit(1)
    );

    if (parentCategoryResult.err) {
      console.error('Database error validating parent category:', parentCategoryResult.err);
      return errorResponse(c, 'Failed to validate parent category', 500);
    }

    if (!parentCategoryResult.data?.[0]) {
      return errorResponse(c, 'Parent category not found', 404);
    }
  }

  const result = await tryCatch(
    db.insert(categories).values({
      name: normalizedName,
      parentId: normalizedParentId,
    }).returning()
  );

  if (result.err) {
    console.error('Database error creating category:', result.err);
    return errorResponse(c, 'Failed to create category', 500);
  }

  console.log('Category created successfully:', result.data[0]);
  return c.json({ data: result.data[0], err: null });
});

// Payment Modes
app.get('/payment-modes', auth, async (c) => {
  const result = await tryCatch(db.select().from(paymentModes));
  
  if (result.err) return errorResponse(c, 'Failed to fetch payment modes', 500);
  
  return c.json({ data: result.data, err: null });
});

// Merchants
app.get('/merchants', auth, async (c) => {
  const payload = c.get('jwtPayload') as JwtPayload;
  const userId = payload.id;

  // Get unique merchant IDs used by this user
  const result = await tryCatch(
    db.select({
      id: merchants.id,
      name: merchants.name,
    })
    .from(merchants)
    .innerJoin(transactions, eq(transactions.receiverId, merchants.id))
    .where(eq(transactions.userId, userId))
    .groupBy(merchants.id)
  );

  if (result.err) return errorResponse(c, 'Failed to fetch unique merchants', 500);

  return c.json({ data: result.data, err: null });
});

// Transactions
app.post('/transactions', auth, async (c) => {
  const payload = c.get('jwtPayload') as JwtPayload;
  const userId = payload.id;
  
  const bodyResult = await tryCatch(c.req.json());
  if (bodyResult.err) return errorResponse(c, 'Invalid JSON body', 400);

  const { 
    transactionType, 
    paymentModeId, 
    amount, 
    currency, 
    receiverId, 
    merchantName,
    categoryId, 
    description, 
    officialTxnId,
    createdAt 
  } = bodyResult.data;

  if (!transactionType || amount === undefined) {
    return errorResponse(c, 'Missing required fields: transactionType and amount', 400);
  }

  const result = await tryCatch(db.transaction(async (tx) => {
    let finalReceiverId = receiverId;

    // If merchantName is provided, find or create the merchant
    if (merchantName && typeof merchantName === 'string') {
      const [existingMerchant] = await tx
        .select()
        .from(merchants)
        .where(eq(merchants.name, merchantName))
        .limit(1);

      if (existingMerchant) {
        finalReceiverId = existingMerchant.id;
      } else {
        const [newMerchant] = await tx
          .insert(merchants)
          .values({ name: merchantName })
          .returning();
        finalReceiverId = newMerchant!.id;
      }
    }

    return await tx.insert(transactions).values({
      userId,
      transactionType,
      paymentModeId,
      amount,
      currency: currency || 'INR',
      receiverId: finalReceiverId,
      categoryId,
      description,
      officialTxnId,
      ...(createdAt ? { createdAt } : {}),
    }).returning();
  }));

  if (result.err) return errorResponse(c, 'Failed to create transaction', 500);

  return c.json({ data: { message: 'Transaction created successfully' }, err: null });
});

app.get('/transactions', auth, async (c) => {
  const payload = c.get('jwtPayload') as JwtPayload;
  const userId = payload.id;

  const result = await tryCatch(
    db.select({
      id: transactions.id,
      amount: transactions.amount,
      currency: transactions.currency,
      transactionType: transactions.transactionType,
      description: transactions.description,
      createdAt: transactions.createdAt,
      merchantName: merchants.name,
      categoryId: categories.id,
      categoryName: categories.name,
      categoryParentId: categories.parentId,
      paymentModeName: paymentModes.name,
    })
    .from(transactions)
    .leftJoin(merchants, eq(transactions.receiverId, merchants.id))
    .leftJoin(categories, eq(transactions.categoryId, categories.id))
    .leftJoin(paymentModes, eq(transactions.paymentModeId, paymentModes.id))
    .where(eq(transactions.userId, userId))
    .orderBy(sql`${transactions.createdAt} DESC`)
  );

  if (result.err) return errorResponse(c, 'Failed to fetch transactions', 500);

  // Collect parent category IDs that need resolving
  const parentIds = [...new Set(
    result.data
      .map((r) => r.categoryParentId)
      .filter((pid): pid is number => pid !== null)
  )];

  // Batch-fetch parent category names
  let parentMap: Record<number, string> = {};
  if (parentIds.length > 0) {
    const parents = await db
      .select({ id: categories.id, name: categories.name })
      .from(categories)
      .where(sql`${categories.id} IN (${sql.join(parentIds.map(id => sql`${id}`), sql`, `)})`);
    for (const p of parents) {
      parentMap[p.id] = p.name;
    }
  }

  const data = result.data.map((row) => ({
    id: row.id,
    amount: row.amount,
    currency: row.currency,
    transactionType: row.transactionType,
    description: row.description,
    createdAt: row.createdAt,
    merchantName: row.merchantName,
    categoryName: row.categoryParentId ? (parentMap[row.categoryParentId] ?? null) : row.categoryName,
    subCategoryName: row.categoryParentId ? row.categoryName : null,
    paymentModeName: row.paymentModeName,
  }));

  return c.json({ data, err: null });
});

app.get('/transactions/:id', auth, async (c) => {
  const payload = c.get('jwtPayload') as JwtPayload;
  const id = parseInt(c.req.param('id'));

  if (isNaN(id)) return errorResponse(c, 'Invalid transaction ID', 400);

  const result = await tryCatch(
    db.select({
      id: transactions.id,
      amount: transactions.amount,
      currency: transactions.currency,
      transactionType: transactions.transactionType,
      description: transactions.description,
      officialTxnId: transactions.officialTxnId,
      createdAt: transactions.createdAt,
      updatedAt: transactions.updatedAt,
      merchantName: merchants.name,
      categoryName: categories.name,
      categoryParentId: categories.parentId,
      paymentModeName: paymentModes.name,
    })
    .from(transactions)
    .leftJoin(merchants, eq(transactions.receiverId, merchants.id))
    .leftJoin(categories, eq(transactions.categoryId, categories.id))
    .leftJoin(paymentModes, eq(transactions.paymentModeId, paymentModes.id))
    .where(and(eq(transactions.id, id), eq(transactions.userId, payload.id)))
    .limit(1)
  );

  if (result.err) return errorResponse(c, 'Failed to fetch transaction', 500);
  if (!result.data?.[0]) return errorResponse(c, 'Transaction not found', 404);

  const row = result.data[0];

  // If category has a parent, resolve the parent name
  let categoryName = row.categoryName;
  let subCategoryName: string | null = null;

  if (row.categoryParentId) {
    const [parent] = await db
      .select({ name: categories.name })
      .from(categories)
      .where(eq(categories.id, row.categoryParentId))
      .limit(1);
    categoryName = parent?.name ?? null;
    subCategoryName = row.categoryName;
  }

  const data = {
    id: row.id,
    amount: row.amount,
    currency: row.currency,
    transactionType: row.transactionType,
    description: row.description,
    officialTxnId: row.officialTxnId,
    createdAt: row.createdAt,
    updatedAt: row.updatedAt,
    merchantName: row.merchantName,
    categoryName,
    subCategoryName,
    paymentModeName: row.paymentModeName,
  };

  return c.json({ data, err: null });
});

app.get('/stats/monthly', auth, async (c) => {
  const payload = c.get('jwtPayload') as JwtPayload;
  const userId = payload.id;

  // Get start of current month
  const now = new Date();
  const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1).toISOString();

  const result = await tryCatch(
    db.select({
      date: sql<string>`date(${transactions.createdAt})`,
      type: transactions.transactionType,
      total: sql<number>`sum(${transactions.amount})`,
    })
    .from(transactions)
    .where(
      and(
        eq(transactions.userId, userId),
        sql`${transactions.createdAt} >= ${startOfMonth}`
      )
    )
    .groupBy(sql`date(${transactions.createdAt})`, transactions.transactionType)
  );

  if (result.err) return errorResponse(c, 'Failed to fetch stats', 500);

  // Transform data for the chart
  const dailyStats: Record<string, { date: string; credit: number; debit: number }> = {};
  
  result.data.forEach((row: any) => {
    if (!dailyStats[row.date]) {
      dailyStats[row.date] = { date: row.date, credit: 0, debit: 0 };
    }
    const entry = dailyStats[row.date]!;
    if (row.type === 'credit') {
      entry.credit = row.total;
    } else {
      entry.debit = row.total;
    }
  });

  const chartData = Object.values(dailyStats).sort((a, b) => a.date.localeCompare(b.date));

  return c.json({ data: chartData, err: null });
});

app.delete('/transactions/:id', auth, async (c) => {
  const payload = c.get('jwtPayload') as JwtPayload;
  const id = parseInt(c.req.param('id'));

  if (isNaN(id)) return errorResponse(c, 'Invalid transaction ID', 400);

  const result = await tryCatch(
    db.delete(transactions)
      .where(and(eq(transactions.id, id), eq(transactions.userId, payload.id)))
      .returning()
  );

  if (result.err) return errorResponse(c, 'Failed to delete transaction', 500);
  if (!result.data?.[0]) return errorResponse(c, 'Transaction not found or unauthorized', 404);

  return c.json({ data: { message: 'Transaction deleted successfully' }, err: null });
});

// --- CSV Export ---

/** Escape a value for safe inclusion in a CSV cell. */
const escapeCSV = (value: unknown): string => {
  if (value === null || value === undefined || value === '') return 'NULL';
  const str = String(value);
  // Wrap in double-quotes if the value contains special CSV characters
  if (str.includes(',') || str.includes('"') || str.includes('\n')) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
};

app.get('/export/csv', auth, async (c) => {
  const payload = c.get('jwtPayload') as JwtPayload;
  const userId = payload.id;
  const BATCH_SIZE = 500;

  // Self-join alias so we can resolve parent category names
  const parentCategories = alias(categories, 'parent_categories');

  const encoder = new TextEncoder();
  const CSV_HEADER =
    'ID,Type,Amount,Currency,Payment Mode,Category,Sub-category,Merchant,Description,Official Txn ID,Date,Updated At\n';

  // Cursor tracks the last id we returned so the next batch starts after it
  let cursor = 0;

  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(CSV_HEADER));
    },

    async pull(controller) {
      const batchResult = await tryCatch(
        db
          .select({
            id: transactions.id,
            transactionType: transactions.transactionType,
            amount: transactions.amount,
            currency: transactions.currency,
            paymentMode: paymentModes.name,
            categoryName: categories.name,
            categoryParentId: categories.parentId,
            parentCategoryName: parentCategories.name,
            merchantName: merchants.name,
            description: transactions.description,
            officialTxnId: transactions.officialTxnId,
            createdAt: transactions.createdAt,
            updatedAt: transactions.updatedAt,
          })
          .from(transactions)
          .leftJoin(merchants, eq(transactions.receiverId, merchants.id))
          .leftJoin(categories, eq(transactions.categoryId, categories.id))
          .leftJoin(parentCategories, eq(categories.parentId, parentCategories.id))
          .leftJoin(paymentModes, eq(transactions.paymentModeId, paymentModes.id))
          .where(
            and(
              eq(transactions.userId, userId),
              sql`${transactions.id} > ${cursor}`,
            ),
          )
          .orderBy(sql`${transactions.id} ASC`)
          .limit(BATCH_SIZE),
      );

      // On DB error, abort the stream so the client sees a broken download
      if (batchResult.err) {
        controller.error(batchResult.err);
        return;
      }

      const rows = batchResult.data;

      // No more rows — we're done
      if (rows.length === 0) {
        controller.close();
        return;
      }

      // Build a single string for the entire batch to minimise enqueue calls
      let chunk = '';
      for (const row of rows) {
        // Determine main category vs sub-category:
        //   - If parentId exists the row's category is a sub-category
        //   - The parent's name becomes the main "Category" column
        const mainCategory = row.categoryParentId
          ? row.parentCategoryName
          : row.categoryName;
        const subCategory = row.categoryParentId ? row.categoryName : '';

        chunk += [
          escapeCSV(row.id),
          escapeCSV(row.transactionType),
          escapeCSV(row.amount),
          escapeCSV(row.currency),
          escapeCSV(row.paymentMode),
          escapeCSV(mainCategory),
          escapeCSV(subCategory),
          escapeCSV(row.merchantName),
          escapeCSV(row.description),
          escapeCSV(row.officialTxnId),
          escapeCSV(row.createdAt),
          escapeCSV(row.updatedAt),
        ].join(',') + '\n';
      }

      controller.enqueue(encoder.encode(chunk));

      // Advance cursor to the last id in this batch
      cursor = rows[rows.length - 1]!.id;

      // If we got fewer rows than BATCH_SIZE we've exhausted the data
      if (rows.length < BATCH_SIZE) {
        controller.close();
      }
    },
  });

  const today = new Date().toISOString().slice(0, 10); // YYYY-MM-DD

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/csv',
      'Content-Disposition': `attachment; filename="rothsva-export-${today}.csv"`,
      'Transfer-Encoding': 'chunked',
    },
  });
});

export default {
  hostname: '0.0.0.0',
  port,
  fetch: app.fetch,
};
