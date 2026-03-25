"""
E2E tests for the AI Pipeline page (ai-pipeline.html).

Tests:
- Page loads without JS errors
- Required DOM elements exist
- HITL checkbox works
- Generate button is clickable (no crash)
- Streaming mode is selectable (default, no HITL)
- Result cards are hidden on load
- Stages list is empty on load

Run:
    pytest tests/frontend/test_ai_pipeline_page.py -v
    pytest tests/frontend/test_ai_pipeline_page.py -v -m e2e
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e

BASE_URL = "http://localhost:8000"
PAGE_URL = f"{BASE_URL}/frontend/ai-pipeline.html"


@pytest.fixture(autouse=True)
def collect_js_errors(page: Page):
    """Collect JS errors during the test."""
    errors = []
    page.on("pageerror", lambda err: errors.append(str(err)))
    yield errors
    # Report any JS errors (not assert — some are non-fatal warnings)
    if errors:
        pytest.fail(f"JS errors on page: {errors}")


class TestAiPipelinePageLoad:
    """Page loads correctly with all required elements."""

    def test_page_returns_200(self, page: Page):
        resp = page.goto(PAGE_URL)
        assert resp.status == 200

    def test_no_js_errors_on_load(self, page: Page, collect_js_errors):
        page.goto(PAGE_URL)
        page.wait_for_load_state("networkidle", timeout=10000)
        # collect_js_errors fixture will fail the test if any JS errors occur

    def test_title_contains_pipeline(self, page: Page):
        page.goto(PAGE_URL)
        assert "Pipeline" in page.title() or "AI" in page.title()

    def test_generate_button_exists(self, page: Page):
        page.goto(PAGE_URL)
        btn = page.locator("#btnGenerate")
        expect(btn).to_be_visible()

    def test_symbol_select_exists(self, page: Page):
        page.goto(PAGE_URL)
        expect(page.locator("#symbol")).to_be_visible()

    def test_timeframe_select_exists(self, page: Page):
        page.goto(PAGE_URL)
        expect(page.locator("#timeframe")).to_be_visible()

    def test_start_date_input_exists(self, page: Page):
        page.goto(PAGE_URL)
        expect(page.locator("#startDate")).to_be_visible()

    def test_end_date_input_exists(self, page: Page):
        page.goto(PAGE_URL)
        expect(page.locator("#endDate")).to_be_visible()


class TestAiPipelineOptions:
    """Configuration options are present and functional."""

    def test_run_backtest_checkbox_exists(self, page: Page):
        page.goto(PAGE_URL)
        cb = page.locator("#runBacktest")
        expect(cb).to_be_visible()
        assert page.evaluate("document.getElementById('runBacktest').checked") is True

    def test_hitl_checkbox_exists(self, page: Page):
        page.goto(PAGE_URL)
        cb = page.locator("#enableHitl")
        expect(cb).to_be_visible()

    def test_hitl_checkbox_unchecked_by_default(self, page: Page):
        page.goto(PAGE_URL)
        checked = page.evaluate("document.getElementById('enableHitl').checked")
        assert checked is False

    def test_hitl_checkbox_can_be_toggled(self, page: Page):
        page.goto(PAGE_URL)
        page.locator("#enableHitl").click()
        checked = page.evaluate("document.getElementById('enableHitl').checked")
        assert checked is True

    def test_agent_chips_visible(self, page: Page):
        page.goto(PAGE_URL)
        chips = page.locator(".agent-chip")
        assert chips.count() >= 1

    def test_deepseek_chip_selected_by_default(self, page: Page):
        page.goto(PAGE_URL)
        deepseek = page.locator(".agent-chip[data-agent='deepseek']")
        assert "selected" in (deepseek.get_attribute("class") or "")

    def test_agent_chip_toggle(self, page: Page):
        page.goto(PAGE_URL)
        qwen = page.locator(".agent-chip[data-agent='qwen']")
        qwen.click()
        assert "selected" in (qwen.get_attribute("class") or "")


class TestAiPipelineInitialState:
    """Result sections are hidden on initial load."""

    def test_results_section_hidden_on_load(self, page: Page):
        page.goto(PAGE_URL)
        page.wait_for_load_state("networkidle", timeout=10000)
        visible = page.evaluate(
            "document.getElementById('resultsSection').classList.contains('visible')"
        )
        assert visible is False

    def test_progress_section_hidden_on_load(self, page: Page):
        page.goto(PAGE_URL)
        page.wait_for_load_state("networkidle", timeout=10000)
        visible = page.evaluate(
            "document.getElementById('progressSection').classList.contains('visible')"
        )
        assert visible is False

    def test_hitl_panel_hidden_on_load(self, page: Page):
        page.goto(PAGE_URL)
        page.wait_for_load_state("networkidle", timeout=10000)
        hidden = page.evaluate(
            "document.getElementById('hitlPanel').classList.contains('hidden')"
        )
        assert hidden is True

    def test_strategy_card_hidden_on_load(self, page: Page):
        page.goto(PAGE_URL)
        hidden = page.evaluate(
            "document.getElementById('strategyCard').classList.contains('hidden')"
        )
        assert hidden is True

    def test_stages_list_empty_on_load(self, page: Page):
        page.goto(PAGE_URL)
        content = page.evaluate("document.getElementById('stagesList').innerHTML.trim()")
        assert content == ""


class TestAiPipelineJs:
    """JavaScript functions are defined and callable."""

    def test_run_pipeline_function_exists(self, page: Page):
        page.goto(PAGE_URL)
        exists = page.evaluate("typeof runPipeline === 'function'")
        assert exists is True

    def test_toggle_agent_function_exists(self, page: Page):
        page.goto(PAGE_URL)
        exists = page.evaluate("typeof toggleAgent === 'function'")
        assert exists is True

    def test_show_notification_function_exists(self, page: Page):
        page.goto(PAGE_URL)
        exists = page.evaluate("typeof showNotification === 'function'")
        assert exists is True

    def test_escape_html_function_exists(self, page: Page):
        page.goto(PAGE_URL)
        exists = page.evaluate("typeof escapeHtml === 'function'")
        assert exists is True

    def test_approve_hitl_function_exists(self, page: Page):
        page.goto(PAGE_URL)
        exists = page.evaluate("typeof approveHitl === 'function'")
        assert exists is True

    def test_reject_hitl_function_exists(self, page: Page):
        page.goto(PAGE_URL)
        exists = page.evaluate("typeof rejectHitl === 'function'")
        assert exists is True

    def test_display_stream_result_function_exists(self, page: Page):
        page.goto(PAGE_URL)
        exists = page.evaluate("typeof displayStreamResult === 'function'")
        assert exists is True

    def test_node_display_map_exists(self, page: Page):
        page.goto(PAGE_URL)
        exists = page.evaluate("typeof NODE_DISPLAY === 'object' && NODE_DISPLAY !== null")
        assert exists is True

    def test_node_display_has_analyze_market(self, page: Page):
        page.goto(PAGE_URL)
        val = page.evaluate("NODE_DISPLAY['analyze_market']")
        assert val == 'Market Analysis'

    def test_escape_html_sanitizes_script(self, page: Page):
        page.goto(PAGE_URL)
        result = page.evaluate("escapeHtml('<script>alert(1)</script>')")
        assert "<script>" not in result

    def test_show_notification_creates_toast(self, page: Page):
        page.goto(PAGE_URL)
        page.evaluate("showNotification('test message', 'info')")
        toast = page.locator(".notification-toast")
        expect(toast).to_be_visible()

    def test_display_stream_result_shows_results_section(self, page: Page):
        page.goto(PAGE_URL)
        page.evaluate("""
            displayStreamResult({
                proposals_count: 1,
                selected: {
                    selected_strategy: {strategy_name: 'TestStrat', description: 'Test'},
                    selected_agent: 'deepseek',
                    agreement_score: 0.9
                },
                backtest: { metrics: {sharpe_ratio: 1.2, max_drawdown: 10.0, win_rate: 55.0, total_trades: 30, total_return: 15.0} },
                execution_path: [['analyze_market', 0.12], ['report', 0.01]],
                pipeline_metrics: {total_cost_usd: 0.005, llm_call_count: 2, total_wall_time_s: 5.0}
            }, {})
        """)
        visible = page.evaluate("document.getElementById('resultsSection').classList.contains('visible')")
        assert visible is True

    def test_display_stream_result_shows_strategy_name(self, page: Page):
        page.goto(PAGE_URL)
        page.evaluate("""
            displayStreamResult({
                proposals_count: 1,
                selected: {
                    selected_strategy: {strategy_name: 'RSI_Momentum_v1'},
                    selected_agent: 'deepseek',
                    agreement_score: 0.85
                },
                backtest: {metrics: {}},
                execution_path: [],
                pipeline_metrics: {}
            }, {})
        """)
        content = page.evaluate("document.getElementById('strategyInfo').textContent")
        assert 'RSI_Momentum_v1' in content

    def test_show_hitl_panel_makes_panel_visible(self, page: Page):
        page.goto(PAGE_URL)
        page.evaluate("""
            showHitlPanel('test-pipe-123', {
                strategy_summary: {strategy_name: 'Test Strategy'},
                backtest_metrics: {sharpe_ratio: 1.5, max_drawdown: 8.0, total_trades: 42},
                regime: 'trending_bull'
            })
        """)
        hidden = page.evaluate("document.getElementById('hitlPanel').classList.contains('hidden')")
        assert hidden is False

    def test_reject_hitl_hides_panel(self, page: Page):
        page.goto(PAGE_URL)
        # Show panel first
        page.evaluate("document.getElementById('hitlPanel').classList.remove('hidden')")
        page.evaluate("rejectHitl()")
        hidden = page.evaluate("document.getElementById('hitlPanel').classList.contains('hidden')")
        assert hidden is True
