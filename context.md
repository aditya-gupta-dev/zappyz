# Zapisi - Personal Finance TUI

This project is a modern Python Text User Interface (TUI) application designed to manage personal finance transactions. It implements the schema and features provided in the `uses.ts` file, utilizing Python frameworks like `textual` and `sqlmodel`.

## Project Structure

- `pyproject.toml`: The UV project configuration. Includes all dependencies (`textual`, `textual-plotext`, `sqlmodel`, `bcrypt`, `passlib`).
- `src/zapisi/__init__.py`: Entry point for the application. Contains the `main()` function which initializes and runs the Textual app.
- `src/zapisi/models.py`: Defines the database schemas using `sqlmodel`. Tables include:
  - `User`: Handles authentication and user details.
  - `PaymentMode`: Modes of payment (e.g., UPI, Bank, Cash).
  - `Category`: Transaction categories, supporting nested sub-categories.
  - `Merchant`: The receivers for the transactions.
  - `Transaction`: The core table storing amounts, types (credit/debit), foreign keys, and descriptions.
- `src/zapisi/database.py`: Handles SQLite database initialization, creating the `database.db` file, and populating default categories and payment modes.
- `src/zapisi/auth.py`: Password hashing and verification using `passlib` and `bcrypt`.
- `src/zapisi/ui.py`: The Textual TUI interface containing multiple screens:
  - `LoginScreen`: Handles user login and registration.
  - `MainScreen`: Displays a graph of monthly transactions (via `textual-plotext`) and a datatable of recent transactions.
  - `AddTransactionScreen`: Form to submit new transactions.
  - `AddMerchantScreen`: Form to add new merchants.
- `session.json`: A file generated at runtime to persist user sessions for up to 6 hours.

## Key Features & Keybinds
- **Login / Register**: Automatically hashes passwords and logs in upon successful authentication. Session is maintained for 6 hours.
- **Main View**:
  - Automatically loads and creates tables if they don't exist.
  - Fetches the current month's stats and displays them in a bar graph.
  - Loads the latest 20 transactions into a data table.
- **Keybinds**:
  - `A`: Add Transaction
  - `M`: Add Merchant
  - `L`: Logout
  - `Q`: Quit

## How to Run
Since this project is managed by UV, it can be executed using the registered entry point:
```bash
uv run zapisi
```
Alternatively:
```bash
uv run python -m zapisi
```
