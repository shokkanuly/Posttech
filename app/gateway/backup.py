"""SQLite online backup API, for a backup or restoration to a NEW file only."""

import argparse
import os
import sqlite3
from pathlib import Path


def copy_database(source: Path, destination: Path) -> None:
    source = source.resolve(strict=True)
    destination = destination.absolute()
    # Exclusive creation prevents accidental overwrite, including a symlink target.
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    try:
        with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as origin:
            with sqlite3.connect(destination) as target:
                origin.backup(target)
                if target.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                    raise RuntimeError("Database integrity check failed")
    except Exception:
        destination.unlink()
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    copy_database(args.source, args.destination)
    print("Database copied to a new private file; integrity check passed.")


if __name__ == "__main__":
    main()
