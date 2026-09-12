# Zapisi - Personal Finance TUI

This project is a modern Python Text User Interface (TUI) application designed to manage personal finance transactions. It implements the schema and features provided in the `uses.ts` file, utilizing Python frameworks like `textual` and `sqlmodel`.

## Current App Status & Features
The application has been refined with Several UX and UI improvements based on user feedback:
- **Authentication**: Uses the native `bcrypt` module directly (bypassing `passlib` to resolve password length crashes).
- **Styling**: Integrates seamlessly with the user's terminal by injecting their exact Ghostty color palette (e.g. `#E9D3DC`, `#8AADD3`) and using completely transparent backgrounds.
- **Forms**: Upgraded ID-based raw inputs in `AddTransactionScreen` to `Select` dropdowns that fetch names directly from the database for superior UX.
- **Data Display**: The main dashboard features a clean, simple `DataTable` of recent transactions (charting was removed per user request for simplicity).
- **Testing**: Pre-seeded with 50 randomized fake transactions spanning 30 days and various generic merchants to demonstrate the UI.

## Project Structure

- `pyproject.toml`: The UV project configuration. Includes core dependencies (`textual`, `sqlmodel`, `bcrypt`).
- `src/zapisi/__init__.py`: Entry point for the application. Contains the `main()` function which initializes and runs the Textual app.
- `src/zapisi/models.py`: Defines the database schemas using `sqlmodel`. Tables include:
  - `User`: Handles authentication and user details.
  - `PaymentMode`: Modes of payment (e.g., UPI, Bank, Cash).
  - `Category`: Transaction categories, supporting nested sub-categories.
  - `Merchant`: The receivers for the transactions.
  - `Transaction`: The core table storing amounts, types (credit/debit), foreign keys, and descriptions.
- `src/zapisi/database.py`: Handles SQLite database initialization, creating the `database.db` file, and populating default categories and payment modes.
- `src/zapisi/auth.py`: Password hashing and verification using `bcrypt`.
- `src/zapisi/ui.py`: The Textual TUI interface containing multiple screens:
  - `LoginScreen`: Handles user login and registration.
  - `MainScreen`: Displays a datatable of recent transactions.
  - `AddTransactionScreen`: Form to submit new transactions utilizing dropdowns.
  - `AddMerchantScreen`: Form to add new merchants.
- `session.json`: A file generated at runtime to persist user sessions for up to 6 hours.

## Keybinds (Main View)
- `A`: Add Transaction
- `M`: Add Merchant
- `L`: Logout
- `Q`: Quit

## How to Run
Since this project is managed by UV, it can be executed using the registered entry point:
```bash
uv run zapisi
```
