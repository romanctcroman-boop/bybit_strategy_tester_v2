# Tests for structured_logging.py

from backend.agents.structured_logging import (
    AgentLogger,
    agent_log,
    get_correlation_id,
    new_correlation_id,
    set_correlation_id,
)


class TestCorrelationId:
    def test_get_creates_new(self):
        set_correlation_id(None)  # type: ignore[arg-type]
        # Force a fresh state by setting None, then calling new
        cid = new_correlation_id()
        assert isinstance(cid, str)
        assert len(cid) == 12

    def test_set_and_get(self):
        set_correlation_id("test-cid-123")
        assert get_correlation_id() == "test-cid-123"

    def test_new_generates_unique(self):
        cid1 = new_correlation_id()
        cid2 = new_correlation_id()
        assert cid1 != cid2

    def test_get_returns_same(self):
        new_correlation_id()
        cid1 = get_correlation_id()
        cid2 = get_correlation_id()
        assert cid1 == cid2


class TestAgentLog:
    def test_basic_log(self, capfd):
        new_correlation_id()
        agent_log("INFO", "Test message")
        # No exception means success

    def test_log_with_agent(self):
        new_correlation_id()
        agent_log("INFO", "Test", agent="deepseek")

    def test_log_with_component(self):
        new_correlation_id()
        agent_log("DEBUG", "Test", agent="qwen", component="rate_limiter")

    def test_log_with_extra(self):
        new_correlation_id()
        agent_log("WARNING", "Test", extra={"tokens": 1000, "cost": 0.01})


class TestAgentLogger:
    def test_creation(self):
        logger = AgentLogger(agent="deepseek", component="pool")
        assert logger.agent == "deepseek"
        assert logger.component == "pool"

    def test_debug(self):
        logger = AgentLogger(agent="deepseek")
        logger.debug("Debug message")

    def test_info(self):
        logger = AgentLogger(agent="qwen")
        logger.info("Info message")

    def test_warning(self):
        logger = AgentLogger(agent="perplexity")
        logger.warning("Warning message")

    def test_error(self):
        logger = AgentLogger(agent="deepseek")
        logger.error("Error message")

    def test_with_extra_kwargs(self):
        logger = AgentLogger(agent="deepseek", component="cost")
        logger.info("Usage recorded", tokens=500, cost=0.01)
