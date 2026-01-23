"""
IP Whitelisting Service.

AI Agent Security Recommendation - Phase 4 Implementation:
- Restrict trading operations by IP address
- Support for CIDR ranges
- Temporary IP allowlisting
- Geographic restrictions (optional)
- Request rate limiting by IP
- Audit logging for blocked requests
"""

import ipaddress
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class IPStatus(str, Enum):
    """Status of an IP address."""

    ALLOWED = "allowed"
    BLOCKED = "blocked"
    RATE_LIMITED = "rate_limited"
    TEMPORARY = "temporary"
    UNKNOWN = "unknown"


class ActionType(str, Enum):
    """Types of actions that can be restricted."""

    TRADING = "trading"
    API_ACCESS = "api_access"
    ADMIN = "admin"
    DATA_EXPORT = "data_export"
    KEY_MANAGEMENT = "key_management"
    ALL = "all"


class BlockReason(str, Enum):
    """Reasons for blocking an IP."""

    MANUAL = "manual"
    RATE_LIMIT = "rate_limit"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    FAILED_AUTH = "failed_auth"
    GEO_BLOCKED = "geo_blocked"
    NOT_WHITELISTED = "not_whitelisted"


@dataclass
class IPRule:
    """IP whitelist/blacklist rule."""

    rule_id: str
    ip_pattern: str  # Single IP, CIDR, or pattern
    is_whitelist: bool = True
    action_types: list[ActionType] = field(default_factory=lambda: [ActionType.ALL])
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    created_by: Optional[str] = None
    is_enabled: bool = True


@dataclass
class BlockedRequest:
    """Record of a blocked request."""

    request_id: str
    timestamp: datetime
    ip_address: str
    reason: BlockReason
    action_type: ActionType
    request_path: Optional[str] = None
    user_agent: Optional[str] = None
    details: dict = field(default_factory=dict)


@dataclass
class IPStats:
    """Statistics for an IP address."""

    ip_address: str
    total_requests: int = 0
    allowed_requests: int = 0
    blocked_requests: int = 0
    last_seen: Optional[datetime] = None
    first_seen: Optional[datetime] = None
    status: IPStatus = IPStatus.UNKNOWN


@dataclass
class WhitelistConfig:
    """Configuration for IP whitelisting."""

    enabled: bool = True
    default_action: str = "deny"  # "allow" or "deny" for unknown IPs
    enable_rate_limiting: bool = True
    rate_limit_requests: int = 100  # per minute
    rate_limit_window_seconds: int = 60
    auto_block_threshold: int = 10  # failed attempts before auto-block
    auto_block_duration_minutes: int = 30
    log_blocked_requests: bool = True


