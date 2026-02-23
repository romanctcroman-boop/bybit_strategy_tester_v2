"""
Shamir's Secret Sharing Implementation.

DeepSeek Recommendation: Quarter 1 - Key sharding

Features:
- Split master key into N shares
- Require K shares to reconstruct (threshold scheme)
- Information-theoretic security
- GF(256) arithmetic for byte-level operations
- Compatible with standard Shamir implementations

Use cases:
- Distributed key custody (no single point of failure)
- Multi-party authorization for critical operations
- Disaster recovery with geographically distributed shares
- Compliance with separation of duties requirements
"""

import secrets
from dataclasses import dataclass


class GF256:
    """
    GF(2^8) Galois Field arithmetic.

    Uses the irreducible polynomial x^8 + x^4 + x^3 + x + 1 (0x11B).
    This is the same polynomial used in AES.
    """

    # Pre-compute exp and log tables
    _exp = [0] * 512
    _log = [0] * 256
    _initialized = False

    @classmethod
    def _init(cls):
        """Initialize lookup tables."""
        if cls._initialized:
            return

        x = 1
        for i in range(255):
            cls._exp[i] = x
            cls._exp[i + 255] = x  # Duplicate for easy modular access
            cls._log[x] = i

            # Multiply by the generator (3)
            x = (x << 1) ^ x
            if x >= 256:
                x ^= 0x11B  # Reduce by irreducible polynomial

        cls._log[0] = 0  # Undefined, but set to avoid issues
        cls._initialized = True

    @classmethod
    def add(cls, a: int, b: int) -> int:
        """Addition in GF(256) is XOR."""
        return a ^ b

    @classmethod
    def mul(cls, a: int, b: int) -> int:
        """Multiplication in GF(256)."""
        if not cls._initialized:
            cls._init()
        if a == 0 or b == 0:
            return 0
        return cls._exp[cls._log[a] + cls._log[b]]

    @classmethod
    def div(cls, a: int, b: int) -> int:
        """Division in GF(256)."""
        if not cls._initialized:
            cls._init()
        if b == 0:
            raise ZeroDivisionError("Division by zero in GF(256)")
        if a == 0:
            return 0
        return cls._exp[cls._log[a] + 255 - cls._log[b]]

    @classmethod
    def pow(cls, a: int, n: int) -> int:
        """Exponentiation in GF(256)."""
        if not cls._initialized:
            cls._init()
        if a == 0:
            return 0 if n > 0 else 1
        return cls._exp[(cls._log[a] * n) % 255]


# Initialize the field on module load
GF256._init()


def _eval_poly(coeffs: list[int], x: int) -> int:
    """
    Evaluate polynomial at x in GF(256).

    Args:
        coeffs: Coefficients [a0, a1, a2, ...] where p(x) = a0 + a1*x + a2*x^2 + ...
        x: Point to evaluate at

    Returns:
        p(x) in GF(256)
    """
    # Horner's method for efficiency
    result = 0
    for coeff in reversed(coeffs):
        result = GF256.add(GF256.mul(result, x), coeff)
    return result


def _interpolate(points: list[tuple[int, int]], x: int) -> int:
    """
    Lagrange interpolation at point x in GF(256).

    Args:
        points: List of (x_i, y_i) points
        x: Point to interpolate at

    Returns:
        Interpolated value at x
    """
    result = 0
    n = len(points)

    for i in range(n):
        xi, yi = points[i]

        # Calculate Lagrange basis polynomial L_i(x)
        num = 1
        denom = 1

        for j in range(n):
            if i != j:
                xj = points[j][0]
                num = GF256.mul(num, GF256.add(x, xj))
                denom = GF256.mul(denom, GF256.add(xi, xj))

        # L_i(x) = num / denom
        lagrange = GF256.div(num, denom)

        # Add y_i * L_i(x) to result
        result = GF256.add(result, GF256.mul(yi, lagrange))

    return result


@dataclass
class SecretShare:
    """A single share of a split secret."""

    index: int  # Share index (1-based, 0 is reserved for secret)
    data: bytes  # Share data (same length as original secret)
    threshold: int  # Minimum shares needed to reconstruct
    total_shares: int  # Total number of shares created

    def to_hex(self) -> str:
        """Convert to hex string for storage."""
        return f"{self.index:02x}{self.threshold:02x}{self.total_shares:02x}{self.data.hex()}"

    @classmethod
    def from_hex(cls, hex_string: str) -> "SecretShare":
        """Parse from hex string."""
        index = int(hex_string[:2], 16)
        threshold = int(hex_string[2:4], 16)
        total_shares = int(hex_string[4:6], 16)
        data = bytes.fromhex(hex_string[6:])
        return cls(
            index=index, data=data, threshold=threshold, total_shares=total_shares
        )

    def __repr__(self) -> str:
        return f"SecretShare(index={self.index}, threshold={self.threshold}/{self.total_shares}, size={len(self.data)})"


