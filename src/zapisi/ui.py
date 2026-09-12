import json
import os
from datetime import datetime, timedelta
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal, Grid
from textual.widgets import Header, Footer, Button, Input, Label, DataTable, Static, ListItem, ListView, Select
from textual.screen import Screen
from textual.binding import Binding
from textual.theme import Theme

from sqlmodel import select, func
from .database import get_session, create_db_and_tables
from .models import User, Transaction, Category, Merchant, PaymentMode
from .auth import verify_password, get_password_hash

SESSION_FILE = "session.json"

def get_current_session():
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r") as f:
                data = json.load(f)
                exp = datetime.fromisoformat(data["expires_at"])
                if datetime.now() < exp:
                    return data["user_id"]
        except Exception:
            pass
    return None

def save_session(user_id):
    expires_at = datetime.now() + timedelta(hours=6)
    with open(SESSION_FILE, "w") as f:
        json.dump({"user_id": user_id, "expires_at": expires_at.isoformat()}, f)
        
def clear_session():
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)

class LoginScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="login-container"):
            yield Label("Welcome to Zapisi", id="title")
            yield Input(placeholder="Email", id="email")
            yield Input(placeholder="Password", id="password", password=True)
            yield Input(placeholder="Name (for Register only)", id="name")
            yield Label("", id="error-message")
            with Horizontal():
                yield Button("Login", id="login", variant="primary")
                yield Button("Register", id="register", variant="success")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        email = self.query_one("#email", Input).value
        password = self.query_one("#password", Input).value
        name = self.query_one("#name", Input).value
        error_label = self.query_one("#error-message", Label)

        if not email or not password:
            error_label.update("Email and password are required.")
            return

        with get_session() as session:
            if event.button.id == "login":
                user = session.exec(select(User).where(User.email == email)).first()
                if not user or not verify_password(password, user.password_hash):
                    error_label.update("Invalid email or password.")
                else:
                    self.app.login(user.id)
            elif event.button.id == "register":
                if not name:
                    error_label.update("Name is required for registration.")
                    return
                user = session.exec(select(User).where(User.email == email)).first()
                if user:
                    error_label.update("Email already registered.")
                else:
                    new_user = User(name=name, email=email, password_hash=get_password_hash(password))
                    session.add(new_user)
                    session.commit()
                    session.refresh(new_user)
                    self.app.login(new_user.id)

class AddMerchantScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Label("Add New Merchant")
            yield Input(placeholder="Merchant Name", id="merchant_name")
            yield Label("", id="merchant_error")
            yield Button("Save Merchant", id="save_merchant", variant="primary")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save_merchant":
            name = self.query_one("#merchant_name", Input).value
            error_label = self.query_one("#merchant_error", Label)
            if not name:
                error_label.update("Merchant name required.")
                return
            with get_session() as session:
                existing = session.exec(select(Merchant).where(Merchant.name == name)).first()
                if existing:
                    error_label.update("Merchant already exists.")
                else:
                    merchant = Merchant(name=name)
                    session.add(merchant)
                    session.commit()
                    self.app.pop_screen()
                    self.app.notify("Merchant added!")

class AddTransactionScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="add-txn-container"):
            yield Label("Add Transaction")
            yield Input(placeholder="Amount", id="amount", type="number")
            yield Select([("Credit", "credit"), ("Debit", "debit")], prompt="Transaction Type", id="txn_type")
            yield Input(placeholder="Description", id="description")
            yield Select([], prompt="Select Merchant (Optional)", id="merchant_id")
            yield Select([], prompt="Select Category (Optional)", id="category_id")
            yield Select([], prompt="Select Payment Mode", id="payment_mode_id")
            yield Label("", id="txn_error")
            yield Button("Save", id="save_txn", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        with get_session() as session:
            merchants = session.exec(select(Merchant)).all()
            self.query_one("#merchant_id", Select).set_options([(m.name, m.id) for m in merchants])
            
            categories = session.exec(select(Category)).all()
            self.query_one("#category_id", Select).set_options([(c.name, c.id) for c in categories])
            
            payment_modes = session.exec(select(PaymentMode)).all()
            self.query_one("#payment_mode_id", Select).set_options([(p.name, p.id) for p in payment_modes])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save_txn":
            amount = self.query_one("#amount", Input).value
            txn_type = self.query_one("#txn_type", Select).value
            description = self.query_one("#description", Input).value
            merchant_id = self.query_one("#merchant_id", Select).value
            category_id = self.query_one("#category_id", Select).value
            payment_mode_id = self.query_one("#payment_mode_id", Select).value
            error_label = self.query_one("#txn_error", Label)

            if not amount or not txn_type or txn_type == Select.BLANK:
                error_label.update("Amount and type are required.")
                return

            with get_session() as session:
                txn = Transaction(
                    user_id=self.app.user_id,
                    amount=float(amount),
                    transaction_type=txn_type,
                    description=description,
                    receiver_id=merchant_id if merchant_id != Select.BLANK else None,
                    category_id=category_id if category_id != Select.BLANK else None,
                    payment_mode_id=payment_mode_id if payment_mode_id != Select.BLANK else None
                )
                session.add(txn)
                session.commit()
                self.app.pop_screen()
                self.app.notify("Transaction saved!")
                if hasattr(self.app.screen, "refresh_data"):
                    self.app.screen.refresh_data()

class MainScreen(Screen):
    BINDINGS = [
        Binding("a", "add_transaction", "Add Transaction", priority=True),
        Binding("m", "add_merchant", "Add Merchant", priority=True),
        Binding("l", "logout", "Logout", priority=True),
        Binding("q", "quit", "Quit", priority=True)
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="txn-pane"):
            yield Label("Recent Transactions")
            yield DataTable(id="txn-table")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Date", "Type", "Amount", "Description")
        self.refresh_data()

    def refresh_data(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        
        with get_session() as session:
            txns = session.exec(select(Transaction).where(Transaction.user_id == self.app.user_id).order_by(Transaction.created_at.desc()).limit(20)).all()
            for txn in txns:
                table.add_row(txn.created_at.strftime("%Y-%m-%d"), txn.transaction_type, str(txn.amount), txn.description or "")
                


    def action_add_transaction(self) -> None:
        self.app.push_screen(AddTransactionScreen())

    def action_add_merchant(self) -> None:
        self.app.push_screen(AddMerchantScreen())
        
    def action_logout(self) -> None:
        clear_session()
        self.app.user_id = None
        self.app.switch_screen(LoginScreen())

class ZapisiApp(App):
    CSS = """
    Screen {
        background: transparent;
    }
    Vertical, Horizontal, Grid, Container {
        background: transparent;
    }
    #login-container {
        align: center middle;
        padding: 2;
    }
    #title {
        text-align: center;
        margin-bottom: 2;
    }
    #error-message {
        color: $error;
        margin-top: 1;
    }
    #main-grid {
        layout: grid;
        grid-size: 2 1;
        grid-columns: 1fr 1fr;
    }
    #stats-pane {
        border-right: solid;
        padding: 1;
    }
    #txn-pane {
        padding: 1;
    }
    #add-txn-container {
        padding: 2;
        align: center middle;
    }
    """

    def __init__(self):
        super().__init__()
        self.user_id = get_current_session()

    def on_mount(self) -> None:
        self.register_theme(Theme(
            name="terminal_theme",
            primary="#8AADD3",
            secondary="#C09BE5",
            warning="#FFDCEE",
            error="#D656FF",
            success="#64DCF0",
            accent="#8CD2F3",
            foreground="#E9D3DC",
            background="transparent",
            surface="transparent",
            panel="transparent",
            dark=True,
        ))
        self.theme = "terminal_theme"
        create_db_and_tables()
        if self.user_id:
            self.push_screen(MainScreen())
        else:
            self.push_screen(LoginScreen())

    def login(self, user_id: int) -> None:
        self.user_id = user_id
        save_session(user_id)
        self.push_screen(MainScreen())
