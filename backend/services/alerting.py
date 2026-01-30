"""
Alerting Service for Bybit Strategy Tester.

Provides Slack and Email notifications for critical system events.
Supports multiple alert levels: INFO, WARNING, CRITICAL.
"""

import asyncio
import logging
import os
import smtplib
import ssl
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Any, Callable, Optional

import httpx

logger = logging.getLogger(__name__)


class AlertLevel(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class AlertConfig:
    """Configuration for alerting service."""

    # Slack
    slack_enabled: bool = False
    slack_webhook_url: str = ""
    slack_channel: str = "#alerts"
    slack_username: str = "Bybit Strategy Tester"
    slack_icon_emoji: str = ":robot_face:"

    # Telegram
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_ids: list[str] = field(default_factory=list)
    telegram_parse_mode: str = "HTML"  # HTML or Markdown

    # Email
    email_enabled: bool = False
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_to_emails: list[str] = field(default_factory=list)
    smtp_use_tls: bool = True

    # Rate limiting
    rate_limit_seconds: int = 60  # Min seconds between same alerts

    @classmethod
    def from_env(cls) -> "AlertConfig":
        """Load configuration from environment variables."""
        to_emails = os.getenv("ALERT_EMAIL_TO", "")
        telegram_chats = os.getenv("TELEGRAM_CHAT_IDS", "")
        return cls(
            slack_enabled=os.getenv("ALERT_SLACK_ENABLED", "false").lower() == "true",
            slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL", ""),
            slack_channel=os.getenv("SLACK_ALERT_CHANNEL", "#alerts"),
            slack_username=os.getenv("SLACK_USERNAME", "Bybit Strategy Tester"),
            slack_icon_emoji=os.getenv("SLACK_ICON_EMOJI", ":robot_face:"),
            telegram_enabled=os.getenv("ALERT_TELEGRAM_ENABLED", "false").lower()
            == "true",
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_ids=[
                c.strip() for c in telegram_chats.split(",") if c.strip()
            ],
            telegram_parse_mode=os.getenv("TELEGRAM_PARSE_MODE", "HTML"),
            email_enabled=os.getenv("ALERT_EMAIL_ENABLED", "false").lower() == "true",
            smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_username=os.getenv("SMTP_USERNAME", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            smtp_from_email=os.getenv("SMTP_FROM_EMAIL", ""),
            smtp_to_emails=[e.strip() for e in to_emails.split(",") if e.strip()],
            smtp_use_tls=os.getenv("SMTP_USE_TLS", "true").lower() == "true",
            rate_limit_seconds=int(os.getenv("ALERT_RATE_LIMIT_SECONDS", "60")),
        )


@dataclass
class Alert:
    """Alert data structure."""

    level: AlertLevel
    title: str
    message: str
    source: str = "system"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def emoji(self) -> str:
        """Get emoji for alert level."""
        return {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.CRITICAL: "🚨",
        }.get(self.level, "📢")

    @property
    def color(self) -> str:
        """Get color for Slack attachment."""
        return {
            AlertLevel.INFO: "#36a64f",  # green
            AlertLevel.WARNING: "#ffa500",  # orange
            AlertLevel.CRITICAL: "#ff0000",  # red
        }.get(self.level, "#808080")

    def to_slack_payload(self, config: AlertConfig) -> dict:
        """Convert to Slack webhook payload."""
        return {
            "channel": config.slack_channel,
            "username": config.slack_username,
            "icon_emoji": config.slack_icon_emoji,
            "attachments": [
                {
                    "color": self.color,
                    "title": f"{self.emoji} {self.title}",
                    "text": self.message,
                    "fields": [
                        {"title": "Source", "value": self.source, "short": True},
                        {
                            "title": "Level",
                            "value": self.level.value.upper(),
                            "short": True,
                        },
                        {
                            "title": "Time",
                            "value": self.timestamp.isoformat(),
                            "short": True,
                        },
                    ]
                    + [
                        {"title": k, "value": str(v), "short": True}
                        for k, v in list(self.metadata.items())[:6]
                    ],
                    "footer": "Bybit Strategy Tester",
                    "ts": int(self.timestamp.timestamp()),
                }
            ],
        }

    def to_email_body(self) -> tuple[str, str]:
        """Convert to email subject and HTML body."""
        subject = f"[{self.level.value.upper()}] {self.title}"

        metadata_html = ""
        if self.metadata:
            metadata_html = "<h3>Additional Information:</h3><ul>"
            for k, v in self.metadata.items():
                metadata_html += f"<li><strong>{k}:</strong> {v}</li>"
            metadata_html += "</ul>"

        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .alert-box {{ padding: 20px; border-radius: 5px; margin: 20px 0; }}
                .critical {{ background-color: #ffe6e6; border-left: 5px solid #ff0000; }}
                .warning {{ background-color: #fff3e6; border-left: 5px solid #ffa500; }}
                .info {{ background-color: #e6ffe6; border-left: 5px solid #36a64f; }}
                h2 {{ margin-top: 0; }}
                .metadata {{ background-color: #f5f5f5; padding: 10px; border-radius: 3px; }}
            </style>
        </head>
        <body>
            <div class="alert-box {self.level.value}">
                <h2>{self.emoji} {self.title}</h2>
                <p><strong>Level:</strong> {self.level.value.upper()}</p>
                <p><strong>Source:</strong> {self.source}</p>
                <p><strong>Time:</strong> {self.timestamp.isoformat()}</p>
                <h3>Message:</h3>
                <p>{self.message}</p>
                {metadata_html}
            </div>
            <hr>
            <p><small>This alert was sent by Bybit Strategy Tester</small></p>
        </body>
        </html>
        """
        return subject, html

    def to_telegram_message(self) -> str:
        """Convert to Telegram message (HTML format)."""
        level_icon = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.CRITICAL: "🚨",
        }.get(self.level, "📢")

        # Build message
        lines = [
            f"<b>{level_icon} {self.title}</b>",
            "",
            f"<b>Level:</b> {self.level.value.upper()}",
            f"<b>Source:</b> {self.source}",
            f"<b>Time:</b> {self.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            "<b>Message:</b>",
            self.message,
        ]

        # Add metadata
        if self.metadata:
            lines.append("")
            lines.append("<b>Details:</b>")
            for k, v in list(self.metadata.items())[:10]:
                lines.append(f"• <code>{k}</code>: {v}")

        return "\n".join(lines)


class AlertingService:
    """
    Service for sending alerts via Slack and Email.

    Usage:
        # Initialize
        service = AlertingService()

        # Send alert
        await service.send_alert(
            level=AlertLevel.CRITICAL,
            title="Trading Error",
            message="Order execution failed for BTCUSDT",
            source="trading_engine",
            metadata={"order_id": "12345", "error": "Insufficient balance"}
        )

        # Or use convenience methods
        await service.critical("API Down", "Bybit API is not responding")
        await service.warning("High Latency", "API latency > 1000ms")
        await service.info("Backtest Complete", "Strategy XYZ finished")
    """

    def __init__(self, config: Optional[AlertConfig] = None):
        """Initialize alerting service."""
        self.config = config or AlertConfig.from_env()
        self._last_alerts: dict[str, datetime] = {}
        self._callbacks: list[Callable[[Alert], None]] = []

        # Log configuration status
        logger.info(
            "AlertingService initialized - Slack: %s, Email: %s",
            "enabled" if self.config.slack_enabled else "disabled",
            "enabled" if self.config.email_enabled else "disabled",
        )

    def register_callback(self, callback: Callable[[Alert], None]) -> None:
        """Register a callback to be called on each alert."""
        self._callbacks.append(callback)

    def _should_rate_limit(self, alert: Alert) -> bool:
        """Check if alert should be rate limited."""
        key = f"{alert.level.value}:{alert.title}:{alert.source}"
        now = datetime.now(timezone.utc)

        if key in self._last_alerts:
            elapsed = (now - self._last_alerts[key]).total_seconds()
            if elapsed < self.config.rate_limit_seconds:
                logger.debug("Rate limiting alert: %s (%.1fs since last)", key, elapsed)
                return True

        self._last_alerts[key] = now
        return False

    async def send_alert(
        self,
        level: AlertLevel,
        title: str,
        message: str,
        source: str = "system",
        metadata: Optional[dict[str, Any]] = None,
        skip_rate_limit: bool = False,
    ) -> bool:
        """
        Send an alert via configured channels.

        Returns True if at least one channel succeeded.
        """
        alert = Alert(
            level=level,
            title=title,
            message=message,
            source=source,
            metadata=metadata or {},
        )

        # Rate limiting
        if not skip_rate_limit and self._should_rate_limit(alert):
            return False

        # Call registered callbacks
        for callback in self._callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.exception("Alert callback failed: %s", e)

        # Send via channels
        results = await asyncio.gather(
            self._send_slack(alert),
            self._send_telegram(alert),
            self._send_email(alert),
            return_exceptions=True,
        )

        successes = sum(1 for r in results if r is True)
        failures = sum(1 for r in results if isinstance(r, Exception))

        if failures > 0:
            logger.warning("Some alert channels failed: %d/%d", failures, len(results))

        return successes > 0

    async def _send_slack(self, alert: Alert) -> bool:
        """Send alert to Slack."""
        if not self.config.slack_enabled or not self.config.slack_webhook_url:
            return False

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.config.slack_webhook_url,
                    json=alert.to_slack_payload(self.config),
                )
                response.raise_for_status()
                logger.info("Slack alert sent: %s", alert.title)
                return True
        except Exception as e:
            logger.exception("Failed to send Slack alert: %s", e)
            return False

    async def _send_telegram(self, alert: Alert) -> bool:
        """Send alert to Telegram."""
        if not self.config.telegram_enabled or not self.config.telegram_bot_token:
            return False

        if not self.config.telegram_chat_ids:
            logger.warning("Telegram enabled but no chat IDs configured")
            return False

        message = alert.to_telegram_message()
        api_url = (
            f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage"
        )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                for chat_id in self.config.telegram_chat_ids:
                    response = await client.post(
                        api_url,
                        json={
                            "chat_id": chat_id,
                            "text": message,
                            "parse_mode": self.config.telegram_parse_mode,
                            "disable_web_page_preview": True,
                        },
                    )
                    if response.status_code != 200:
                        logger.warning(
                            "Telegram send failed for chat %s: %s",
                            chat_id,
                            response.text,
                        )

                logger.info("Telegram alert sent: %s", alert.title)
                return True
        except Exception as e:
            logger.exception("Failed to send Telegram alert: %s", e)
            return False

    async def _send_email(self, alert: Alert) -> bool:
        """Send alert via email."""
        if not self.config.email_enabled:
            return False

        if not all(
            [
                self.config.smtp_host,
                self.config.smtp_username,
                self.config.smtp_password,
                self.config.smtp_from_email,
                self.config.smtp_to_emails,
            ]
        ):
            logger.warning("Email alerting enabled but SMTP config incomplete")
            return False

        try:
            subject, html_body = alert.to_email_body()

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.config.smtp_from_email
            msg["To"] = ", ".join(self.config.smtp_to_emails)
            msg.attach(MIMEText(alert.message, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            # Send in thread pool to not block
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_email_sync, msg)

            logger.info("Email alert sent: %s", alert.title)
            return True
        except Exception as e:
            logger.exception("Failed to send email alert: %s", e)
            return False

    def _send_email_sync(self, msg: MIMEMultipart) -> None:
        """Synchronous email sending (run in thread pool)."""
        context = ssl.create_default_context()

        with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
            if self.config.smtp_use_tls:
                server.starttls(context=context)
            server.login(self.config.smtp_username, self.config.smtp_password)
            server.send_message(msg)

    # Convenience methods
    async def info(
        self,
        title: str,
        message: str,
        source: str = "system",
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Send INFO level alert."""
        return await self.send_alert(AlertLevel.INFO, title, message, source, metadata)

    async def warning(
        self,
        title: str,
        message: str,
        source: str = "system",
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Send WARNING level alert."""
        return await self.send_alert(
            AlertLevel.WARNING, title, message, source, metadata
        )

    async def critical(
        self,
        title: str,
        message: str,
        source: str = "system",
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Send CRITICAL level alert."""
        return await self.send_alert(
            AlertLevel.CRITICAL, title, message, source, metadata, skip_rate_limit=True
        )


# Singleton instance for easy import
_default_service: Optional[AlertingService] = None


def get_alerting_service() -> AlertingService:
    """Get or create the default alerting service instance."""
    global _default_service
    if _default_service is None:
        _default_service = AlertingService()
    return _default_service


async def send_alert(
    level: AlertLevel,
    title: str,
    message: str,
    source: str = "system",
    metadata: Optional[dict[str, Any]] = None,
) -> bool:
    """Convenience function to send alert using default service."""
    return await get_alerting_service().send_alert(
        level, title, message, source, metadata
    )


# Quick functions for common use cases
async def alert_critical(title: str, message: str, **metadata: Any) -> bool:
    """Send a critical alert."""
    return await get_alerting_service().critical(title, message, metadata=metadata)


async def alert_warning(title: str, message: str, **metadata: Any) -> bool:
    """Send a warning alert."""
    return await get_alerting_service().warning(title, message, metadata=metadata)


async def alert_info(title: str, message: str, **metadata: Any) -> bool:
    """Send an info alert."""
    return await get_alerting_service().info(title, message, metadata=metadata)