class IPWhitelistService:
    """
    IP Whitelisting Service.

    Controls access to trading and sensitive operations by IP address.
    """

    _instance: Optional["IPWhitelistService"] = None

    def __init__(self, config: Optional[WhitelistConfig] = None):
        self.config = config or WhitelistConfig()
        self._rules: dict[str, IPRule] = {}
        self._blocked_requests: list[BlockedRequest] = []
        self._ip_stats: dict[str, IPStats] = {}
        self._rate_limit_counters: dict[str, list[datetime]] = defaultdict(list)
        self._auto_blocked: dict[str, datetime] = {}
        self._failed_attempts: dict[str, int] = defaultdict(int)
        self._rule_count = 0
        self._request_count = 0

        # Add localhost by default
        self._add_default_rules()

    @classmethod
    def get_instance(cls) -> "IPWhitelistService":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _add_default_rules(self) -> None:
        """Add default whitelist rules."""
        default_rules = [
            IPRule(
                rule_id="localhost-v4",
                ip_pattern="127.0.0.1",
                is_whitelist=True,
                description="IPv4 localhost",
            ),
            IPRule(
                rule_id="localhost-v6",
                ip_pattern="::1",
                is_whitelist=True,
                description="IPv6 localhost",
            ),
            IPRule(
                rule_id="private-10",
                ip_pattern="10.0.0.0/8",
                is_whitelist=True,
                description="Private network (10.x.x.x)",
            ),
            IPRule(
                rule_id="private-172",
                ip_pattern="172.16.0.0/12",
                is_whitelist=True,
                description="Private network (172.16-31.x.x)",
            ),
            IPRule(
                rule_id="private-192",
                ip_pattern="192.168.0.0/16",
                is_whitelist=True,
                description="Private network (192.168.x.x)",
            ),
        ]

        for rule in default_rules:
            self._rules[rule.rule_id] = rule

    def add_rule(
        self,
        ip_pattern: str,
        is_whitelist: bool = True,
        action_types: Optional[list[ActionType]] = None,
        description: str = "",
        expires_at: Optional[datetime] = None,
        created_by: Optional[str] = None,
    ) -> IPRule:
        """Add an IP rule."""
        # Validate IP pattern
        if not self._is_valid_ip_pattern(ip_pattern):
            raise ValueError(f"Invalid IP pattern: {ip_pattern}")

        self._rule_count += 1
        rule_id = f"rule-{self._rule_count}"

        rule = IPRule(
            rule_id=rule_id,
            ip_pattern=ip_pattern,
            is_whitelist=is_whitelist,
            action_types=action_types or [ActionType.ALL],
            description=description,
            expires_at=expires_at,
            created_by=created_by,
        )

        self._rules[rule_id] = rule
        logger.info(
            f"Added {'whitelist' if is_whitelist else 'blacklist'} rule: "
            f"{ip_pattern} ({rule_id})"
        )

        return rule

    def remove_rule(self, rule_id: str) -> bool:
        """Remove an IP rule."""
        if rule_id in self._rules:
            del self._rules[rule_id]
            logger.info(f"Removed rule: {rule_id}")
            return True
        return False

    def enable_rule(self, rule_id: str) -> bool:
        """Enable a rule."""
        if rule_id in self._rules:
            self._rules[rule_id].is_enabled = True
            return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        """Disable a rule."""
        if rule_id in self._rules:
            self._rules[rule_id].is_enabled = False
            return True
        return False

    def _is_valid_ip_pattern(self, pattern: str) -> bool:
        """Validate an IP pattern."""
        try:
            # Try as single IP
            ipaddress.ip_address(pattern)
            return True
        except ValueError:
            pass

        try:
            # Try as CIDR
            ipaddress.ip_network(pattern, strict=False)
            return True
        except ValueError:
            pass

        return False

    def _ip_matches_pattern(self, ip: str, pattern: str) -> bool:
        """Check if an IP matches a pattern."""
        try:
            ip_obj = ipaddress.ip_address(ip)

            # Try exact match
            try:
                pattern_ip = ipaddress.ip_address(pattern)
                return ip_obj == pattern_ip
            except ValueError:
                pass

            # Try CIDR match
            try:
                network = ipaddress.ip_network(pattern, strict=False)
                return ip_obj in network
            except ValueError:
                pass

        except ValueError:
            pass

        return False

    def check_ip(
        self,
        ip_address: str,
        action_type: ActionType = ActionType.ALL,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if an IP is allowed for an action.

        Returns: (is_allowed, reason)
        """
        now = datetime.now()

        # Update stats
        self._update_stats(ip_address)

        # Check auto-blocked
        if ip_address in self._auto_blocked:
            block_until = self._auto_blocked[ip_address]
            if now < block_until:
                return False, f"Auto-blocked until {block_until.isoformat()}"
            else:
                del self._auto_blocked[ip_address]
                self._failed_attempts[ip_address] = 0

        # Check rate limiting
        if self.config.enable_rate_limiting:
            is_rate_limited, reason = self._check_rate_limit(ip_address)
            if is_rate_limited:
                return False, reason

        # Check explicit rules
        whitelist_match = False

        for rule in self._rules.values():
            if not rule.is_enabled:
                continue

            # Check expiration
            if rule.expires_at and now > rule.expires_at:
                continue

            # Check if action type matches
            if (
                ActionType.ALL not in rule.action_types
                and action_type not in rule.action_types
            ):
                continue

            # Check IP match
            if self._ip_matches_pattern(ip_address, rule.ip_pattern):
                if rule.is_whitelist:
                    whitelist_match = True
                else:
                    # Blacklist match - immediately deny
                    return False, f"Blacklisted by rule: {rule.rule_id}"

        if whitelist_match:
            return True, None

        # Default action for unknown IPs
        if self.config.default_action == "allow":
            return True, None
        else:
            return False, "Not in whitelist"

    def _check_rate_limit(self, ip_address: str) -> tuple[bool, Optional[str]]:
        """Check rate limit for an IP."""
        now = datetime.now()
        window_start = now - timedelta(seconds=self.config.rate_limit_window_seconds)

        # Clean old entries
        self._rate_limit_counters[ip_address] = [
            t for t in self._rate_limit_counters[ip_address] if t > window_start
        ]

        # Check count
        request_count = len(self._rate_limit_counters[ip_address])
        if request_count >= self.config.rate_limit_requests:
            return (
                True,
                f"Rate limit exceeded: {request_count} requests in {self.config.rate_limit_window_seconds}s",
            )

        # Record this request
        self._rate_limit_counters[ip_address].append(now)

        return False, None

    def _update_stats(self, ip_address: str) -> None:
        """Update statistics for an IP."""
        now = datetime.now()

        if ip_address not in self._ip_stats:
            self._ip_stats[ip_address] = IPStats(
                ip_address=ip_address,
                first_seen=now,
            )

        stats = self._ip_stats[ip_address]
        stats.total_requests += 1
        stats.last_seen = now

    def record_blocked(
        self,
        ip_address: str,
        reason: BlockReason,
        action_type: ActionType,
        request_path: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> BlockedRequest:
        """Record a blocked request."""
        self._request_count += 1
        request_id = f"blocked-{self._request_count}"

        record = BlockedRequest(
            request_id=request_id,
            timestamp=datetime.now(),
            ip_address=ip_address,
            reason=reason,
            action_type=action_type,
            request_path=request_path,
            user_agent=user_agent,
            details=details or {},
        )

        self._blocked_requests.append(record)

        # Update stats
        if ip_address in self._ip_stats:
            self._ip_stats[ip_address].blocked_requests += 1

        # Keep only recent blocked requests
        if len(self._blocked_requests) > 10000:
            self._blocked_requests = self._blocked_requests[-10000:]

        logger.warning(f"Blocked request from {ip_address}: {reason.value}")

        return record

    def record_allowed(self, ip_address: str) -> None:
        """Record an allowed request."""
        if ip_address in self._ip_stats:
            self._ip_stats[ip_address].allowed_requests += 1

    def record_failed_auth(self, ip_address: str) -> None:
        """Record a failed authentication attempt."""
        self._failed_attempts[ip_address] += 1

        if self._failed_attempts[ip_address] >= self.config.auto_block_threshold:
            # Auto-block
            block_until = datetime.now() + timedelta(
                minutes=self.config.auto_block_duration_minutes
            )
            self._auto_blocked[ip_address] = block_until
            logger.warning(
                f"Auto-blocked {ip_address} until {block_until.isoformat()} "
                f"after {self._failed_attempts[ip_address]} failed attempts"
            )

    def unblock_ip(self, ip_address: str) -> bool:
        """Manually unblock an IP."""
        if ip_address in self._auto_blocked:
            del self._auto_blocked[ip_address]
            self._failed_attempts[ip_address] = 0
            logger.info(f"Unblocked IP: {ip_address}")
            return True
        return False

    def get_rules(
        self,
        is_whitelist: Optional[bool] = None,
        action_type: Optional[ActionType] = None,
        enabled_only: bool = False,
    ) -> list[IPRule]:
        """Get IP rules."""
        rules = list(self._rules.values())

        if is_whitelist is not None:
            rules = [r for r in rules if r.is_whitelist == is_whitelist]

        if action_type:
            rules = [
                r
                for r in rules
                if ActionType.ALL in r.action_types or action_type in r.action_types
            ]

        if enabled_only:
            rules = [r for r in rules if r.is_enabled]

        return rules

    def get_blocked_requests(
        self,
        ip_address: Optional[str] = None,
        reason: Optional[BlockReason] = None,
        start_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[BlockedRequest]:
        """Get blocked request records."""
        records = self._blocked_requests

        if ip_address:
            records = [r for r in records if r.ip_address == ip_address]

        if reason:
            records = [r for r in records if r.reason == reason]

        if start_time:
            records = [r for r in records if r.timestamp >= start_time]

        return records[-limit:]

    def get_ip_stats(self, ip_address: str) -> Optional[IPStats]:
        """Get statistics for an IP."""
        return self._ip_stats.get(ip_address)

    def get_all_stats(self) -> list[IPStats]:
        """Get all IP statistics."""
        return list(self._ip_stats.values())

    def get_auto_blocked(self) -> dict[str, datetime]:
        """Get auto-blocked IPs."""
        now = datetime.now()
        # Clean expired
        self._auto_blocked = {
            ip: until for ip, until in self._auto_blocked.items() if until > now
        }
        return dict(self._auto_blocked)

    def get_summary(self) -> dict:
        """Get service summary."""
        now = datetime.now()

        # Count active rules
        active_whitelist = sum(
            1
            for r in self._rules.values()
            if r.is_enabled
            and r.is_whitelist
            and (not r.expires_at or r.expires_at > now)
        )
        active_blacklist = sum(
            1
            for r in self._rules.values()
            if r.is_enabled
            and not r.is_whitelist
            and (not r.expires_at or r.expires_at > now)
        )

        # Recent blocked
        hour_ago = now - timedelta(hours=1)
        recent_blocked = sum(
            1 for r in self._blocked_requests if r.timestamp > hour_ago
        )

        return {
            "enabled": self.config.enabled,
            "default_action": self.config.default_action,
            "total_rules": len(self._rules),
            "active_whitelist_rules": active_whitelist,
            "active_blacklist_rules": active_blacklist,
            "auto_blocked_ips": len(self._auto_blocked),
            "unique_ips_seen": len(self._ip_stats),
            "total_blocked_requests": len(self._blocked_requests),
            "blocked_last_hour": recent_blocked,
            "rate_limiting_enabled": self.config.enable_rate_limiting,
            "rate_limit": f"{self.config.rate_limit_requests}/{self.config.rate_limit_window_seconds}s",
        }

    def get_status(self) -> dict:
        """Get service status."""
        return {
            "operational": True,
            "enabled": self.config.enabled,
            "rules_count": len(self._rules),
            "auto_blocked_count": len(self._auto_blocked),
        }


# Singleton accessor
def get_ip_whitelist_service() -> IPWhitelistService:
    """Get IP whitelist service instance."""
    return IPWhitelistService.get_instance()
