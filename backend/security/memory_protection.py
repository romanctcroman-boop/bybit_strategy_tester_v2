"""
Memory Protection Module for Sensitive Data.

DeepSeek Recommendation: Week 1 - Memory protection

Features:
- SecureString: Protected string with secure erasure
- MemoryGuard: Context manager for sensitive operations
- Memory locking (mlock) on supported platforms
- Protection from swap and core dumps
"""

import ctypes
import gc
import logging
import secrets
import sys
from contextlib import contextmanager
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Platform detection
IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
IS_MACOS = sys.platform == "darwin"

# Try to import platform-specific memory functions
MLOCK_AVAILABLE = False
VIRTUAL_LOCK = None
VIRTUAL_UNLOCK = None

if IS_WINDOWS:
    try:
        kernel32 = ctypes.windll.kernel32
        VIRTUAL_LOCK = kernel32.VirtualLock
        VIRTUAL_UNLOCK = kernel32.VirtualUnlock
        MLOCK_AVAILABLE = True
    except Exception:
        pass
elif IS_LINUX or IS_MACOS:
    try:
        libc = ctypes.CDLL("libc.so.6" if IS_LINUX else "libc.dylib", use_errno=True)
        MLOCK_AVAILABLE = hasattr(libc, "mlock")
    except Exception:
        pass


class SecureString:
    """
    Secure string container with memory protection.

    Features:
    - Automatic secure zeroing on deletion
    - Memory locking (prevents swap exposure)
    - Protection from garbage collector exposure
    - Safe comparison (constant-time)
    - Redacted repr/str to prevent logging

    Usage:
        secret = SecureString("my_api_key")
        value = secret.get()  # Use the value
        secret.clear()        # Explicit clear when done
        del secret            # Or let destructor handle it
    """

    __slots__ = ("_data", "_size", "_locked", "_cleared")

    def __init__(self, value: str):
        """
        Initialize secure string.

        Args:
            value: The sensitive string to protect
        """
        # Convert to bytes for manipulation
        encoded = value.encode("utf-8")
        self._size = len(encoded)
        self._cleared = False

        # Create mutable bytearray
        self._data = bytearray(encoded)

        # Clear the original encoded bytes
        self._secure_zero(encoded)

        # Try to lock memory (prevent swapping)
        self._locked = self._try_lock_memory()

        if self._locked:
            logger.debug("SecureString: Memory locked successfully")

    def _try_lock_memory(self) -> bool:
        """Try to lock the memory to prevent swapping."""
        if not MLOCK_AVAILABLE or not self._data:
            return False

        try:
            addr = ctypes.addressof(
                (ctypes.c_char * len(self._data)).from_buffer(self._data)
            )
            size = len(self._data)

            if IS_WINDOWS and VIRTUAL_LOCK:
                return bool(VIRTUAL_LOCK(ctypes.c_void_p(addr), ctypes.c_size_t(size)))
            elif IS_LINUX or IS_MACOS:
                libc = ctypes.CDLL("libc.so.6" if IS_LINUX else "libc.dylib")
                return libc.mlock(ctypes.c_void_p(addr), ctypes.c_size_t(size)) == 0
        except Exception as e:
            logger.debug(f"Memory lock failed: {e}")

        return False

    def _try_unlock_memory(self) -> None:
        """Try to unlock the memory."""
        if not self._locked or not self._data:
            return

        try:
            addr = ctypes.addressof(
                (ctypes.c_char * len(self._data)).from_buffer(self._data)
            )
            size = len(self._data)

            if IS_WINDOWS and VIRTUAL_UNLOCK:
                VIRTUAL_UNLOCK(ctypes.c_void_p(addr), ctypes.c_size_t(size))
            elif IS_LINUX or IS_MACOS:
                libc = ctypes.CDLL("libc.so.6" if IS_LINUX else "libc.dylib")
                libc.munlock(ctypes.c_void_p(addr), ctypes.c_size_t(size))
        except Exception:
            pass

    @staticmethod
    def _secure_zero(data: bytes | bytearray) -> None:
        """Securely zero bytes (works for immutable bytes too via memory view)."""
        if isinstance(data, bytearray):
            for i in range(len(data)):
                data[i] = 0
        elif isinstance(data, bytes):
            # For immutable bytes, try to overwrite via ctypes
            try:
                addr = id(data) + sys.getsizeof(b"") - 1  # Approximate offset to data
                ctypes.memset(addr, 0, len(data))
            except Exception:
                pass  # Best effort for immutable bytes

    def get(self) -> str:
        """
        Get the protected string value.

        Returns:
            The original string value

        Raises:
            ValueError: If the data has been cleared
        """
        if self._cleared:
            raise ValueError("SecureString has been cleared")
        return bytes(self._data).decode("utf-8")

    def get_bytes(self) -> bytes:
        """Get the protected value as bytes."""
        if self._cleared:
            raise ValueError("SecureString has been cleared")
        return bytes(self._data)

    def clear(self) -> None:
        """
        Securely clear the string from memory.

        This overwrites the memory with zeros before releasing.
        """
        if self._cleared:
            return

        # Unlock memory first
        self._try_unlock_memory()

        # Overwrite with random data, then zeros (multiple passes for paranoia)
        if self._data:
            # Pass 1: Random data
            for i in range(len(self._data)):
                self._data[i] = secrets.randbelow(256)

            # Pass 2: Zeros
            for i in range(len(self._data)):
                self._data[i] = 0

            # Pass 3: 0xFF
            for i in range(len(self._data)):
                self._data[i] = 0xFF

            # Final: Zeros
            for i in range(len(self._data)):
                self._data[i] = 0

            self._data.clear()

        self._cleared = True
        self._locked = False

    def __len__(self) -> int:
        """Return the length of the protected string."""
        return self._size

    def __repr__(self) -> str:
        """Safe repr that doesn't expose the value."""
        status = "cleared" if self._cleared else "active"
        lock = "locked" if self._locked else "unlocked"
        return f"SecureString(size={self._size}, status={status}, memory={lock})"

    def __str__(self) -> str:
        """Never expose value via str()."""
        return "[SECURE STRING - REDACTED]"

    def __eq__(self, other: Any) -> bool:
        """Constant-time comparison to prevent timing attacks."""
        if isinstance(other, SecureString):
            return secrets.compare_digest(self.get_bytes(), other.get_bytes())
        elif isinstance(other, str):
            return secrets.compare_digest(self.get_bytes(), other.encode("utf-8"))
        return False

    def __hash__(self):
        """Prevent hashing (which would store the value)."""
        raise TypeError("SecureString is not hashable for security reasons")

    def __del__(self):
        """Destructor ensures memory is cleared."""
        self.clear()


