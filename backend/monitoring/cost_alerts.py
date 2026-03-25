"""
Cost Alert Notification System

Sends alerts via Telegram and/or Email when cost thresholds are exceeded.
"""

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

import httpx
from loguru import logger

# Strong references to background tasks — prevents GC before completion (RUF006)
_background_tasks: set[asyncio.Task] = set()


class AlertLevel(Enum):
    """Alert severity levels"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class CostAlert:
    """Cost alert data"""

    alert_type: str  # "hourly", "daily", "session", "budget"
    level: AlertLevel
    current_cost: float
    threshold: float
    period: str  # "2025-12-08", "2025-12-08_16", etc.
    agent: str | None = None
    message: str = ""
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().timestamp()
        if not self.message:
            self.message = self._generate_message()

    def _generate_message(self) -> str:
        """Generate alert message"""
        level_emoji = {
            AlertLevel.INFO: "\u2139\ufe0f",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.CRITICAL: "🚨",
        }
        emoji = level_emoji.get(self.level, "📢")

        agent_info = f" ({self.agent})" if self.agent else ""

        return (
            f"{emoji} **Cost Alert: {self.alert_type.upper()}**{agent_info}\n\n"
            f"💰 Current: **${self.current_cost:.4f}**\n"
            f"📊 Threshold: ${self.threshold:.4f}\n"
            f"📅 Period: {self.period}\n"
            f"🕐 Time: {datetime.fromtimestamp(self.timestamp).strftime('%Y-%m-%d %H:%M:%S')}"
        )


class TelegramNotifier:
    """Send notifications via Telegram Bot API"""

    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.enabled = bool(self.bot_token and self.chat_id)

        if not self.enabled:
            logger.info("📱 Telegram notifications disabled (no TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID)")

    async def send_alert(self, alert: CostAlert) -> bool:
        """Send alert via Telegram"""
        if not self.enabled:
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    json={
                        "chat_id": self.chat_id,
                        "text": alert.message,
                        "parse_mode": "Markdown",
                    },
                )

                if response.status_code == 200:
                    logger.info(f"📱 Telegram alert sent: {alert.alert_type}")
                    return True
                else:
                    logger.error(f"❌ Telegram API error: {response.text}")
                    return False

        except Exception as e:
            logger.error(f"❌ Telegram send failed: {e}")
            return False

    def send_alert_sync(self, alert: CostAlert) -> bool:
        """Synchronous wrapper for send_alert"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Store reference to prevent GC before task completes (RUF006)
                task = asyncio.create_task(self.send_alert(alert))
                _background_tasks.add(task)
                task.add_done_callback(_background_tasks.discard)
                return True
            else:
                return loop.run_until_complete(self.send_alert(alert))
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(self.send_alert(alert))


class EmailNotifier:
    """Send notifications via Email (SMTP)"""

    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.recipient = os.getenv("ALERT_EMAIL")

        self.enabled = bool(self.smtp_user and self.smtp_password and self.recipient)

        if not self.enabled:
            logger.info("📧 Email notifications disabled (no SMTP credentials)")

    async def send_alert(self, alert: CostAlert) -> bool:
        """Send alert via Email"""
        if not self.enabled:
            return False

        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            msg = MIMEMultipart()
            msg["From"] = self.smtp_user or ""
            msg["To"] = self.recipient or ""
            msg["Subject"] = f"[Cost Alert] {alert.alert_type.upper()} - ${alert.current_cost:.2f}"

            # HTML body
            html = f"""
            <html>
            <body>
            <h2 style="color: {"red" if alert.level == AlertLevel.CRITICAL else "orange"}">
                Cost Alert: {alert.alert_type.upper()}
            </h2>
            <table>
                <tr><td><strong>Current Cost:</strong></td><td>${alert.current_cost:.4f}</td></tr>
                <tr><td><strong>Threshold:</strong></td><td>${alert.threshold:.4f}</td></tr>
                <tr><td><strong>Period:</strong></td><td>{alert.period}</td></tr>
                <tr><td><strong>Agent:</strong></td><td>{alert.agent or "All"}</td></tr>
                <tr><td><strong>Time:</strong></td><td>{datetime.fromtimestamp(alert.timestamp).isoformat()}</td></tr>
            </table>
            </body>
            </html>
            """
            msg.attach(MIMEText(html, "html"))

            # Send in thread to avoid blocking
            def send_email():
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    server.starttls()
                    server.login(self.smtp_user or "", self.smtp_password or "")
                    server.send_message(msg)

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, send_email)

            logger.info(f"📧 Email alert sent: {alert.alert_type}")
            return True

        except Exception as e:
            logger.error(f"❌ Email send failed: {e}")
            return False


