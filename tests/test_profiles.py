"""Regression tests for persistence, isolation, and non-destructive migration."""

import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlmodel import select

from zapisi.database import Database
from zapisi.models import Category, PaymentMode, Transaction
from zapisi.profiles import ProfileStore, default_data_directory


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.store = ProfileStore(self.root / "data")

    def test_cache_directory_respects_platform_and_overrides(self):
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("zapisi.profiles.Path.home", return_value=self.root),
        ):
            with patch("zapisi.profiles.sys.platform", "linux"):
                self.assertEqual(default_data_directory(), self.root / ".cache" / "zappyz")
                with patch.dict("os.environ", {"XDG_CACHE_HOME": str(self.root / "custom-cache")}):
                    self.assertEqual(
                        default_data_directory(), self.root / "custom-cache" / "zappyz"
                    )
            with patch("zapisi.profiles.sys.platform", "darwin"):
                self.assertEqual(
                    default_data_directory(), self.root / "Library" / "Caches" / "zappyz"
                )
            with patch("zapisi.profiles.sys.platform", "win32"):
                self.assertEqual(
                    default_data_directory(), self.root / "AppData" / "Local" / "Cache" / "zappyz"
                )
            with patch.dict("os.environ", {"ZAPISI_DATA_DIR": str(self.root / "override")}):
                self.assertEqual(default_data_directory(), self.root / "override")

    def test_existing_profiles_move_to_cache_with_selection(self):
        old = self.root / "old-data" / "zappyz"
        destination = self.root / "cache" / "zappyz"
        previous = ProfileStore(old)
        profile = previous.create("Existing")
        previous.select(profile)
        original = profile.path.read_bytes()
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("zapisi.profiles.default_data_directory", return_value=destination),
            patch("zapisi.profiles.previous_data_directory", return_value=old),
        ):
            migrated = ProfileStore()
        self.assertFalse(old.exists())
        self.assertEqual(migrated.active_profile().name, "Existing")
        self.assertEqual(migrated.active_profile().path.parent, destination / "profiles")
        self.assertEqual(migrated.active_profile().path.read_bytes(), original)

    def test_profiles_isolate_data_and_remember_selection(self):
        first = self.store.create("First")
        second = self.store.create("Second")
        self.assertNotEqual(first.path, second.path)
        database = Database(first.path)
        with database.session() as session:
            session.add(Transaction(amount=42, transaction_type="debit"))
            session.commit()
        database.close()
        database = Database(second.path)
        with database.session() as session:
            self.assertEqual(session.exec(select(Transaction)).all(), [])
            self.assertEqual(len(session.exec(select(PaymentMode)).all()), 5)
        database.close()
        self.store.select(first)
        restored = ProfileStore(self.root / "data")
        self.assertEqual(restored.active_profile(), first)
        database = Database(restored.active_profile().path)
        with database.session() as session:
            self.assertEqual(session.exec(select(Transaction)).one().amount, 42)
        database.close()
        with sqlite3.connect(first.path) as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
            self.assertNotIn("user", tables)
            columns = {row[1] for row in connection.execute("PRAGMA table_info(transactions)")}
            self.assertNotIn("user_id", columns)

    def test_names_and_unrelated_files(self):
        for name in ("", " ", "x" * 81, "bad\nname"):
            with self.assertRaises(ValueError):
                self.store.create(name)
        profile = self.store.create("  Ada  ")
        self.assertEqual(profile.name, "Ada")
        with self.assertRaises(ValueError):
            self.store.create("ADA")
        (self.store.profiles_directory / "broken.db").write_text("not a database")
        self.assertEqual(self.store.list_profiles(), [profile])
        self.store.settings_path.write_text("broken JSON")
        self.assertIsNone(self.store.active_profile())
        self.store.select(profile)
        profile.path.unlink()
        self.assertIsNone(self.store.active_profile())

    def test_initialization_is_idempotent(self):
        profile = self.store.create("User")
        database = Database(profile.path)
        database.initialize(profile.name)
        database.initialize(profile.name)
        with database.session() as session:
            self.assertEqual(len(session.exec(select(PaymentMode)).all()), 5)
            self.assertEqual(len(session.exec(select(Category)).all()), 9)
        database.close()

    def test_legacy_import_preserves_original_and_separates_users(self):
        legacy = self.root / "database.db"
        with sqlite3.connect(legacy) as connection:
            connection.executescript("""
                CREATE TABLE user (id INTEGER PRIMARY KEY, name TEXT, email TEXT, password_hash TEXT);
                INSERT INTO user VALUES (1, 'Ada', 'ada@example.com', 'old-hash');
                INSERT INTO user VALUES (2, 'Grace', 'grace@example.com', 'old-hash');
                CREATE TABLE payment_modes (id INTEGER PRIMARY KEY, name TEXT);
                INSERT INTO payment_modes VALUES (1, 'Cash');
                CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT, parent_id INTEGER);
                INSERT INTO categories VALUES (1, 'Food', NULL);
                CREATE TABLE merchants (id INTEGER PRIMARY KEY, name TEXT);
                INSERT INTO merchants VALUES (1, 'Shop');
                CREATE TABLE transactions (
                    id INTEGER PRIMARY KEY, user_id INTEGER, transaction_type TEXT,
                    payment_mode_id INTEGER, amount REAL, currency TEXT, receiver_id INTEGER,
                    category_id INTEGER, description TEXT, official_txn_id TEXT,
                    created_at TEXT, updated_at TEXT
                );
                INSERT INTO transactions VALUES
                    (1, 1, 'debit', 1, 10, 'INR', 1, 1, 'Ada expense', NULL,
                     '2026-01-01 12:00:00', '2026-01-01 12:00:00'),
                    (2, 2, 'credit', 1, 20, 'INR', 1, 1, 'Grace income', NULL,
                     '2026-01-02 12:00:00', '2026-01-02 12:00:00');
            """)
        original_digest = hashlib.sha256(legacy.read_bytes()).hexdigest()
        self.store.import_legacy(legacy)
        self.store.import_legacy(legacy)
        profiles = self.store.list_profiles()
        self.assertEqual([profile.name for profile in profiles], ["Ada", "Grace"])
        for profile, expected_amount in zip(profiles, (10, 20)):
            database = Database(profile.path)
            with database.session() as session:
                transaction = session.exec(select(Transaction)).one()
                self.assertEqual(transaction.amount, expected_amount)
                self.assertEqual(session.get(Category, transaction.category_id).name, "Food")
            database.close()
            self.assertNotIn(b"old-hash", profile.path.read_bytes())
        self.assertEqual(hashlib.sha256(legacy.read_bytes()).hexdigest(), original_digest)


if __name__ == "__main__":
    unittest.main()
