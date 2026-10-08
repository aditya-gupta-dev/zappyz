# Project context

Zappyz is a local personal finance TUI built with Textual and SQLModel.
See README.md for current behavior, build instructions, data paths, and development checks.

There is no authentication. A user is a local profile with its own SQLite file.
Profile selection is persisted without expiry. The app owns one database connection
at a time; each form writes to the currently selected database. All new profile
schemas omit account credentials and transaction user IDs.

The old shared database is copied into separate profiles on startup when present.
This import reads the source without modifying it and does not copy credentials.

Keep the terminal palette and h/j/k/l table navigation. The dashboard intentionally
shows a simple recent-transactions table without charts.
