"""Zappyz: a local personal finance terminal application."""

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Zappyz — personal finance with local user databases"
    )
    parser.add_argument(
        "--data-dir", type=Path, help="Directory for profile databases and settings"
    )
    parser.add_argument(
        "--import-legacy",
        type=Path,
        default=Path.cwd() / "database.db",
        help="Copy users from an old database (default: ./database.db if present)",
    )
    parser.add_argument("--version", action="version", version="zappyz 0.1.0")
    args = parser.parse_args()

    from .ui import ZapisiApp

    ZapisiApp(data_directory=args.data_dir, legacy_path=args.import_legacy).run()