class ShamirSecretSharing:
    """
    Shamir's Secret Sharing implementation.

    Provides (k, n) threshold scheme where:
    - n = total number of shares
    - k = minimum shares required to reconstruct

    Any k shares can reconstruct the secret, but k-1 shares reveal nothing.

    Example:
        sss = ShamirSecretSharing()

        # Split a key into 5 shares, require 3 to reconstruct
        secret = b"my_super_secret_key_32_bytes!!"
        shares = sss.split(secret, threshold=3, num_shares=5)

        # Distribute shares to different custodians
        # ...

        # Later, reconstruct with any 3 shares
        recovered = sss.combine([shares[0], shares[2], shares[4]])
        assert recovered == secret
    """

    def __init__(self):
        """Initialize Shamir's Secret Sharing."""
        pass

    def split(
        self, secret: bytes, threshold: int, num_shares: int
    ) -> list[SecretShare]:
        """
        Split a secret into shares using Shamir's scheme.

        Args:
            secret: The secret bytes to split
            threshold: Minimum shares required (k)
            num_shares: Total shares to create (n)

        Returns:
            List of SecretShare objects

        Raises:
            ValueError: If parameters are invalid
        """
        if threshold < 2:
            raise ValueError("Threshold must be at least 2")
        if num_shares < threshold:
            raise ValueError("Number of shares must be >= threshold")
        if num_shares > 255:
            raise ValueError("Maximum 255 shares supported")
        if not secret:
            raise ValueError("Secret cannot be empty")

        shares_data: list[bytearray] = [bytearray() for _ in range(num_shares)]

        # Process each byte of the secret
        for byte in secret:
            # Generate random polynomial with secret as constant term
            # p(x) = secret + a1*x + a2*x^2 + ... + a_{k-1}*x^{k-1}
            coeffs = [byte]  # a0 = secret byte
            for _ in range(threshold - 1):
                coeffs.append(secrets.randbelow(256))

            # Evaluate polynomial at x = 1, 2, 3, ..., n
            for i in range(num_shares):
                x = i + 1  # Use 1-based indices (0 is the secret)
                y = _eval_poly(coeffs, x)
                shares_data[i].append(y)

        # Create share objects
        return [
            SecretShare(
                index=i + 1,
                data=bytes(shares_data[i]),
                threshold=threshold,
                total_shares=num_shares,
            )
            for i in range(num_shares)
        ]

    def combine(self, shares: list[SecretShare]) -> bytes:
        """
        Reconstruct the secret from shares.

        Args:
            shares: List of SecretShare objects (at least threshold shares)

        Returns:
            The reconstructed secret bytes

        Raises:
            ValueError: If not enough shares or shares are inconsistent
        """
        if not shares:
            raise ValueError("No shares provided")

        threshold = shares[0].threshold
        secret_length = len(shares[0].data)

        # Validate shares
        if len(shares) < threshold:
            raise ValueError(f"Need at least {threshold} shares, got {len(shares)}")

        for share in shares:
            if share.threshold != threshold:
                raise ValueError("Shares have inconsistent threshold values")
            if len(share.data) != secret_length:
                raise ValueError("Shares have inconsistent lengths")

        # Check for duplicate indices
        indices = [s.index for s in shares]
        if len(set(indices)) != len(indices):
            raise ValueError("Duplicate share indices detected")

        # Use exactly threshold shares (first k)
        used_shares = shares[:threshold]

        # Reconstruct each byte
        result = bytearray()
        for byte_idx in range(secret_length):
            # Collect (x, y) points for this byte
            points = [(s.index, s.data[byte_idx]) for s in used_shares]

            # Interpolate at x = 0 to get the secret byte
            secret_byte = _interpolate(points, 0)
            result.append(secret_byte)

        return bytes(result)

    def verify_share(self, share: SecretShare, other_shares: list[SecretShare]) -> bool:
        """
        Verify a share is consistent with others.

        Uses extra shares to check if this share lies on the same polynomial.

        Args:
            share: Share to verify
            other_shares: Other shares to check against

        Returns:
            True if share is valid, False if it appears corrupted/fake
        """
        if len(other_shares) < share.threshold:
            raise ValueError(f"Need at least {share.threshold} other shares to verify")

        # Reconstruct with the share and check consistency
        try:
            test_shares = [share, *other_shares[:share.threshold - 1]]
            secret1 = self.combine(test_shares)

            # Reconstruct without this share
            secret2 = self.combine(other_shares[: share.threshold])

            return secret1 == secret2
        except Exception:
            return False

    @staticmethod
    def generate_random_secret(length: int = 32) -> bytes:
        """Generate a cryptographically random secret."""
        return secrets.token_bytes(length)


def split_key(key: bytes, threshold: int = 3, num_shares: int = 5) -> list[str]:
    """
    Convenience function to split a key.

    Args:
        key: The key bytes to split
        threshold: Minimum shares to reconstruct (default 3)
        num_shares: Total shares to create (default 5)

    Returns:
        List of hex-encoded share strings
    """
    sss = ShamirSecretSharing()
    shares = sss.split(key, threshold, num_shares)
    return [s.to_hex() for s in shares]


def combine_key(share_strings: list[str]) -> bytes:
    """
    Convenience function to combine shares.

    Args:
        share_strings: List of hex-encoded share strings

    Returns:
        The reconstructed key bytes
    """
    sss = ShamirSecretSharing()
    shares = [SecretShare.from_hex(s) for s in share_strings]
    return sss.combine(shares)


__all__ = [
    "GF256",
    "SecretShare",
    "ShamirSecretSharing",
    "combine_key",
    "split_key",
]
