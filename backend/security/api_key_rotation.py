"""
API Key Rotation Manager
=========================
Автоматическая ротация API ключей каждые 90 дней
с audit logging и уведомлениями
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class APIKeyRotationManager:
    """
    Управление ротацией API ключей

    Features:
    - Отслеживание возраста ключей
    - Автоматическое уведомление о необходимости ротации
    - Audit logging всех операций с ключами
    - Безопасное хранение метаданных
    """

    def __init__(self, metadata_file: Path, rotation_days: int = 90):
        """
        Initialize rotation manager

        Args:
            metadata_file: Path to metadata JSON file
            rotation_days: Days before key rotation required
        """
        self.metadata_file = metadata_file
        self.rotation_days = rotation_days
        self.metadata = self._load_metadata()

        logger.info(
            f"API Key Rotation Manager initialized (rotation_days={rotation_days})"
        )

    def _load_metadata(self) -> dict:
        """Load key metadata from file"""
        if not self.metadata_file.exists():
            return {"keys": {}, "audit_log": []}

        try:
            with open(self.metadata_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
            return {"keys": {}, "audit_log": []}

    def _save_metadata(self):
        """Save metadata to file"""
        try:
            # Ensure directory exists
            self.metadata_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, indent=2, default=str)

            # Set restrictive permissions
            os.chmod(self.metadata_file, 0o600)

        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")

    def _add_audit_log(self, action: str, key_id: str, details: dict = None):
        """Add entry to audit log"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "key_id": key_id,
            "details": details or {},
        }

        if "audit_log" not in self.metadata:
            self.metadata["audit_log"] = []

        self.metadata["audit_log"].append(entry)

        # Keep only last 1000 entries
        if len(self.metadata["audit_log"]) > 1000:
            self.metadata["audit_log"] = self.metadata["audit_log"][-1000:]

        self._save_metadata()

        logger.info(f"Audit log: {action} for key {key_id}", extra={"audit": entry})

    def register_key(self, key_id: str, key_name: str, service: str):
        """
        Register new API key

        Args:
            key_id: Unique key identifier (hash)
            key_name: Friendly name
            service: Service name (e.g., 'deepseek', 'perplexity')
        """
        key_hash = hashlib.sha256(key_id.encode()).hexdigest()[:16]

        self.metadata["keys"][key_hash] = {
            "name": key_name,
            "service": service,
            "created_at": datetime.now().isoformat(),
            "last_rotated": datetime.now().isoformat(),
            "rotation_count": 0,
            "usage_count": 0,
            "last_used": None,
        }

        self._add_audit_log(
            "register", key_hash, {"service": service, "name": key_name}
        )

        logger.info(f"Registered API key: {key_name} ({service})")

    def record_usage(self, key_id: str):
        """Record key usage"""
        key_hash = hashlib.sha256(key_id.encode()).hexdigest()[:16]

        if key_hash in self.metadata["keys"]:
            self.metadata["keys"][key_hash]["usage_count"] += 1
            self.metadata["keys"][key_hash]["last_used"] = datetime.now().isoformat()
            self._save_metadata()

    def record_rotation(self, key_id: str):
        """
        Record key rotation

        Args:
            key_id: Key identifier
        """
        key_hash = hashlib.sha256(key_id.encode()).hexdigest()[:16]

        if key_hash in self.metadata["keys"]:
            self.metadata["keys"][key_hash]["last_rotated"] = datetime.now().isoformat()
            self.metadata["keys"][key_hash]["rotation_count"] += 1

            self._add_audit_log(
                "rotate",
                key_hash,
                {"rotation_count": self.metadata["keys"][key_hash]["rotation_count"]},
            )

            logger.info(f"Recorded rotation for key {key_hash}")

    def check_rotation_needed(self) -> list[dict]:
        """
        Check which keys need rotation

        Returns:
            List of keys requiring rotation
        """
        now = datetime.now()
        needs_rotation = []

        for key_hash, info in self.metadata["keys"].items():
            last_rotated = datetime.fromisoformat(info["last_rotated"])
            days_since_rotation = (now - last_rotated).days

            if days_since_rotation >= self.rotation_days:
                needs_rotation.append(
                    {
                        "key_hash": key_hash,
                        "name": info["name"],
                        "service": info["service"],
                        "days_old": days_since_rotation,
                        "last_rotated": info["last_rotated"],
                    }
                )

        return needs_rotation

    def get_expiring_soon(self, days_threshold: int = 7) -> list[dict]:
        """
        Get keys expiring within threshold

        Args:
            days_threshold: Days before expiration to warn

        Returns:
            List of keys expiring soon
        """
        now = datetime.now()
        expiring = []

        for key_hash, info in self.metadata["keys"].items():
            last_rotated = datetime.fromisoformat(info["last_rotated"])
            days_until_expiry = self.rotation_days - (now - last_rotated).days

            if 0 < days_until_expiry <= days_threshold:
                expiring.append(
                    {
                        "key_hash": key_hash,
                        "name": info["name"],
                        "service": info["service"],
                        "days_until_expiry": days_until_expiry,
                        "expiry_date": (
                            last_rotated + timedelta(days=self.rotation_days)
                        ).isoformat(),
                    }
                )

        return expiring

    def get_statistics(self) -> dict:
        """Get rotation statistics"""
        total_keys = len(self.metadata["keys"])
        needs_rotation = len(self.check_rotation_needed())
        expiring_soon = len(self.get_expiring_soon())

        total_usage = sum(
            info["usage_count"] for info in self.metadata["keys"].values()
        )
        total_rotations = sum(
            info["rotation_count"] for info in self.metadata["keys"].values()
        )

        return {
            "total_keys": total_keys,
            "needs_rotation": needs_rotation,
            "expiring_soon": expiring_soon,
            "total_usage": total_usage,
            "total_rotations": total_rotations,
            "audit_log_entries": len(self.metadata.get("audit_log", [])),
        }

    def generate_rotation_report(self) -> str:
        """Generate markdown report"""
        needs_rotation = self.check_rotation_needed()
        expiring = self.get_expiring_soon()
        stats = self.get_statistics()

        report = [
            "# API Key Rotation Report",
            f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "\n## Statistics\n",
            f"- Total Keys: {stats['total_keys']}",
            f"- Needs Rotation: {stats['needs_rotation']}",
            f"- Expiring Soon (7 days): {stats['expiring_soon']}",
            f"- Total Usage: {stats['total_usage']}",
            f"- Total Rotations: {stats['total_rotations']}",
        ]

        if needs_rotation:
            report.append("\n## ⚠️  Keys Requiring Immediate Rotation\n")
            for key in needs_rotation:
                report.append(
                    f"- **{key['name']}** ({key['service']}) - "
                    f"{key['days_old']} days old"
                )

        if expiring:
            report.append("\n## 🔔 Keys Expiring Soon\n")
            for key in expiring:
                report.append(
                    f"- **{key['name']}** ({key['service']}) - "
                    f"expires in {key['days_until_expiry']} days"
                )

        if not needs_rotation and not expiring:
            report.append("\n## ✅ All Keys Up to Date\n")
            report.append("No keys require rotation at this time.")

        return "\n".join(report)


# Global instance
_rotation_manager: APIKeyRotationManager | None = None


def get_rotation_manager() -> APIKeyRotationManager:
    """Get global rotation manager instance"""
    global _rotation_manager

    if _rotation_manager is None:
        metadata_file = (
            Path(__file__).parent.parent.parent / "config" / "api_key_metadata.json"
        )
        _rotation_manager = APIKeyRotationManager(metadata_file)

    return _rotation_manager


# CLI для проверки статуса
if __name__ == "__main__":
    import sys

    manager = get_rotation_manager()

    if len(sys.argv) > 1 and sys.argv[1] == "report":
        print(manager.generate_rotation_report())
    else:
        stats = manager.get_statistics()
        print("API Key Statistics:")
        print(f"  Total Keys: {stats['total_keys']}")
        print(f"  Needs Rotation: {stats['needs_rotation']}")
        print(f"  Expiring Soon: {stats['expiring_soon']}")

        if stats["needs_rotation"] > 0:
            print("\n⚠️  WARNING: Some keys need rotation!")
            print("Run: python -m backend.security.api_key_rotation report")
