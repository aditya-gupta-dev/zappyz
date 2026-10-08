# Zappyz

A Python terminal app for personal finance. Users are local profiles: each has an
independent SQLite database, with no login, email address, password, or session expiry.

## Run

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```sh
uv run zappyz
```

The first launch asks you to create a user. Later launches reopen the last selected
user. Press **u** to open another user or create a new one. Saved transactions stay
in the previous user's database when you switch or quit.

Keys: **a** adds a transaction, **m** adds a merchant, **u** switches users,
**q** quits, **Esc** returns from a form. **h/j/k/l** navigate the transaction table.

## Build a standalone executable

From this project directory:

```sh
uv run --group build pyinstaller --clean --noconfirm zapisi.spec
```

Or run `make build`. The executable is `dist/zappyz` (`dist/zappyz.exe` on Windows).
It includes Python and the app dependencies. Build on the operating system and
architecture where you intend to run it.

```sh
./dist/zappyz
```

To run it as `zappyz` from anywhere on Linux, install it into a directory on your PATH:

```sh
mkdir -p "$HOME/.local/bin"
install -m 755 dist/zappyz "$HOME/.local/bin/zappyz"
zappyz
```

Ensure `$HOME/.local/bin` is on your PATH. `uv run zapisi` remains available as a
compatibility alias for the old command.

## Data and backups

On Linux, data lives in `${XDG_CACHE_HOME:-~/.cache}/zappyz/`:

- `profiles/<unique-id>.db`: one SQLite file per user; its display name is inside the file.
- `settings.json`: the last selected profile and legacy import history.

On macOS, the default directory is `~/Library/Caches/zappyz/`.
On Windows, it is `%LOCALAPPDATA%/Cache/zappyz/`.

Existing profiles and settings in the previous default data directory are moved
to the cache directory automatically when it has not yet been created.

Set `ZAPISI_DATA_DIR` or pass `--data-dir /path/to/data` to choose another directory.
Data paths are independent of the executable location and current working directory.

Close the app before copying a profile database for backup. Restore it by placing
the `.db` file in the data directory's `profiles/` folder; it appears in the user
picker. Files can be opened with ordinary SQLite tools without a password.

## Existing data

If `database.db` exists in the working directory, Zappyz copies each existing user
into a separate profile on startup. Each user's transactions are separated, while
categories, merchants, and payment modes are preserved. Password hashes and email
addresses are not copied. Imports are tracked so restarting does not repeat them.
The original database and old `session.json` are left untouched; the app no longer
uses the session file.

To import a database elsewhere:

```sh
zappyz --import-legacy /path/to/database.db
```

## Development

```sh
make check
make test
```

`src/zapisi/models.py` defines the schema; `database.py` handles connections and
seed data; `profiles.py` handles profile files, selection, and legacy import;
`screens.py` contains forms and the dashboard; `ui.py` owns the app lifecycle.
Obsolete TypeScript backend references were removed; this is a standalone Python app.
