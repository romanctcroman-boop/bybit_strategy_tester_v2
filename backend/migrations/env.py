from __future__ import annotations
import logging
from logging.config import fileConfig
import os

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')

# Optional: support loading SQLAlchemy metadata from an environment variable to
# enable `alembic revision --autogenerate` without editing this file.
# Set ALEMBIC_TARGET_METADATA to a value like 'backend.models:Base' (module:attribute).
def _load_target_metadata_from_env():
    spec = os.environ.get('ALEMBIC_TARGET_METADATA')
    if not spec:
        return None
    if ':' not in spec:
        logger.warning('ALEMBIC_TARGET_METADATA must be in module:attribute form')
        return None
    module_name, attr = spec.split(':', 1)
    try:
        module = __import__(module_name, fromlist=[attr])
        return getattr(module, attr).metadata
    except Exception as e:
        logger.exception('Failed to import target metadata from %s: %s', spec, e)
        return None

# Allow autogenerate to pick up metadata if ALEMBIC_TARGET_METADATA is set.
target_metadata = _load_target_metadata_from_env()


# Sanitize helper reused in both offline/online modes
def _sanitize_url(url: str) -> str:
    try:
        for ch in ("\u00A0", "\u2007", "\u202F"):
            url = url.replace(ch, "")
        return url.strip()
    except Exception:
        return url


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.
    """
    # Prefer DATABASE_URL environment variable when present (supports CI envs).
    # Also tolerate placeholders in alembic.ini such as %(DATABASE_URL)s or ${DATABASE_URL}.
    def _read_config_url():
        # Attempt to read the raw value from the parsed ini to avoid configparser
        # interpolation errors when the ini uses %(DATABASE_URL)s. `Config.get_main_option`
        # triggers interpolation which will raise InterpolationMissingOptionError if
        # DATABASE_URL is not defined as an option in the ini. We therefore read the
        # raw value from config.file_config when available.
        raw = None
        try:
            # config.file_config is a ConfigParser; use raw=True to disable interpolation
            raw = config.file_config.get(config.config_ini_section, 'sqlalchemy.url', raw=True)
        except Exception:
            # Fall back to alembic's accessor which may attempt interpolation; guard it
            try:
                raw = config.get_main_option('sqlalchemy.url')
            except Exception:
                raw = None

        if not raw:
            return None
        # If the ini contains a common placeholder token, treat as unset
        if any(tok in raw for tok in ('%(DATABASE_URL)s', '${DATABASE_URL}', 'driver://', 'user:pass')):
            return None
        return raw

    url = os.environ.get('DATABASE_URL') or _read_config_url()
    if url:
        url = _sanitize_url(url)
        if url.startswith('postgresql://') and '+' not in url:
            url = url.replace('postgresql://', 'postgresql+psycopg://', 1)
    # Basic validation to provide a helpful error if the URL is still a placeholder
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set or alembic.ini contains a placeholder.\n"
            "Set the DATABASE_URL environment variable to a valid SQLAlchemy URL, for example:\n"
            "  (PowerShell) $env:DATABASE_URL = 'postgresql://user:pass@localhost:5432/dbname'\n"
            "  (bash) export DATABASE_URL='postgresql://user:pass@localhost:5432/dbname'\n"
            "Then re-run `alembic upgrade head`."
        )
    context.configure(url=url, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we create an Engine and associate a connection with the context.
    """
    from sqlalchemy import create_engine

    # Prefer DATABASE_URL environment variable when present. Reuse same helper logic.
    def _read_config_url():
        # Read raw value from ini to avoid interpolation errors (same approach as offline)
        raw = None
        try:
            raw = config.file_config.get(config.config_ini_section, 'sqlalchemy.url', raw=True)
        except Exception:
            try:
                raw = config.get_main_option('sqlalchemy.url')
            except Exception:
                raw = None

        if not raw:
            return None
        if any(tok in raw for tok in ('%(DATABASE_URL)s', '${DATABASE_URL}', 'driver://', 'user:pass')):
            return None
        return raw

    url = os.environ.get('DATABASE_URL') or _read_config_url()
    if url:
        url = _sanitize_url(url)
        if url.startswith('postgresql://') and '+' not in url:
            url = url.replace('postgresql://', 'postgresql+psycopg://', 1)
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set or alembic.ini contains a placeholder.\n"
            "Set the DATABASE_URL environment variable to a valid SQLAlchemy URL, for example:\n"
            "  (PowerShell) $env:DATABASE_URL = 'postgresql://user:pass@localhost:5432/dbname'\n"
            "  (bash) export DATABASE_URL='postgresql://user:pass@localhost:5432/dbname'\n"
            "Then re-run `alembic upgrade head`."
        )

    engine = create_engine(url)

    try:
        with engine.connect() as connection:
            context.configure(connection=connection)

            with context.begin_transaction():
                context.run_migrations()
    except UnicodeDecodeError as e:
        raise RuntimeError(
            "Failed to decode bytes while connecting to the database.\n"
            "This often indicates an invalid or mangled DATABASE_URL or a password/username containing non-ASCII characters that are not percent-encoded.\n"
            "Troubleshooting steps:\n"
            "  1) Verify your DATABASE_URL is correct and Postgres is listening:\n"
            "       $env:DATABASE_URL = 'postgresql://user:pass@host:5432/dbname'\n"
            "       psql \"$env:DATABASE_URL\"\n"
            "  2) If your password/user contains special characters, percent-encode them (e.g. @ -> %40).\n"
            "  3) Try connecting with the `psycopg2` quick test script in `scripts/check_db_connect.py`.\n"
            f"Original error: {e}"
        )
    except Exception as e:
        # Import here to avoid heavy deps at module import time
        try:
            from sqlalchemy.exc import OperationalError
        except Exception:
            OperationalError = None

        if OperationalError and isinstance(e, OperationalError):
            raise RuntimeError(
                "OperationalError while connecting to the database. Check that your DB is running and reachable.\n"
                "Test connection with psql and ensure credentials are correct.\n"
                f"Original error: {e}"
            )
        raise


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
