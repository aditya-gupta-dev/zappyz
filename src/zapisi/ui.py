"""Application lifecycle and ownership of the selected profile database."""

import sqlite3
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError
from textual.app import App
from textual.theme import Theme

from .database import Database
from .profiles import Profile, ProfileStore
from .screens import MainScreen, ProfileScreen


class ZapisiApp(App):
    TITLE = "Zappyz"
    CSS = """
    #profile-container {
        align: center middle;
        padding: 2;
    }
    #title {
        text-align: center;
        margin-bottom: 2;
    }
    #profile-error, #merchant_error, #txn_error {
        color: $error;
        margin-top: 1;
    }
    #txn-pane {
        padding: 1;
    }
    #add-txn-container, #merchant-container {
        padding: 2;
        align: center middle;
    }
    """

    def __init__(self, data_directory: Path | None = None, legacy_path: Path | None = None):
        super().__init__()
        self.profiles = ProfileStore(data_directory)
        self.legacy_path = legacy_path
        self.database: Database | None = None
        self.profile: Profile | None = None

    def on_mount(self) -> None:
        self.register_theme(
            Theme(
                name="terminal_theme",
                primary="#8AADD3",
                secondary="#C09BE5",
                warning="#FFDCEE",
                error="#D656FF",
                success="#64DCF0",
                accent="#8CD2F3",
                foreground="#E9D3DC",
                background="#151311",
                surface="#151311",
                panel="#151311",
                dark=True,
            )
        )
        self.theme = "terminal_theme"
        try:
            if self.legacy_path is not None:
                self.profiles.import_legacy(self.legacy_path)
            if profile := self.profiles.active_profile():
                self.open_profile(profile)
            else:
                self.push_screen(ProfileScreen())
        except (OSError, ValueError, sqlite3.DatabaseError, SQLAlchemyError) as error:
            self.push_screen(ProfileScreen())
            self.notify(f"Could not open profile data: {error}", severity="error", timeout=10)

    def open_profile(self, profile: Profile) -> None:
        database = Database(profile.path)
        try:
            database.initialize(profile.name)
            self.profiles.select(profile)
        except Exception:
            database.close()
            raise
        previous = self.database
        self.database = database
        self.profile = profile
        if previous is not None:
            previous.close()
        if len(self.screen_stack) > 1:
            self.switch_screen(MainScreen(profile.name))
        else:
            self.push_screen(MainScreen(profile.name))

    def on_unmount(self) -> None:
        if self.database is not None:
            self.database.close()
