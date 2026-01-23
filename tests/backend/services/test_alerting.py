"""
Tests for Alerting Service.
"""

import pytest

from backend.services.alerting import (
    Alert,
    AlertConfig,
    AlertingService,
    AlertLevel,
    get_alerting_service,
)


class TestAlertLevel:
    """Test alert level enum."""

    def test_alert_levels(self):
        """Test all alert level values."""
        assert AlertLevel.INFO.value == "info"
        assert AlertLevel.WARNING.value == "warning"
        assert AlertLevel.CRITICAL.value == "critical"

    def test_alert_level_list(self):
        """Test listing alert levels."""
        levels = list(AlertLevel)
        assert len(levels) == 3
        assert AlertLevel.INFO in levels
        assert AlertLevel.WARNING in levels
        assert AlertLevel.CRITICAL in levels


class TestAlertConfig:
    """Test alert configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = AlertConfig()

        assert config.slack_enabled is False
        assert config.email_enabled is False
        assert config.slack_webhook_url == ""
        assert config.smtp_host == "smtp.gmail.com"

    def test_custom_config(self):
        """Test custom configuration."""
        config = AlertConfig(
            slack_enabled=True,
            slack_webhook_url="https://hooks.slack.com/test",
            email_enabled=True,
            smtp_host="smtp.gmail.com",
            smtp_port=587,
            smtp_username="test@example.com",
            smtp_password="password",
            smtp_from_email="alerts@example.com",
            smtp_to_emails=["admin@example.com"],
        )

        assert config.slack_enabled is True
        assert config.slack_webhook_url == "https://hooks.slack.com/test"
        assert config.email_enabled is True
        assert config.smtp_host == "smtp.gmail.com"
        assert config.smtp_from_email == "alerts@example.com"
        assert config.smtp_to_emails == ["admin@example.com"]


class TestAlert:
    """Test Alert dataclass."""

    def test_alert_creation(self):
        """Test creating an alert."""
        alert = Alert(
            level=AlertLevel.INFO,
            title="Test Alert",
            message="Test message",
            source="test",
        )

        assert alert.level == AlertLevel.INFO
        assert alert.title == "Test Alert"
        assert alert.message == "Test message"
        assert alert.source == "test"
        assert alert.timestamp is not None

    def test_alert_emoji(self):
        """Test alert emoji property."""
        info = Alert(AlertLevel.INFO, "T", "M")
        warning = Alert(AlertLevel.WARNING, "T", "M")
        critical = Alert(AlertLevel.CRITICAL, "T", "M")

        assert info.emoji == "ℹ️"
        assert warning.emoji == "⚠️"
        assert critical.emoji == "🚨"

    def test_alert_color(self):
        """Test alert color property."""
        info = Alert(AlertLevel.INFO, "T", "M")
        warning = Alert(AlertLevel.WARNING, "T", "M")
        critical = Alert(AlertLevel.CRITICAL, "T", "M")

        # Check colors are hex codes
        assert info.color.startswith("#")
        assert warning.color.startswith("#")
        assert critical.color.startswith("#")


class TestAlertingService:
    """Test cases for AlertingService."""

    @pytest.fixture
    def service(self):
        """Create alerting service for testing."""
        config = AlertConfig()  # Default config with nothing enabled
        return AlertingService(config=config)

    @pytest.fixture
    def configured_service(self):
        """Create configured alerting service for testing."""
        config = AlertConfig(
            slack_enabled=True,
            slack_webhook_url="https://hooks.slack.com/test",
            email_enabled=True,
            smtp_host="localhost",
            smtp_port=25,
            smtp_username="test@example.com",
            smtp_password="password",
            smtp_from_email="test@example.com",
            smtp_to_emails=["admin@example.com"],
        )
        return AlertingService(config=config)

    def test_service_init(self, service):
        """Test service initialization."""
        assert service.config is not None
        assert service.config.slack_enabled is False
        assert service.config.email_enabled is False

    def test_service_config(self, configured_service):
        """Test configured service."""
        assert configured_service.config.slack_enabled is True
        assert configured_service.config.email_enabled is True
        assert (
            configured_service.config.slack_webhook_url
            == "https://hooks.slack.com/test"
        )

    @pytest.mark.asyncio
    async def test_send_alert_no_channels(self, service):
        """Test sending alert with no channels configured."""
        result = await service.send_alert(
            level=AlertLevel.INFO, title="Test", message="Test message", source="test"
        )

        # No channels enabled - returns False
        assert result is False

    @pytest.mark.asyncio
    async def test_info_convenience_method(self, service):
        """Test info convenience method."""
        result = await service.info("Test Info", "Info message")
        assert result is False  # No channels

    @pytest.mark.asyncio
    async def test_warning_convenience_method(self, service):
        """Test warning convenience method."""
        result = await service.warning("Test Warning", "Warning message")
        assert result is False  # No channels

    @pytest.mark.asyncio
    async def test_critical_convenience_method(self, service):
        """Test critical convenience method."""
        result = await service.critical("Test Critical", "Critical message")
        assert result is False  # No channels

    def test_register_callback(self, service):
        """Test registering a callback."""
        alerts_received = []

        def callback(alert):
            alerts_received.append(alert)

        service.register_callback(callback)
        assert len(service._callbacks) == 1

    def test_rate_limiting(self, service):
        """Test rate limiting check."""
        alert = Alert(
            level=AlertLevel.INFO,
            title="Test",
            message="Message",
            source="test",
        )

        # First call should not be rate limited
        assert service._should_rate_limit(alert) is False

        # Second call should be rate limited (within 60s default)
        assert service._should_rate_limit(alert) is True


class TestGlobalService:
    """Test global service instance."""

    def test_get_alerting_service(self):
        """Test getting global service instance."""
        svc1 = get_alerting_service()
        svc2 = get_alerting_service()

        assert svc1 is svc2  # Same instance
        assert isinstance(svc1, AlertingService)
