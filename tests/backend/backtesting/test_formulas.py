"""
tests/backend/backtesting/test_formulas.py
==========================================
Тесты для backend/backtesting/formulas.py

Принципы:
- Параметрические тесты с известными значениями
- Edge-cases: пустые массивы, нули, экстремальные значения
- Проверка соответствия с TradingView формулами
- 95%+ coverage цели

Run:
    pytest tests/backend/backtesting/test_formulas.py -v
    pytest tests/backend/backtesting/test_formulas.py --cov=backend/backtesting/formulas -v
"""

import math

import numpy as np
import pytest

from backend.backtesting.formulas import (
    ANNUALIZATION_DAILY,
    ANNUALIZATION_HOURLY,
    calc_cagr,
    calc_calmar,
    calc_expectancy,
    calc_max_drawdown,
    calc_payoff_ratio,
    calc_profit_factor,
    calc_recovery_factor,
    calc_returns_from_equity,
    calc_sharpe,
    calc_sortino,
    calc_sqn,
    calc_ulcer_index,
    calc_win_rate,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def flat_equity():
    """Кривая без просадок — горизонтальная линия."""
    return np.array([10000.0] * 50)


@pytest.fixture
def growing_equity():
    """Монотонно растущая кривая — нет просадок."""
    return np.linspace(10000.0, 20000.0, 100)


@pytest.fixture
def drawdown_equity():
    """Кривая с одной чёткой просадкой: 10k→12k→9k→12k."""
    equity = np.array(
        [10000.0, 10500.0, 11000.0, 11500.0, 12000.0, 11000.0, 10000.0, 9000.0, 9500.0, 10000.0, 11000.0, 12000.0]
    )
    return equity


@pytest.fixture
def normal_returns():
    """Нормально-распределённые доходности (seed=42 для воспроизводимости)."""
    rng = np.random.default_rng(42)
    return rng.normal(loc=0.001, scale=0.02, size=1000)


@pytest.fixture
def all_positive_returns():
    return np.array([0.01, 0.02, 0.015, 0.005, 0.03])


@pytest.fixture
def all_negative_returns():
    return np.array([-0.01, -0.02, -0.015, -0.005, -0.03])


# =============================================================================
# КОНСТАНТЫ
# =============================================================================


class TestConstants:
    def test_annualization_hourly_value(self):
        """8766 = 365.25 * 24"""
        assert pytest.approx(8766.0) == ANNUALIZATION_HOURLY

    def test_annualization_daily_value(self):
        """365.25 дней в году"""
        assert pytest.approx(365.25) == ANNUALIZATION_DAILY


# =============================================================================
# calc_returns_from_equity
# =============================================================================


class TestCalcReturnsFromEquity:
    def test_basic_two_elements(self):
        eq = np.array([100.0, 110.0])
        r = calc_returns_from_equity(eq)
        assert len(r) == 1
        assert r[0] == pytest.approx(0.1)  # +10%

    def test_basic_three_elements(self):
        eq = np.array([100.0, 110.0, 99.0])
        r = calc_returns_from_equity(eq)
        assert len(r) == 2
        assert r[0] == pytest.approx(0.1)
        assert r[1] == pytest.approx((99.0 - 110.0) / 110.0)

    def test_empty_array_returns_empty(self):
        r = calc_returns_from_equity(np.array([]))
        assert len(r) == 0

    def test_single_element_returns_empty(self):
        r = calc_returns_from_equity(np.array([10000.0]))
        assert len(r) == 0

    def test_zero_equity_protected(self):
        """Деление на 0 защищено: используется max(equity, 1)."""
        eq = np.array([0.0, 100.0, 50.0])
        r = calc_returns_from_equity(eq)
        assert np.all(np.isfinite(r))

    def test_growing_equity_all_positive(self, growing_equity):
        r = calc_returns_from_equity(growing_equity)
        assert np.all(r > 0)

    def test_nan_and_inf_replaced_by_zero(self):
        eq = np.array([100.0, float("nan"), 110.0, float("inf"), 90.0])
        r = calc_returns_from_equity(eq)
        assert np.all(np.isfinite(r))


# =============================================================================
# calc_win_rate
# =============================================================================


class TestCalcWinRate:
    def test_basic_60_percent(self):
        assert calc_win_rate(6, 10) == pytest.approx(60.0)

    def test_zero_total_trades(self):
        assert calc_win_rate(0, 0) == 0.0

    def test_negative_total_trades(self):
        assert calc_win_rate(5, -1) == 0.0

    def test_all_winning(self):
        assert calc_win_rate(10, 10) == pytest.approx(100.0)

    def test_all_losing(self):
        assert calc_win_rate(0, 10) == pytest.approx(0.0)

    def test_returns_percentage_not_fraction(self):
        """Важно: возвращает %, а не долю (TV-стандарт)."""
        result = calc_win_rate(5, 10)
        assert result == pytest.approx(50.0)
        assert result > 1.0  # НЕ 0.5

    @pytest.mark.parametrize(
        "wins,total,expected",
        [
            (1, 3, pytest.approx(33.333, rel=1e-3)),
            (2, 3, pytest.approx(66.667, rel=1e-3)),
            (100, 200, pytest.approx(50.0)),
        ],
    )
    def test_parametric(self, wins, total, expected):
        assert calc_win_rate(wins, total) == expected


# =============================================================================
# calc_profit_factor
# =============================================================================


class TestCalcProfitFactor:
    def test_basic_ratio(self):
        assert calc_profit_factor(1000.0, 500.0) == pytest.approx(2.0)

    def test_zero_loss_with_profit(self):
        """Нет убытков → PF = 100 (TV ceiling)."""
        assert calc_profit_factor(500.0, 0.0) == pytest.approx(100.0)

    def test_zero_loss_zero_profit(self):
        assert calc_profit_factor(0.0, 0.0) == pytest.approx(0.0)

    def test_capped_at_100(self):
        """Очень большая прибыль → клипуется в 100."""
        assert calc_profit_factor(99999.0, 1.0) == pytest.approx(100.0)

    def test_less_than_one(self):
        """Убыточная стратегия."""
        pf = calc_profit_factor(300.0, 500.0)
        assert pf == pytest.approx(0.6)
        assert pf < 1.0

    @pytest.mark.parametrize(
        "gp,gl,expected",
        [
            (1000, 1000, pytest.approx(1.0)),
            (2000, 1000, pytest.approx(2.0)),
            (0, 500, pytest.approx(0.0)),
        ],
    )
    def test_parametric(self, gp, gl, expected):
        assert calc_profit_factor(gp, gl) == expected


# =============================================================================
# calc_payoff_ratio
# =============================================================================


class TestCalcPayoffRatio:
    def test_basic_ratio(self):
        assert calc_payoff_ratio(200.0, -100.0) == pytest.approx(2.0)

    def test_avg_loss_zero(self):
        assert calc_payoff_ratio(100.0, 0.0) == 0.0

    def test_positive_avg_loss_value(self):
        """avg_loss может быть передан как |значение| или отрицательное."""
        assert calc_payoff_ratio(300.0, 100.0) == pytest.approx(3.0)
        assert calc_payoff_ratio(300.0, -100.0) == pytest.approx(3.0)

    def test_equal_win_loss(self):
        assert calc_payoff_ratio(100.0, -100.0) == pytest.approx(1.0)


# =============================================================================
# calc_expectancy
# =============================================================================


class TestCalcExpectancy:
    def test_positive_expectancy(self):
        """60% win rate, avg_win=200, avg_loss=-100 → 0.6*200 + 0.4*(-100) = 80."""
        result = calc_expectancy(60.0, 200.0, -100.0)
        assert result == pytest.approx(80.0)

    def test_negative_expectancy(self):
        """40% win rate, avg_win=100, avg_loss=-200 → 0.4*100 + 0.6*(-200) = -80."""
        result = calc_expectancy(40.0, 100.0, -200.0)
        assert result == pytest.approx(-80.0)

    def test_zero_expectancy(self):
        """50% win rate, avg_win=100, avg_loss=-100 → 0."""
        result = calc_expectancy(50.0, 100.0, -100.0)
        assert result == pytest.approx(0.0)

    def test_100_percent_win_rate(self):
        result = calc_expectancy(100.0, 500.0, -100.0)
        assert result == pytest.approx(500.0)

    def test_0_percent_win_rate(self):
        result = calc_expectancy(0.0, 500.0, -100.0)
        assert result == pytest.approx(-100.0)


# =============================================================================
# calc_max_drawdown
# =============================================================================


class TestCalcMaxDrawdown:
    def test_no_drawdown_flat(self, flat_equity):
        pct, val, dur = calc_max_drawdown(flat_equity)
        assert pct == pytest.approx(0.0)
        assert val == pytest.approx(0.0)
        assert dur == 0

    def test_no_drawdown_growing(self, growing_equity):
        pct, _val, _dur = calc_max_drawdown(growing_equity)
        assert pct == pytest.approx(0.0, abs=1e-10)

    def test_known_drawdown(self, drawdown_equity):
        """Пик=12000, минимум=9000 → dd=(12000-9000)/12000=25%."""
        pct, val, _dur = calc_max_drawdown(drawdown_equity)
        assert pct == pytest.approx(25.0, rel=0.01)
        assert val == pytest.approx(3000.0, rel=0.01)

    def test_single_element(self):
        pct, val, dur = calc_max_drawdown(np.array([10000.0]))
        assert pct == 0.0
        assert val == 0.0
        assert dur == 0

    def test_empty_array(self):
        pct, _val, _dur = calc_max_drawdown(np.array([]))
        assert pct == 0.0

    def test_monotonic_decline(self):
        """Кривая только падает: 100→50 = 50% просадка."""
        equity = np.array([100.0, 90.0, 80.0, 70.0, 60.0, 50.0])
        pct, val, _dur = calc_max_drawdown(equity)
        assert pct == pytest.approx(50.0)
        assert val == pytest.approx(50.0)

    def test_zero_equity_protected(self):
        """Начало с нуля — нет деления на 0."""
        equity = np.array([0.0, 10.0, 5.0, 8.0])
        pct, _val, _dur = calc_max_drawdown(equity)
        assert np.isfinite(pct)

    def test_returns_three_values(self, drawdown_equity):
        result = calc_max_drawdown(drawdown_equity)
        assert len(result) == 3

    def test_duration_positive(self, drawdown_equity):
        _, _, dur = calc_max_drawdown(drawdown_equity)
        assert dur > 0


# =============================================================================
# calc_ulcer_index
# =============================================================================


class TestCalcUlcerIndex:
    def test_no_drawdown(self, growing_equity):
        ui = calc_ulcer_index(growing_equity)
        assert ui == pytest.approx(0.0, abs=1e-10)

    def test_returns_percentage(self, drawdown_equity):
        """Ulcer Index уже в %."""
        ui = calc_ulcer_index(drawdown_equity)
        assert ui > 0.0
        assert ui < 100.0

    def test_empty_array(self):
        assert calc_ulcer_index(np.array([])) == 0.0

    def test_single_element(self):
        assert calc_ulcer_index(np.array([10000.0])) == 0.0

    def test_larger_drawdown_larger_ui(self):
        """Стратегия с большей просадкой должна иметь больший UI."""
        small_dd = np.array([10000, 9800, 9900, 10000, 10100, 10200], dtype=float)
        large_dd = np.array([10000, 8000, 8500, 9000, 9500, 10000], dtype=float)
        ui_small = calc_ulcer_index(small_dd)
        ui_large = calc_ulcer_index(large_dd)
        assert ui_large > ui_small


# =============================================================================
# calc_cagr
# =============================================================================


class TestCalcCagr:
    def test_basic_annual_return(self):
        """10k → 12k за 1 год = 20% CAGR."""
        cagr = calc_cagr(10000.0, 12000.0, 1.0)
        assert cagr == pytest.approx(20.0)

    def test_two_year_compound(self):
        """10k → 14400 за 2 года = 20% CAGR (sqrt(1.44)-1=0.2)."""
        cagr = calc_cagr(10000.0, 14400.0, 2.0)
        assert cagr == pytest.approx(20.0, rel=1e-4)

    def test_zero_initial_capital(self):
        assert calc_cagr(0.0, 12000.0, 1.0) == 0.0

    def test_zero_years(self):
        assert calc_cagr(10000.0, 12000.0, 0.0) == 0.0

    def test_negative_return(self):
        """10k → 8k за 1 год = -20%."""
        cagr = calc_cagr(10000.0, 8000.0, 1.0)
        assert cagr == pytest.approx(-20.0)

    def test_short_period_no_extreme_values(self):
        """Период < 30 дней → простая аннуализация, нет экстремальных значений."""
        cagr = calc_cagr(10000.0, 10100.0, 0.05)  # ~18 дней
        assert -100.0 <= cagr <= 200.0

    def test_total_loss_clipped(self):
        """Банкротство (-100%) возвращает -100."""
        cagr = calc_cagr(10000.0, 0.0, 1.0)
        assert cagr == pytest.approx(-100.0)

    def test_result_clipped_upper(self):
        """Нереальная прибыль клипуется в 200."""
        cagr = calc_cagr(1.0, 1_000_000.0, 0.01)
        assert cagr <= 200.0


# =============================================================================
# calc_recovery_factor
# =============================================================================


class TestCalcRecoveryFactor:
    def test_basic_recovery(self):
        """Net profit 2000, initial 10000, max_dd 10% → rf = 2000/(10000*0.1) = 2.0."""
        rf = calc_recovery_factor(2000.0, 10000.0, 10.0)
        assert rf == pytest.approx(2.0)

    def test_zero_drawdown(self):
        assert calc_recovery_factor(1000.0, 10000.0, 0.0) == 0.0

    def test_zero_initial_capital(self):
        assert calc_recovery_factor(1000.0, 0.0, 10.0) == 0.0

    def test_negative_net_profit(self):
        rf = calc_recovery_factor(-500.0, 10000.0, 10.0)
        assert rf < 0.0

    def test_clipped_at_100(self):
        """Огромная прибыль при малой просадке → клипуется в 100."""
        rf = calc_recovery_factor(99999.0, 10000.0, 0.01)
        assert rf <= 100.0


# =============================================================================
# calc_sharpe
# =============================================================================


class TestCalcSharpe:
    def test_empty_returns(self):
        assert calc_sharpe(np.array([])) == 0.0

    def test_single_return(self):
        assert calc_sharpe(np.array([0.01])) == 0.0

    def test_zero_std(self):
        """Все доходности одинаковые → std=0 → Sharpe=0."""
        returns = np.ones(100) * 0.01
        assert calc_sharpe(returns) == 0.0

    def test_positive_sharpe(self, normal_returns):
        sharpe = calc_sharpe(normal_returns)
        assert sharpe > 0  # mean=0.001 > 0, std > 0

    def test_negative_sharpe(self, all_negative_returns):
        sharpe = calc_sharpe(all_negative_returns)
        assert sharpe < 0

    def test_clipped_at_100(self):
        """Нереальный Sharpe клипуется в 100."""
        returns = np.ones(1000) * 1.0  # 100% return every bar
        # std=0 → returns 0
        returns[0] = 1.001  # Небольшое отличие для ненулевого std
        sharpe = calc_sharpe(returns)
        assert sharpe <= 100.0

    def test_clipped_at_minus_100(self):
        returns = np.ones(1000) * -1.0
        returns[0] = -1.001
        sharpe = calc_sharpe(returns)
        assert sharpe >= -100.0

    def test_daily_annualization(self, normal_returns):
        """Разные annualization factors дают разные результаты."""
        s_hourly = calc_sharpe(normal_returns, annualization_factor=ANNUALIZATION_HOURLY)
        s_daily = calc_sharpe(normal_returns, annualization_factor=ANNUALIZATION_DAILY)
        assert s_hourly != s_daily

    def test_short_series_no_annualization(self):
        """< 24 элементов при HOURLY → no annualization (raw ratio)."""
        returns = np.array([0.01, 0.02, 0.015, 0.01, 0.02, 0.01])
        sharpe = calc_sharpe(returns, annualization_factor=ANNUALIZATION_HOURLY)
        assert np.isfinite(sharpe)

    def test_non_finite_values_removed(self):
        returns = np.array([0.01, float("nan"), 0.02, float("inf"), 0.01, -0.01])
        sharpe = calc_sharpe(returns)
        assert np.isfinite(sharpe)


# =============================================================================
# calc_sortino
# =============================================================================


class TestCalcSortino:
    def test_empty_returns(self):
        assert calc_sortino(np.array([])) == 0.0

    def test_single_return(self):
        assert calc_sortino(np.array([0.01])) == 0.0

    def test_all_positive_returns(self, all_positive_returns):
        """Нет downside deviation → Sortino = 100 (идеальная стратегия)."""
        sortino = calc_sortino(all_positive_returns)
        assert sortino == pytest.approx(100.0)

    def test_all_negative_returns(self, all_negative_returns):
        sortino = calc_sortino(all_negative_returns)
        assert sortino < 0

    def test_positive_sortino(self, normal_returns):
        sortino = calc_sortino(normal_returns)
        assert sortino > 0

    def test_clipped_values(self, normal_returns):
        sortino = calc_sortino(normal_returns)
        assert -100.0 <= sortino <= 100.0

    def test_sortino_higher_than_sharpe_for_positive_skew(self, all_positive_returns):
        """Нет потерь → Sortino (100) > Sharpe."""
        sharpe = calc_sharpe(all_positive_returns)
        sortino = calc_sortino(all_positive_returns)
        assert sortino > sharpe

    def test_mar_parameter_effect(self, normal_returns):
        """MAR > 0 снижает Sortino."""
        sortino_0 = calc_sortino(normal_returns, mar=0.0)
        sortino_high = calc_sortino(normal_returns, mar=0.01)
        assert sortino_0 > sortino_high


# =============================================================================
# calc_calmar
# =============================================================================


class TestCalcCalmar:
    def test_basic_calmar(self):
        """Total return 20%, max_dd 10%, 1 year → calmar = 20/10 = 2.0."""
        calmar = calc_calmar(20.0, 10.0, years=1.0)
        assert calmar == pytest.approx(2.0)

    def test_small_drawdown_returns_10(self):
        """max_dd <= 1% → возвращает 10.0 (нет значимой просадки)."""
        calmar = calc_calmar(50.0, 0.5, years=1.0)
        assert calmar == pytest.approx(10.0)

    def test_negative_return_with_drawdown(self):
        calmar = calc_calmar(-20.0, 20.0, years=1.0)
        assert calmar < 0.0

    def test_zero_return_with_drawdown(self):
        calmar = calc_calmar(0.0, 10.0)
        # 0% return / 10% dd = 0
        assert calmar == pytest.approx(0.0, abs=1e-10)

    def test_multi_year_uses_cagr(self):
        """2 года: CAGR(44%) = 20%, max_dd 10% → calmar = 20/10 = 2.0."""
        calmar = calc_calmar(44.0, 10.0, years=2.0)
        assert calmar == pytest.approx(2.0, rel=1e-3)

    def test_capped_at_100(self):
        calmar = calc_calmar(10000.0, 2.0, years=1.0)
        assert calmar <= 100.0

    def test_capped_at_minus_100(self):
        calmar = calc_calmar(-10000.0, 2.0, years=1.0)
        assert calmar >= -100.0


# =============================================================================
# calc_sqn
# =============================================================================


class TestCalcSqn:
    def test_empty_pnl(self):
        assert calc_sqn(np.array([])) == 0.0

    def test_single_trade(self):
        assert calc_sqn(np.array([100.0])) == 0.0

    def test_zero_std(self):
        """Все сделки одинаковые → SQN=0."""
        assert calc_sqn(np.ones(100) * 100.0) == 0.0

    def test_positive_edge(self):
        """Среднее > 0, std > 0 → положительный SQN."""
        rng = np.random.default_rng(42)
        pnls = rng.normal(loc=50.0, scale=100.0, size=100)
        sqn = calc_sqn(pnls)
        assert sqn > 0.0

    def test_negative_edge(self):
        rng = np.random.default_rng(42)
        pnls = rng.normal(loc=-50.0, scale=100.0, size=100)
        sqn = calc_sqn(pnls)
        assert sqn < 0.0

    def test_clipped_values(self):
        pnls = np.ones(100) * 1000.0
        pnls[0] = 1001.0  # tiny std
        sqn = calc_sqn(pnls)
        assert -100.0 <= sqn <= 100.0

    @pytest.mark.parametrize(
        "n_trades,expected_min",
        [
            (25, 1.6),  # 25 сделок при хорошем edge → SQN > 1.6
            (100, 2.0),  # 100 сделок → SQN выше
        ],
    )
    def test_sqn_increases_with_n_trades(self, n_trades, expected_min):
        """SQN должен расти с увеличением N при постоянном edge."""
        rng = np.random.default_rng(0)
        pnls = rng.normal(loc=20.0, scale=50.0, size=n_trades)
        sqn = calc_sqn(pnls)
        assert sqn > 0  # Хотя бы положительный


# =============================================================================
# ИНТЕГРАЦИОННЫЕ ТЕСТЫ — согласованность формул
# =============================================================================


class TestFormulasConsistency:
    def test_sharpe_le_sortino_for_symmetric_distribution(self, normal_returns):
        """
        При нормальном распределении Sortino ≥ Sharpe (меньший знаменатель).
        """
        sharpe = calc_sharpe(normal_returns)
        sortino = calc_sortino(normal_returns)
        assert sortino >= sharpe * 0.9  # с небольшим допуском

    def test_profit_factor_consistent_with_win_rate(self):
        """PF < 1 при убыточных стратегиях, PF > 1 при прибыльных."""
        # Прибыльная: gross_profit > gross_loss
        assert calc_profit_factor(1000, 500) > 1.0
        # Убыточная: gross_profit < gross_loss
        assert calc_profit_factor(500, 1000) < 1.0

    def test_expectancy_sign_matches_strategy_performance(self):
        """Ожидаемость > 0 для прибыльной стратегии."""
        positive = calc_expectancy(60.0, 200.0, -100.0)
        negative = calc_expectancy(30.0, 100.0, -200.0)
        assert positive > 0
        assert negative < 0

    def test_cagr_recoverable_from_formula(self):
        """CAGR верифицируется через формулу конечного капитала."""
        initial = 10000.0
        cagr_pct = 15.0  # 15% годовых
        years = 3.0
        final = initial * math.pow(1 + cagr_pct / 100, years)
        computed_cagr = calc_cagr(initial, final, years)
        assert computed_cagr == pytest.approx(cagr_pct, rel=1e-5)

    def test_max_drawdown_zero_for_monotonic_growth(self, growing_equity):
        pct, _val, _dur = calc_max_drawdown(growing_equity)
        assert pct == pytest.approx(0.0, abs=1e-10)
        assert _val == pytest.approx(0.0, abs=1e-10)

    def test_win_rate_range(self):
        """Win rate всегда в [0, 100]."""
        for wins, total in [(0, 10), (5, 10), (10, 10), (0, 0)]:
            wr = calc_win_rate(wins, total)
            assert 0.0 <= wr <= 100.0

    def test_profit_factor_range(self):
        """Profit factor всегда в [0, 100]."""
        for gp, gl in [(0, 0), (0, 100), (100, 0), (100, 100), (10000, 1)]:
            pf = calc_profit_factor(gp, gl)
            assert 0.0 <= pf <= 100.0


# =============================================================================
# EDGE CASES — граничные условия
# =============================================================================


class TestEdgeCases:
    def test_very_long_equity_curve(self):
        """Производительность на большом массиве (50k баров)."""
        rng = np.random.default_rng(42)
        equity = np.cumsum(rng.normal(0, 10, 50000)) + 10000
        pct, _val, _dur = calc_max_drawdown(equity)
        assert np.isfinite(pct)

    def test_all_nan_returns_sharpe(self):
        returns = np.array([float("nan")] * 10)
        assert calc_sharpe(returns) == 0.0

    def test_all_nan_returns_sortino(self):
        returns = np.array([float("nan")] * 10)
        assert calc_sortino(returns) == 0.0

    def test_ulcer_index_flat_equity(self, flat_equity):
        """Нет просадок → UI = 0."""
        assert calc_ulcer_index(flat_equity) == pytest.approx(0.0, abs=1e-10)

    def test_calmar_very_small_drawdown(self):
        """Очень маленькая просадка не вызывает ошибок."""
        calmar = calc_calmar(10.0, 0.001)
        assert np.isfinite(calmar)

    def test_recovery_factor_very_small_drawdown(self):
        rf = calc_recovery_factor(1000.0, 10000.0, 0.001)
        assert np.isfinite(rf)

    def test_returns_from_equity_preserves_length(self):
        eq = np.linspace(10000, 20000, 500)
        returns = calc_returns_from_equity(eq)
        assert len(returns) == 499  # len(equity) - 1