class CostAlertManager:
    """Manage cost alerts and notifications"""

    # Rate limiting: don't send more than 1 alert per type per period
    _sent_alerts: dict[str, float] = {}
    ALERT_COOLDOWN_SECONDS = 3600  # 1 hour cooldown per alert type

    def __init__(self):
        self.telegram = TelegramNotifier()
        self.email = EmailNotifier()

        # Thresholds (can be configured via env)
        self.thresholds = {
            "hourly": float(os.getenv("COST_ALERT_HOURLY", "1.0")),
            "daily": float(os.getenv("COST_ALERT_DAILY", "10.0")),
            "session": float(os.getenv("COST_ALERT_SESSION", "5.0")),
            "budget": float(os.getenv("COST_ALERT_BUDGET", "100.0")),
        }

    def check_and_alert(
        self,
        alert_type: str,
        current_cost: float,
        period: str = "",
        agent: str | None = None,
    ) -> bool:
        """Check if threshold exceeded and send alert if needed"""
        threshold = self.thresholds.get(alert_type, 0)
        if current_cost <= threshold:
            return False

        # Rate limiting check
        alert_key = f"{alert_type}:{period}:{agent or 'all'}"
        last_sent = self._sent_alerts.get(alert_key, 0)
        now = datetime.now().timestamp()

        if now - last_sent < self.ALERT_COOLDOWN_SECONDS:
            logger.debug(f"Alert {alert_key} on cooldown, skipping")
            return False

        # Determine alert level
        ratio = current_cost / threshold
        if ratio >= 2.0:
            level = AlertLevel.CRITICAL
        elif ratio >= 1.5:
            level = AlertLevel.WARNING
        else:
            level = AlertLevel.INFO

        # Create alert
        alert = CostAlert(
            alert_type=alert_type,
            level=level,
            current_cost=current_cost,
            threshold=threshold,
            period=period or datetime.now().strftime("%Y-%m-%d"),
            agent=agent,
        )

        # Send notifications
        sent = False

        if self.telegram.enabled:
            self.telegram.send_alert_sync(alert)
            sent = True

        # Only send email for critical alerts
        if self.email.enabled and level == AlertLevel.CRITICAL:
            try:
                asyncio.run(self.email.send_alert(alert))
                sent = True
            except Exception as e:
                logger.error(f"Failed to send email alert: {e}")

        if sent:
            self._sent_alerts[alert_key] = now
            logger.info(f"🔔 Cost alert sent: {alert_type} ${current_cost:.2f} > ${threshold:.2f}")

        return sent


# Singleton instance
_alert_manager: CostAlertManager | None = None


def get_alert_manager() -> CostAlertManager:
    """Get or create singleton alert manager"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = CostAlertManager()
    return _alert_manager


def send_cost_alert(
    alert_type: str,
    current_cost: float,
    period: str = "",
    agent: str | None = None,
) -> bool:
    """Convenience function to check and send cost alert"""
    return get_alert_manager().check_and_alert(
        alert_type=alert_type,
        current_cost=current_cost,
        period=period,
        agent=agent,
    )
