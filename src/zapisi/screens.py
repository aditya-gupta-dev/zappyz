"""Profile selection and finance forms for the terminal interface."""

import math
from typing import ClassVar

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Select

from .models import Category, Merchant, PaymentMode, Transaction


class ProfileScreen(Screen):
    BINDINGS: ClassVar = [Binding("q", "app.quit", "Quit"), Binding("escape", "back", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="profile-container"):
            yield Label("Welcome to Zappyz", id="title")
            yield Label("Each user has a separate database saved on this computer.")
            profiles = self.app.profiles.list_profiles()
            if profiles:
                yield Select(
                    [(profile.name, profile.path.name) for profile in profiles],
                    prompt="Choose a user",
                    id="profile",
                )
                yield Button("Open User", id="open-profile", variant="primary")
            else:
                yield Label("Create your first user to get started.")
            yield Input(placeholder="New user name", id="profile-name", max_length=80)
            yield Button("Create New User", id="create-profile", variant="success")
            yield Label("", id="profile-error")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        try:
            if event.button.id == "create-profile":
                profile = self.app.profiles.create(self.query_one("#profile-name", Input).value)
            elif event.button.id == "open-profile":
                filename = self.query_one("#profile", Select).value
                profile = next(
                    (
                        profile
                        for profile in self.app.profiles.list_profiles()
                        if profile.path.name == filename
                    ),
                    None,
                )
                if profile is None:
                    raise ValueError("Choose an existing user.")
            else:
                return
            self.app.open_profile(profile)
        except (ValueError, OSError, SQLAlchemyError) as error:
            self.query_one("#profile-error", Label).update(str(error))

    def action_back(self) -> None:
        if self.app.database is not None:
            self.app.switch_screen(MainScreen(self.app.profile.name))


class AddMerchantScreen(Screen):
    BINDINGS: ClassVar = [("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="merchant-container"):
            yield Label("Add New Merchant")
            yield Input(placeholder="Merchant Name", id="merchant_name")
            yield Label("", id="merchant_error")
            yield Button("Save Merchant", id="save_merchant", variant="primary")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save_merchant":
            name = self.query_one("#merchant_name", Input).value.strip()
            error_label = self.query_one("#merchant_error", Label)
            if not name:
                error_label.update("Merchant name required.")
                return
            try:
                with self.app.database.session() as session:
                    existing = session.exec(select(Merchant).where(Merchant.name == name)).first()
                    if existing:
                        error_label.update("Merchant already exists.")
                    else:
                        merchant = Merchant(name=name)
                        session.add(merchant)
                        session.commit()
                        self.app.pop_screen()
                        self.app.notify("Merchant added!")
            except (OSError, SQLAlchemyError):
                self.query_one("#merchant_error", Label).update(
                    "Could not save to the database. Check disk space and file permissions."
                )


class AddTransactionScreen(Screen):
    BINDINGS: ClassVar = [("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="add-txn-container"):
            yield Label("Add Transaction")
            yield Input(placeholder="Amount", id="amount", type="number")
            yield Select(
                [("Credit", "credit"), ("Debit", "debit")], prompt="Transaction Type", id="txn_type"
            )
            yield Input(placeholder="Description", id="description")
            yield Select([], prompt="Select Merchant (Optional)", id="merchant_id")
            yield Select([], prompt="Select Category (Optional)", id="category_id")
            yield Select([], prompt="Select Payment Mode", id="payment_mode_id")
            yield Label("", id="txn_error")
            yield Button("Save", id="save_txn", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        with self.app.database.session() as session:
            merchants = session.exec(select(Merchant)).all()
            self.query_one("#merchant_id", Select).set_options([(m.name, m.id) for m in merchants])

            categories = session.exec(select(Category)).all()
            self.query_one("#category_id", Select).set_options([(c.name, c.id) for c in categories])

            payment_modes = session.exec(select(PaymentMode)).all()
            self.query_one("#payment_mode_id", Select).set_options(
                [(p.name, p.id) for p in payment_modes]
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save_txn":
            amount = self.query_one("#amount", Input).value
            txn_type = self.query_one("#txn_type", Select).value
            description = self.query_one("#description", Input).value
            merchant_id = self.query_one("#merchant_id", Select).value
            category_id = self.query_one("#category_id", Select).value
            payment_mode_id = self.query_one("#payment_mode_id", Select).value
            error_label = self.query_one("#txn_error", Label)

            if not amount or txn_type not in ("credit", "debit"):
                error_label.update("Amount and type are required.")
                return

            try:
                amount_value = float(amount)
                if not math.isfinite(amount_value) or amount_value <= 0:
                    raise ValueError
            except ValueError:
                error_label.update("Enter a finite amount greater than zero.")
                return
            if not isinstance(payment_mode_id, int):
                error_label.update("Choose a payment mode.")
                return

            try:
                with self.app.database.session() as session:
                    txn = Transaction(
                        amount=amount_value,
                        transaction_type=txn_type,
                        description=description,
                        receiver_id=merchant_id if isinstance(merchant_id, int) else None,
                        category_id=category_id if isinstance(category_id, int) else None,
                        payment_mode_id=payment_mode_id,
                    )
                    session.add(txn)
                    session.commit()
                    self.app.pop_screen()
                    self.app.notify("Transaction saved!")
                    if hasattr(self.app.screen, "refresh_data"):
                        self.app.screen.refresh_data()
            except (OSError, SQLAlchemyError):
                self.query_one("#txn_error", Label).update(
                    "Could not save to the database. Check disk space and file permissions."
                )


class TransactionTable(DataTable):
    BINDINGS: ClassVar = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("h", "cursor_left", "Left", show=False),
        Binding("l", "cursor_right", "Right", show=False),
    ]


class MainScreen(Screen):
    def __init__(self, profile_name: str):
        super().__init__()
        self.sub_title = profile_name

    BINDINGS: ClassVar = [
        Binding("a", "add_transaction", "Add Transaction", priority=True),
        Binding("m", "add_merchant", "Add Merchant", priority=True),
        Binding("u", "switch_profile", "Switch User", priority=True),
        Binding("q", "app.quit", "Quit", priority=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="txn-pane"):
            yield Label("Recent Transactions")
            yield TransactionTable(id="txn-table")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(TransactionTable)
        table.add_columns("Date", "Type", "Amount", "Description")
        self.refresh_data()

    def refresh_data(self) -> None:
        table = self.query_one(TransactionTable)
        table.clear()

        with self.app.database.session() as session:
            txns = session.exec(
                select(Transaction).order_by(Transaction.created_at.desc()).limit(20)
            ).all()
            for txn in txns:
                table.add_row(
                    txn.created_at.strftime("%Y-%m-%d"),
                    txn.transaction_type,
                    str(txn.amount),
                    txn.description or "",
                )

    def action_add_transaction(self) -> None:
        self.app.push_screen(AddTransactionScreen())

    def action_add_merchant(self) -> None:
        self.app.push_screen(AddMerchantScreen())

    def action_switch_profile(self) -> None:
        self.app.switch_screen(ProfileScreen())
