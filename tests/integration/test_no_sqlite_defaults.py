import os


def _walk_repo(root):
    for base, _dirs, files in os.walk(root):
        for f in files:
            yield os.path.join(base, f)


def test_no_sqlite_specific_defaults_present():
    """
    Ensure we don't use SQLite-specific defaults like datetime('now') in migrations/models.

    Criterion: grep does not find "datetime('now')" anywhere in the repo.
    """
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
    offending = []
    needle = "datetime('now')"
    for path in _walk_repo(root):
        # Only scan text-like files
        if any(path.endswith(ext) for ext in (".py", ".sql", ".ini", ".md", ".yml", ".yaml")):
            try:
                with open(path, encoding="utf-8", errors="ignore") as fh:
                    txt = fh.read()
                # Ignore this very test file to avoid false positive from the assertion message
                if needle in txt and not path.endswith("test_no_sqlite_defaults.py"):
                    offending.append(path)
            except Exception:
                pass
    assert not offending, f"Found SQLite-specific datetime('now') in: {offending}"
