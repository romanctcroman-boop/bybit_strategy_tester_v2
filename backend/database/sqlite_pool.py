"""
SQLite Connection Pool

Thread-safe connection pool for SQLite with WAL mode.
Provides connection reuse and proper cleanup.

THREAD SAFETY:
    Each thread gets its own connection via thread-local storage.
    This avoids the unsafe check_same_thread=False pattern.

Usage:
    from backend.database.sqlite_pool import get_pool

    pool = get_pool()
    with pool.connection() as conn:
        cursor = conn.execute("SELECT * FROM bybit_kline_audit LIMIT 10")
        rows = cursor.fetchall()
"""

import logging
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from queue import Empty, Queue
from typing import Optional

logger = logging.getLogger(__name__)

# Thread-local storage for per-thread connections
_thread_local = threading.local()


class SQLiteConnectionPool:
    """
    Thread-safe connection pool for SQLite.

    THREAD SAFETY:
        Uses thread-local storage to give each thread its own connection.
        This is safer than check_same_thread=False which can cause
        data corruption in concurrent scenarios.

    Features:
    - Thread-local connections (one per thread)
    - Shared connection pool for non-thread-local usage
    - Pre-created connections with WAL mode
    - Automatic connection validation
    - Connection reuse with proper cleanup
    - Statistics and monitoring

    Attributes:
        db_path: Path to SQLite database file
        pool_size: Maximum number of connections in pool
        timeout: Connection timeout in seconds
        use_thread_local: If True, each thread gets dedicated connection
    """

    def __init__(
        self,
        db_path: str,
        pool_size: int = 10,
        timeout: float = 30.0,
        use_thread_local: bool = True,
    ):
        """
        Initialize connection pool.

        Args:
            db_path: Path to SQLite database file
            pool_size: Number of connections to maintain
            timeout: Timeout for acquiring connection
            use_thread_local: Use thread-local storage for connections (safer)
        """
        self.db_path = db_path
        self.pool_size = pool_size
        self.timeout = timeout
        self.use_thread_local = use_thread_local

        self._pool: Queue = Queue(pool_size)
        self._lock = threading.Lock()
        self._created = 0
        self._checkouts = 0
        self._checkins = 0
        self._initialized = False

        # Track thread-local connections for cleanup
        self._thread_connections: dict = {}
        self._thread_conn_lock = threading.Lock()

        # Initialize pool
        self._initialize_pool()

    def _initialize_pool(self) -> None:
        """Pre-create pool connections."""
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            # Ensure database file exists
            db_path = Path(self.db_path)
            if not db_path.exists():
                logger.warning(f"Database file does not exist: {db_path}")

            # Create connections
            for _ in range(self.pool_size):
                try:
                    conn = self._create_connection()
                    self._pool.put(conn)
                except Exception as e:
                    logger.error(f"Failed to create connection: {e}")
                    break

            self._initialized = True
            logger.info(
                f"SQLite pool initialized: {self._pool.qsize()}/{self.pool_size} "
                f"connections for {db_path.name}"
            )

    def _create_connection(self, for_thread_local: bool = False) -> sqlite3.Connection:
        """
        Create a new configured connection.

        Enables WAL mode and optimizes for performance.

        Args:
            for_thread_local: If True, uses check_same_thread=True (safer)
        """
        # For thread-local connections, we CAN use check_same_thread=True
        # because each thread has its own dedicated connection
        conn = sqlite3.connect(
            self.db_path,
            timeout=self.timeout,
            check_same_thread=not for_thread_local,  # True for thread-local (safer)
            isolation_level=None,  # Autocommit mode by default
        )

        # Configure for performance and concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA mmap_size=268435456")  # 256MB memory-mapped I/O

        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys=ON")

        # Use Row factory for dict-like access
        conn.row_factory = sqlite3.Row

        self._created += 1
        logger.debug(f"Created new SQLite connection (total: {self._created})")

        return conn

    def _validate_connection(self, conn: sqlite3.Connection) -> bool:
        """Check if connection is still alive."""
        try:
            conn.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False

    def _get_thread_connection(self) -> sqlite3.Connection:
        """
        Get or create a connection for the current thread.

        Each thread gets its own dedicated connection stored in thread-local storage.
        This is the safest approach for SQLite multi-threading.

        Returns:
            sqlite3.Connection dedicated to current thread
        """
        thread_id = threading.get_ident()

        # Check thread-local storage first
        if (
            hasattr(_thread_local, "connection")
            and _thread_local.connection is not None
        ):
            conn = _thread_local.connection
            if self._validate_connection(conn):
                return conn
            else:
                # Connection is dead, remove it
                logger.warning(f"Thread {thread_id} connection invalid, recreating")
                try:
                    conn.close()
                except Exception as e:
                    logger.debug("Close invalid connection: %s", e)

        # Create new connection for this thread
        conn = self._create_connection(for_thread_local=True)
        _thread_local.connection = conn

        # Track for cleanup
        with self._thread_conn_lock:
            self._thread_connections[thread_id] = conn

        logger.debug(f"Created thread-local connection for thread {thread_id}")
        return conn

    def get_connection(self) -> sqlite3.Connection:
        """
        Get a connection from the pool.

        If use_thread_local=True (default), returns a thread-dedicated connection.
        Otherwise, uses the shared pool with check_same_thread=False (legacy).

        Returns:
            sqlite3.Connection ready for use

        Raises:
            TimeoutError: If no connection available within timeout
        """
        # Use thread-local connection (SAFE)
        if self.use_thread_local:
            self._checkouts += 1
            return self._get_thread_connection()

        # Legacy pool-based approach (less safe, for backward compatibility)
        try:
            conn = self._pool.get(timeout=self.timeout)

            # Validate connection is alive
            if not self._validate_connection(conn):
                logger.warning("Connection invalid, creating new one")
                try:
                    conn.close()
                except Exception as e:
                    logger.debug("Close invalid pool connection: %s", e)
                conn = self._create_connection(for_thread_local=False)

            self._checkouts += 1
            return conn

        except Empty:
            # Pool exhausted, try to create new connection
            logger.warning("Connection pool exhausted, creating new connection")
            return self._create_connection(for_thread_local=False)

    def return_connection(self, conn: sqlite3.Connection) -> None:
        """
        Return a connection to the pool.

        For thread-local connections: no-op (connection stays with thread).
        For pool connections: returns to pool or closes if full.

        Args:
            conn: Connection to return
        """
        if conn is None:
            return

        self._checkins += 1

        # Thread-local connections are NOT returned to pool
        # They stay with the thread for reuse
        if self.use_thread_local:
            return

        try:
            # Try to put back in pool
            self._pool.put_nowait(conn)
        except Exception:
            # Pool full, close connection
            logger.debug("Pool full, closing connection")
            try:
                conn.close()
            except Exception:
                pass

    @contextmanager
    def connection(self):
        """
        Context manager for connection usage.

        Automatically returns connection to pool on exit.

        Usage:
            with pool.connection() as conn:
                cursor = conn.execute("SELECT * FROM table")
                rows = cursor.fetchall()

        Yields:
            sqlite3.Connection
        """
        conn = self.get_connection()
        try:
            yield conn
        finally:
            self.return_connection(conn)

    @contextmanager
    def transaction(self):
        """
        Context manager for transaction with explicit commit/rollback.

        Usage:
            with pool.transaction() as conn:
                conn.execute("INSERT INTO table VALUES (?)", (value,))
                # Auto-commit on success, rollback on exception
        """
        conn = self.get_connection()
        try:
            conn.execute("BEGIN")
            yield conn
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            self.return_connection(conn)

    def close_all(self) -> None:
        """Close all connections in the pool and thread-local storage."""
        closed = 0

        # Close thread-local connections
        with self._thread_conn_lock:
            for thread_id, conn in list(self._thread_connections.items()):
                try:
                    conn.close()
                    closed += 1
                    logger.debug(
                        f"Closed thread-local connection for thread {thread_id}"
                    )
                except Exception as e:
                    logger.error(f"Error closing thread connection {thread_id}: {e}")
            self._thread_connections.clear()

        # Close pool connections
        with self._lock:
            while not self._pool.empty():
                try:
                    conn = self._pool.get_nowait()
                    conn.close()
                    closed += 1
                except Empty:
                    break
                except Exception as e:
                    logger.error(f"Error closing connection: {e}")

        self._initialized = False
        logger.info(f"Closed {closed} pool connections (including thread-local)")

    def get_stats(self) -> dict:
        """
        Get pool statistics.

        Returns:
            Dict with pool metrics
        """
        with self._thread_conn_lock:
            thread_conn_count = len(self._thread_connections)

        return {
            "pool_size": self.pool_size,
            "available": self._pool.qsize(),
            "in_use": self.pool_size - self._pool.qsize(),
            "thread_local_connections": thread_conn_count,
            "use_thread_local": self.use_thread_local,
            "total_created": self._created,
            "total_checkouts": self._checkouts,
            "total_checkins": self._checkins,
            "db_path": self.db_path,
            "initialized": self._initialized,
        }

    def __del__(self):
        """Cleanup on garbage collection."""
        try:
            self.close_all()
        except Exception:
            pass


# ============================================================================
# Global Pool Instance
# ============================================================================

_pool: Optional[SQLiteConnectionPool] = None
_pool_lock = threading.Lock()


def get_pool(
    db_path: Optional[str] = None,
    pool_size: int = 10,
) -> SQLiteConnectionPool:
    """
    Get or create the global connection pool.

    Thread-safe singleton pattern.

    Args:
        db_path: Path to database (only used on first call)
        pool_size: Pool size (only used on first call)

    Returns:
        SQLiteConnectionPool instance
    """
    global _pool

    if _pool is None:
        with _pool_lock:
            if _pool is None:
                # Default to data.sqlite3 in project root
                if db_path is None:
                    db_path = str(Path(__file__).parent.parent.parent / "data.sqlite3")

                _pool = SQLiteConnectionPool(db_path, pool_size)

    return _pool


def reset_pool() -> None:
    """
    Reset the global pool.

    Closes all connections and clears the singleton.
    Use when reconfiguring or shutting down.
    """
    global _pool

    with _pool_lock:
        if _pool is not None:
            _pool.close_all()
            _pool = None
            logger.info("Global SQLite pool reset")
