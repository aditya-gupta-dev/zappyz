"""Exercise the user journey with Textual's headless terminal pilot."""

import tempfile
import unittest
from pathlib import Path

from sqlmodel import select
from textual.widgets import Input, Label, Select

from zapisi.models import Transaction
from zapisi.screens import MainScreen, ProfileScreen, TransactionTable
from zapisi.ui import ZapisiApp


class UserJourneyTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_save_switch_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = ZapisiApp(root)
            async with app.run_test(size=(100, 40)) as pilot:
                self.assertIsInstance(app.screen, ProfileScreen)
                app.screen.query_one("#profile-name", Input).value = "First"
                await pilot.click("#create-profile")
                await pilot.pause()
                self.assertIsInstance(app.screen, MainScreen)
                first_path = app.profile.path
                await pilot.press("a")
                await pilot.pause()
                app.screen.query_one("#amount", Input).value = "12.50"
                app.screen.query_one("#txn_type", Select).value = "debit"
                app.screen.query_one("#payment_mode_id", Select).value = 1
                await pilot.click("#save_txn")
                await pilot.pause()
                self.assertEqual(app.screen.query_one(TransactionTable).row_count, 1)
                await pilot.press("u")
                await pilot.pause()
                app.screen.query_one("#profile-name", Input).value = "Second"
                await pilot.click("#create-profile")
                await pilot.pause()
                self.assertNotEqual(app.profile.path, first_path)
                self.assertEqual(app.screen.query_one(TransactionTable).row_count, 0)
                await pilot.press("u")
                await pilot.pause()
                app.screen.query_one("#profile", Select).value = first_path.name
                await pilot.click("#open-profile")
                await pilot.pause()
                self.assertEqual(app.screen.query_one(TransactionTable).row_count, 1)
                # Table navigation remains available without a logout key collision.
                await pilot.press("l")
                self.assertIsInstance(app.screen, MainScreen)
            restored = ZapisiApp(root)
            async with restored.run_test(size=(100, 40)) as pilot:
                await pilot.pause()
                self.assertIsInstance(restored.screen, MainScreen)
                self.assertEqual(restored.profile.path, first_path)
                self.assertEqual(restored.screen.query_one(TransactionTable).row_count, 1)

    async def test_forms_scroll_on_standard_terminal(self):
        from textual.containers import VerticalScroll

        with tempfile.TemporaryDirectory() as directory:
            app = ZapisiApp(Path(directory))
            first = app.profiles.create("First")
            app.profiles.select(first)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.press("u")
                await pilot.pause()
                app.screen.query_one("#profile-name", Input).value = "Second"
                app.screen.query_one(VerticalScroll).scroll_end(animate=False)
                await pilot.pause()
                await pilot.click("#create-profile")
                await pilot.pause()
                self.assertEqual(app.profile.name, "Second")
                await pilot.press("a")
                await pilot.pause()
                app.screen.query_one("#amount", Input).value = "5"
                app.screen.query_one("#txn_type", Select).value = "credit"
                app.screen.query_one("#payment_mode_id", Select).value = 1
                app.screen.query_one(VerticalScroll).scroll_end(animate=False)
                await pilot.pause()
                await pilot.click("#save_txn")
                await pilot.pause()
                self.assertIsInstance(app.screen, MainScreen)
                self.assertEqual(app.screen.query_one(TransactionTable).row_count, 1)

    async def test_invalid_amount_does_not_save(self):
        with tempfile.TemporaryDirectory() as directory:
            app = ZapisiApp(Path(directory))
            app.profiles.select(app.profiles.create("User"))
            async with app.run_test(size=(100, 40)) as pilot:
                await pilot.pause()
                await pilot.press("a")
                await pilot.pause()
                app.screen.query_one("#amount", Input).value = "-2"
                app.screen.query_one("#txn_type", Select).value = "debit"
                await pilot.click("#save_txn")
                await pilot.pause()
                self.assertIn(
                    "greater than zero", str(app.screen.query_one("#txn_error", Label).render())
                )
                with app.database.session() as session:
                    self.assertEqual(session.exec(select(Transaction)).all(), [])
                await pilot.press("escape")
                self.assertIsInstance(app.screen, MainScreen)


if __name__ == "__main__":
    unittest.main()
