"""
⛓️ Blockchain-Verified Backtests

Hash-based verification of backtest results.

@version: 1.0.0
@date: 2026-02-26
"""

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BacktestProof:
    """Cryptographic proof of backtest"""

    backtest_id: str
    timestamp: str
    strategy_hash: str
    data_hash: str
    results_hash: str
    signature: str
    verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BacktestProof":
        return cls(**data)


class BacktestVerifier:
    """
    Blockchain-style backtest verification.

    Creates cryptographic proofs for backtest results.
    """

    def __init__(self):
        self.proofs: dict[str, BacktestProof] = {}
        self.chain: list[BacktestProof] = []

    def hash_data(self, data: Any) -> str:
        """
        Create SHA-256 hash of data.

        Args:
            data: Data to hash

        Returns:
            Hex hash string
        """
        if isinstance(data, dict):
            data_str = json.dumps(data, sort_keys=True)
        elif isinstance(data, str):
            data_str = data
        else:
            data_str = json.dumps(data, sort_keys=True, default=str)

        return hashlib.sha256(data_str.encode()).hexdigest()

    def create_proof(
        self, backtest_id: str, strategy_config: dict[str, Any], data_config: dict[str, Any], results: dict[str, Any]
    ) -> BacktestProof:
        """
        Create cryptographic proof for backtest.

        Args:
            backtest_id: Unique backtest identifier
            strategy_config: Strategy configuration
            data_config: Data configuration
            results: Backtest results

        Returns:
            BacktestProof
        """
        timestamp = datetime.now().isoformat()

        # Hash components
        strategy_hash = self.hash_data(strategy_config)
        data_hash = self.hash_data(data_config)
        results_hash = self.hash_data(results)

        # Create combined hash
        combined = f"{backtest_id}:{timestamp}:{strategy_hash}:{data_hash}:{results_hash}"
        signature = self.hash_data(combined)

        proof = BacktestProof(
            backtest_id=backtest_id,
            timestamp=timestamp,
            strategy_hash=strategy_hash,
            data_hash=data_hash,
            results_hash=results_hash,
            signature=signature,
            verified=True,
        )

        # Add to chain
        self.proofs[backtest_id] = proof
        self.chain.append(proof)

        logger.info(f"Created proof for backtest {backtest_id}")

        return proof

    def verify_proof(self, proof: BacktestProof) -> bool:
        """
        Verify cryptographic proof.

        Args:
            proof: Proof to verify

        Returns:
            True if valid
        """
        # Recreate signature
        combined = f"{proof.backtest_id}:{proof.timestamp}:{proof.strategy_hash}:{proof.data_hash}:{proof.results_hash}"
        expected_signature = self.hash_data(combined)

        # Verify
        is_valid = proof.signature == expected_signature

        proof.verified = is_valid

        logger.info(f"Verified proof for {proof.backtest_id}: {is_valid}")

        return is_valid

    def verify_chain(self) -> bool:
        """
        Verify entire proof chain.

        Returns:
            True if all proofs valid
        """
        all_valid = True

        for proof in self.chain:
            if not self.verify_proof(proof):
                all_valid = False
                logger.warning(f"Invalid proof: {proof.backtest_id}")

        return all_valid

    def get_proof(self, backtest_id: str) -> BacktestProof | None:
        """Get proof by backtest ID"""
        return self.proofs.get(backtest_id)

    def export_proof(self, backtest_id: str) -> dict[str, Any] | None:
        """Export proof as dictionary"""
        proof = self.get_proof(backtest_id)
        if proof:
            return proof.to_dict()
        return None

    def import_proof(self, proof_dict: dict[str, Any]) -> BacktestProof:
        """Import proof from dictionary"""
        proof = BacktestProof.from_dict(proof_dict)
        self.proofs[proof.backtest_id] = proof
        return proof

    def get_chain_summary(self) -> dict[str, Any]:
        """Get chain summary"""
        return {
            "total_proofs": len(self.chain),
            "verified_proofs": sum(1 for p in self.chain if p.verified),
            "first_backtest": self.chain[0].backtest_id if self.chain else None,
            "last_backtest": self.chain[-1].backtest_id if self.chain else None,
        }
