from sqlmodel import SQLModel, create_engine, Session, select
from .models import User, PaymentMode, Category, Merchant, Transaction

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
engine = create_engine(sqlite_url)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    init_defaults()

def init_defaults():
    with Session(engine) as session:
        # Check and add modes
        modes = ['UPI', 'Bank', 'Cash', 'Crypto', 'Other']
        for mode in modes:
            if not session.exec(select(PaymentMode).where(PaymentMode.name == mode)).first():
                session.add(PaymentMode(name=mode))
        
        main_cats = ['Food', 'Travel', 'Fees', 'Misc', 'Rent']
        for cat_name in main_cats:
            cat = session.exec(select(Category).where(Category.name == cat_name)).first()
            if not cat:
                cat = Category(name=cat_name)
                session.add(cat)
                session.commit()
                session.refresh(cat)
            
            if cat_name == 'Food':
                sub_cats = ['Breakfast', 'Lunch', 'Snacks', 'Dinner']
                for sub in sub_cats:
                    if not session.exec(select(Category).where(Category.name == sub, Category.parent_id == cat.id)).first():
                        session.add(Category(name=sub, parent_id=cat.id))
        session.commit()

def get_session():
    return Session(engine)