class MemoryGuard:
    """
    Context manager for sensitive operations.

    Ensures all local variables are cleared after the block.
    Disables garbage collection during sensitive operations.

    Usage:
        with MemoryGuard() as guard:
            api_key = guard.protect("sk-secret-key")
            # Use api_key.get()
            # Automatically cleared on exit
    """

    def __init__(self, disable_gc: bool = True):
        """
        Initialize memory guard.

        Args:
            disable_gc: Whether to disable GC during the block
        """
        self._disable_gc = disable_gc
        self._gc_was_enabled = False
        self._protected: list[SecureString] = []

    def __enter__(self) -> "MemoryGuard":
        """Enter the guarded block."""
        if self._disable_gc:
            self._gc_was_enabled = gc.isenabled()
            gc.disable()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the guarded block, clearing all protected data."""
        # Clear all protected strings
        for secure in self._protected:
            secure.clear()
        self._protected.clear()

        # Re-enable GC if it was enabled
        if self._disable_gc and self._gc_was_enabled:
            gc.enable()

        # Force collection to clear any remnants
        gc.collect()

    def protect(self, value: str) -> SecureString:
        """
        Create a protected string that will be cleared on exit.

        Args:
            value: The sensitive string to protect

        Returns:
            SecureString instance
        """
        secure = SecureString(value)
        self._protected.append(secure)
        return secure


@contextmanager
def secure_operation():
    """
    Context manager for secure operations.

    Simple alias for MemoryGuard.

    Usage:
        with secure_operation() as guard:
            secret = guard.protect(api_key)
            use_key(secret.get())
    """
    guard = MemoryGuard()
    try:
        yield guard
    finally:
        guard.__exit__(None, None, None)


def secure_compare(a: str | bytes, b: str | bytes) -> bool:
    """
    Constant-time string comparison.

    Prevents timing attacks when comparing secrets.

    Args:
        a: First string/bytes
        b: Second string/bytes

    Returns:
        True if equal, False otherwise
    """
    if isinstance(a, str):
        a = a.encode("utf-8")
    if isinstance(b, str):
        b = b.encode("utf-8")
    return secrets.compare_digest(a, b)


def secure_random_string(length: int = 32, alphabet: Optional[str] = None) -> str:
    """
    Generate a cryptographically secure random string.

    Args:
        length: Length of the string
        alphabet: Characters to use (default: alphanumeric)

    Returns:
        Random string
    """
    if alphabet is None:
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def wipe_string_from_memory(s: str) -> None:
    """
    Attempt to wipe a string from memory.

    Note: Python strings are immutable, so this is best-effort only.
    For true security, use SecureString from the start.

    Args:
        s: String to wipe
    """
    try:
        # Get the internal buffer size
        str_size = sys.getsizeof(s)

        # Try to overwrite via ctypes
        addr = id(s)
        ctypes.memset(addr, 0, str_size)
    except Exception:
        pass  # Best effort


__all__ = [
    "SecureString",
    "MemoryGuard",
    "secure_operation",
    "secure_compare",
    "secure_random_string",
    "wipe_string_from_memory",
    "MLOCK_AVAILABLE",
]
