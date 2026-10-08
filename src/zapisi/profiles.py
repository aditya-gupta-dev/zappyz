"""Password-free local profiles, persistent selection, and legacy data import."""

import json
import os
import shutil
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .database import Database


def default_data_directory() -> Path:
    if directory := os.environ.get("ZAPISI_DATA_DIR"):
        return Path(directory).expanduser().resolve()
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return root / "Cache" / "zappyz"
    if sys.platform == "darwin":
        root = Path.home() / "Library" / "Caches"
    else:
        root = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return root / "zappyz"


def previous_data_directory() -> Path:
    """Old default location, used only to migrate existing local profiles."""
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return root / "zappyz"


@dataclass(frozen=True)
class Profile:
    name: str
    path: Path


class ProfileStore:
    def __init__(self, directory: Path | None = None):
        self.directory = (directory or default_data_directory()).resolve()
        if directory is None and not os.environ.get("ZAPISI_DATA_DIR"):
            previous = previous_data_directory().resolve()
            if previous != self.directory and previous.is_dir() and not self.directory.exists():
                self.directory.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(previous), str(self.directory))
        self.profiles_directory = self.directory / "profiles"
        self.profiles_directory.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.directory / "settings.json"

    def _settings(self) -> dict:
        try:
            data = json.loads(self.settings_path.read_text())
            return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_settings(self, settings: dict) -> None:
        temporary = self.settings_path.with_name(f"settings-{uuid4().hex}.tmp")
        try:
            temporary.write_text(json.dumps(settings, indent=2) + "\n")
            temporary.replace(self.settings_path)
        finally:
            temporary.unlink(missing_ok=True)

    def list_profiles(self) -> list[Profile]:
        profiles = []
        for path in sorted(self.profiles_directory.glob("*.db")):
            try:
                with closing(sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)) as connection:
                    row = connection.execute(
                        "SELECT name FROM profile_info WHERE id = 1"
                    ).fetchone()
                if row:
                    profiles.append(Profile(row[0], path))
            except sqlite3.DatabaseError:
                continue  # An unrelated or incomplete file is not a profile.
        return sorted(profiles, key=lambda profile: (profile.name.casefold(), profile.path.name))

    def create(self, name: str) -> Profile:
        name = name.strip()
        if not name or len(name) > 80 or any(ord(character) < 32 for character in name):
            raise ValueError("Enter a profile name with 1–80 printable characters.")
        if any(profile.name.casefold() == name.casefold() for profile in self.list_profiles()):
            raise ValueError("A profile with that name already exists.")
        profile = Profile(name, self.profiles_directory / f"{uuid4().hex}.db")
        database = Database(profile.path)
        try:
            database.initialize(name)
        except Exception:
            database.close()
            profile.path.unlink(missing_ok=True)
            raise
        finally:
            database.close()
        return profile

    def select(self, profile: Profile) -> None:
        if profile not in self.list_profiles():
            raise ValueError("This profile database is no longer available.")
        settings = self._settings()
        settings["active_profile"] = profile.path.name
        self._save_settings(settings)

    def active_profile(self) -> Profile | None:
        filename = self._settings().get("active_profile")
        return next(
            (profile for profile in self.list_profiles() if profile.path.name == filename), None
        )

    def import_legacy(self, source: Path) -> None:
        """Copy each old user's data once; never modify the original database."""
        source = source.resolve()
        if not source.is_file():
            return
        settings = self._settings()
        imported = settings.get("legacy_imports", {})
        if not isinstance(imported, dict):
            imported = {}
        source_key = str(source)
        with closing(sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True)) as legacy:
            legacy.row_factory = sqlite3.Row
            if not legacy.execute("SELECT name FROM sqlite_master WHERE name = 'user'").fetchone():
                return
            for user in legacy.execute('SELECT id, name FROM "user" ORDER BY id').fetchall():
                key = f"{source_key}:{user['id']}"
                if key in imported:
                    continue
                name = user["name"] or f"Imported user {user['id']}"
                name = (
                    "".join(character for character in name if ord(character) >= 32).strip()[:60]
                    or "Imported user"
                )
                names = {profile.name.casefold() for profile in self.list_profiles()}
                candidate = name
                suffix = 2
                while candidate.casefold() in names:
                    candidate = f"{name} ({suffix})"
                    suffix += 1
                # Build privately and publish only after the complete copy succeeds.
                destination = self.profiles_directory / f"{uuid4().hex}.db"
                temporary = destination.with_suffix(".importing")
                database = Database(temporary)
                try:
                    from sqlmodel import SQLModel

                    SQLModel.metadata.create_all(database.engine)
                    with closing(sqlite3.connect(temporary)) as target, target:
                        target.execute(
                            "INSERT INTO profile_info (id, name) VALUES (1, ?)", (candidate,)
                        )
                        for table in ("payment_modes", "categories", "merchants", "transactions"):
                            columns = [
                                row[1] for row in target.execute(f'PRAGMA table_info("{table}")')
                            ]
                            column_sql = ", ".join(f'"{column}"' for column in columns)
                            query = f'SELECT {column_sql} FROM "{table}"'
                            parameters = ()
                            if table == "transactions":
                                query += " WHERE user_id = ?"
                                parameters = (user["id"],)
                            rows = legacy.execute(query, parameters).fetchall()
                            placeholders = ", ".join("?" for _ in columns)
                            target.executemany(
                                f'INSERT INTO "{table}" ({column_sql}) VALUES ({placeholders})',
                                rows,
                            )
                        if target.execute("PRAGMA foreign_key_check").fetchall():
                            raise ValueError("The existing database contains broken references.")
                    database.initialize(candidate)
                    database.close()
                    temporary.replace(destination)
                finally:
                    database.close()
                    temporary.unlink(missing_ok=True)
                imported[key] = destination.name
                settings["legacy_imports"] = imported
                self._save_settings(settings)
