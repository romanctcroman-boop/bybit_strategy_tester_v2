/**
 * 📄 Shared - Leverage Manager
 *
 * Handles leverage slider, display, limits calculation,
 * and risk assessment based on volatility
 *
 * @version 1.1.1
 * @date 2026-02-21
 */

import { fetchInstrumentInfo, fetchCurrentPrice, fetchVolatility } from './instrumentService.js';

/**
 * Update leverage display and slider background color
 * @param {number} value - Current leverage value
 */
export function updateLeverageDisplay(value) {
    const leverageValue = document.getElementById('leverageValue');
    const leverageSlider = document.getElementById('strategyLeverage');
    const maxLeverage = leverageSlider ? parseInt(leverageSlider.max) || 100 : 100;

    if (leverageValue) {
        leverageValue.textContent = value + 'x';
        // Change color for high leverage warning (relative to max)
        const leveragePercent = value / maxLeverage;
        if (leveragePercent >= 0.5) {
            leverageValue.style.color = '#ff6b6b';
        } else if (leveragePercent >= 0.2) {
            leverageValue.style.color = '#ffd93d';
        } else {
            leverageValue.style.color = 'var(--accent-color)';
        }
    }

    // Update slider track gradient via CSS variable
    if (leverageSlider) {
        const percent = ((value - 1) / (maxLeverage - 1)) * 100;
        leverageSlider.style.setProperty('--leverage-percent', `${percent}%`);
    }
}

/**
 * Initialize leverage slider scroll support
 */
export function initLeverageSliderScroll() {
    const leverageSlider = document.getElementById('strategyLeverage');
    if (!leverageSlider) return;

    // Scroll wheel support
    leverageSlider.addEventListener('wheel', function (e) {
        e.preventDefault();

        const currentValue = parseInt(this.value);
        const maxLeverage = parseInt(this.max) || 100;
        const step = e.deltaY < 0 ? 1 : -1; // Scroll up = increase, scroll down = decrease

        let newValue = currentValue + step;
        newValue = Math.max(1, Math.min(maxLeverage, newValue)); // Clamp between 1 and max

        this.value = newValue;
        updateLeverageDisplay(newValue);
        // Update warning when leverage changes
        updateLeverageLimits().catch(() => { });
    }, { passive: false });

    // Update warning dynamically when slider moves
    leverageSlider.addEventListener('input', function () {
        updateLeverageDisplay(parseInt(this.value));
        updateLeverageLimits().catch(() => { });
    });
}

/**
 * Calculate and apply maximum leverage based on order size and instrument limits
 *
 * Logic:
 * - Get current price, minNotionalValue ($5), qtyStep, minOrderQty
 * - Calculate margin based on position size type (percent, fixed_amount, contracts)
 * - Validate against capital and minimum position requirements
 * - Update risk indicator based on volatility analysis
 */
export async function updateLeverageLimits() {
    try {
        const symbolEl = document.getElementById('strategySymbol');
        const capitalEl = document.getElementById('strategyCapital');
        const positionSizeTypeEl = document.getElementById('strategyPositionSizeType');
        const positionSizeEl = document.getElementById('strategyPositionSize');
        const leverageSlider = document.getElementById('strategyLeverage');
        const leverageScale = document.querySelector('.leverage-scale');
        const leverageWarning = document.getElementById('leverageWarning');
        const leverageRiskIndicator = document.getElementById('leverageRiskIndicator');

        if (!leverageSlider) return;

        const symbol = symbolEl?.value || 'BTCUSDT';
        const capital = parseFloat(capitalEl?.value) || 10000;
        const positionSizeType = positionSizeTypeEl?.value || 'percent';
        const positionSize = parseFloat(positionSizeEl?.value) || 100;

        if (!symbol || capital <= 0) return;

        // Fetch instrument info, current price, and volatility in parallel
        const [info, currentPrice, volatility] = await Promise.all([
            fetchInstrumentInfo(symbol),
            fetchCurrentPrice(symbol),
            fetchVolatility(symbol)
        ]);

        // Default limits
        let exchangeMaxLeverage = 100;
        let minNotionalValue = 5;
        let minOrderQty = 0.001;
        let qtyStep = 0.001;

        if (info) {
            exchangeMaxLeverage = info.maxLeverage || 100;
            minNotionalValue = info.minNotionalValue || 5;
            minOrderQty = info.minOrderQty || 0.001;
            qtyStep = info.qtyStep || 0.001;
        }

        // Calculate margin and position based on order type
        let margin = capital;
        let isPositionFixed = false;
        let fixedPositionValue = 0;

        if (positionSizeType === 'percent') {
            margin = capital * (positionSize / 100);
        } else if (positionSizeType === 'fixed_amount') {
            margin = positionSize;
        } else if (positionSizeType === 'contracts' && currentPrice) {
            isPositionFixed = true;
            fixedPositionValue = positionSize * currentPrice;
        }

        // Calculate minimum position requirements
        let minPositionValue = minNotionalValue;
        if (currentPrice && currentPrice > 0) {
            const minQtyFromNotional = Math.ceil(minNotionalValue / currentPrice / qtyStep) * qtyStep;
            const effectiveMinQty = Math.max(minOrderQty, minQtyFromNotional);
            minPositionValue = effectiveMinQty * currentPrice;
        }

        const effectiveMaxLeverage = exchangeMaxLeverage;
        const currentLeverage = parseInt(leverageSlider.value) || 1;

        let positionValue, requiredMargin;

        if (isPositionFixed) {
            positionValue = fixedPositionValue;
            requiredMargin = positionValue / currentLeverage;
        } else {
            positionValue = margin * currentLeverage;
            requiredMargin = margin;
        }

        let warningMessage = '';
        let isError = false;

        if (margin <= 0 && !isPositionFixed) {
            // No margin set
        } else if (requiredMargin > capital) {
            if (isPositionFixed) {
                const minLeverageForCapital = Math.ceil(fixedPositionValue / capital);
                if (minLeverageForCapital <= effectiveMaxLeverage) {
                    warningMessage = `Требуемая маржа $${requiredMargin.toFixed(2)} превышает капитал $${capital}. Увеличьте плечо до ${minLeverageForCapital}x`;
                } else {
                    warningMessage = `Позиция $${fixedPositionValue.toFixed(2)} слишком большая. Даже с плечом ${effectiveMaxLeverage}x маржа ($${(fixedPositionValue / effectiveMaxLeverage).toFixed(2)}) превышает капитал $${capital}`;
                    isError = true;
                }
            } else {
                warningMessage = `Маржа $${margin.toFixed(2)} превышает капитал $${capital}`;
                isError = true;
            }
        } else if (positionValue < minPositionValue) {
            warningMessage = `Размер позиции $${positionValue.toFixed(2)} меньше минимума $${minPositionValue.toFixed(2)}`;
        }

        // Update slider limits
        leverageSlider.min = 1;
        leverageSlider.max = effectiveMaxLeverage;
        updateLeverageDisplay(currentLeverage);

        // Update scale labels
        if (leverageScale && effectiveMaxLeverage > 0) {
            const max = effectiveMaxLeverage;
            leverageScale.innerHTML = `
                <span>1x</span>
                <span>${Math.round(max * 0.25)}x</span>
                <span>${Math.round(max * 0.5)}x</span>
                <span>${Math.round(max * 0.75)}x</span>
                <span>${max}x</span>
            `;
        }

        // Show/hide warning
        if (leverageWarning) {
            if (warningMessage) {
                leverageWarning.textContent = warningMessage;
                leverageWarning.classList.add('visible');
                if (isError) {
                    leverageWarning.classList.add('error');
                } else {
                    leverageWarning.classList.remove('error');
                }
            } else {
                leverageWarning.classList.remove('visible', 'error');
                leverageWarning.textContent = '';
            }
        }

        // Update risk indicator based on volatility
        updateRiskIndicator(leverageRiskIndicator, currentLeverage, volatility);

        // Debug log
        if (currentPrice) {
            console.log(`${symbol}: type=${positionSizeType}, margin=$${requiredMargin.toFixed(2)}, leverage=${currentLeverage}x, position=$${positionValue.toFixed(2)}, capital=$${capital}`);
        }

    } catch (error) {
        console.warn('Error updating leverage limits:', error);
    }
}

/**
 * Get Bybit maintenance margin rate based on position tier
 * Source: https://www.bybit.com/en/help-center/article/Maintenance-Margin-USDT
 * @param {number} positionValue - Position value in USDT
 * @returns {number} Maintenance margin rate as percentage (0.5 - 12.5%)
 */
function getMaintenanceMarginRate(positionValue = 100000) {
    // Bybit USDT Perpetual tiers (simplified, for BTCUSDT-like)
    const tiers = [
        { limit: 2000000, mmr: 0.5 },
        { limit: 4000000, mmr: 1.0 },
        { limit: 8000000, mmr: 1.5 },
        { limit: 15000000, mmr: 2.0 },
        { limit: 30000000, mmr: 2.5 },
        { limit: 50000000, mmr: 3.0 },
        { limit: 80000000, mmr: 3.5 },
        { limit: 120000000, mmr: 4.0 },
        { limit: Infinity, mmr: 5.0 }
    ];

    for (const tier of tiers) {
        if (positionValue <= tier.limit) {
            return tier.mmr;
        }
    }
    return 5.0; // Max MMR
}

/**
 * Calculate liquidation price distance as percentage (TradingView/Bybit style)
 * Formula: (100 / leverage) - maintenance_margin_rate
 * @param {number} leverage - Current leverage
 * @param {number} positionValue - Position value in USDT (for MMR tier)
 * @returns {number} Percentage move to liquidation
 */
function calculateLiquidationPercent(leverage, positionValue = 100000) {
    const basePercent = 100 / leverage;
    const mmr = getMaintenanceMarginRate(positionValue);
    // Liquidation happens when loss reaches (initial_margin - maintenance_margin)
    // = (1/leverage - mmr/100) * 100 = 100/leverage - mmr
    const liquidationPercent = Math.max(basePercent - mmr, 0.1); // Min 0.1% to avoid negative
    return liquidationPercent;
}

/**
 * Update risk indicator based on leverage and volatility
 * @param {HTMLElement} indicator - Risk indicator element
 * @param {number} leverage - Current leverage
 * @param {Object|null} volatility - Volatility data
 * @param {number} positionValue - Position value for MMR calculation
 */
function updateRiskIndicator(indicator, leverage, volatility, positionValue = 100000) {
    if (!indicator) return;

    // Use TradingView/Bybit-style calculation with maintenance margin
    const liquidationPercent = calculateLiquidationPercent(leverage, positionValue);
    let riskClass, riskText;

    if (volatility && volatility.avg_daily_range) {
        const maxMove = volatility.max_daily_move || 0;
        const avgRange = volatility.avg_daily_range;
        const riskRatio = liquidationPercent / avgRange;
        const maxMoveWarning = maxMove > 0 && liquidationPercent < maxMove;
        const maxSuffix = maxMove > 0 ? ` макс. ${maxMove.toFixed(0)}%` : '';

        if (riskRatio < 2) {
            riskClass = 'risk-extreme';
            riskText = `🔴 ОПАСНО! ликв. ${liquidationPercent.toFixed(1)}% | вол. ${avgRange.toFixed(1)}%/день${maxSuffix}`;
        } else if (riskRatio < 4 || maxMoveWarning) {
            riskClass = 'risk-high';
            riskText = `🟠 Высокий риск: ликв. ${liquidationPercent.toFixed(1)}% | вол. ${avgRange.toFixed(1)}%/день${maxSuffix}`;
        } else if (riskRatio < 8) {
            riskClass = 'risk-medium';
            riskText = `🟡 Средний риск: ликв. ${liquidationPercent.toFixed(1)}% | вол. ${avgRange.toFixed(1)}%/день${maxSuffix}`;
        } else {
            riskClass = 'risk-low';
            riskText = `🟢 Низкий риск: ликв. ${liquidationPercent.toFixed(1)}% | вол. ${avgRange.toFixed(1)}%/день${maxSuffix}`;
        }
    } else {
        // Fallback to simple leverage-based assessment
        if (leverage <= 5) {
            riskClass = 'risk-low';
            riskText = `🟢 Низкий риск: ликв. при движении ${liquidationPercent.toFixed(2)}%`;
        } else if (leverage <= 20) {
            riskClass = 'risk-medium';
            riskText = `🟡 Средний риск: ликв. при движении ${liquidationPercent.toFixed(2)}%`;
        } else if (leverage <= 50) {
            riskClass = 'risk-high';
            riskText = `🟠 Высокий риск: ликв. при движении ${liquidationPercent.toFixed(2)}%`;
        } else {
            riskClass = 'risk-extreme';
            riskText = `🔴 Экстремальный риск: ликв. при движении ${liquidationPercent.toFixed(2)}%`;
        }
    }

    indicator.textContent = riskText;
    // Сохранить существующие классы (properties-leverage-risk и т.д.), обновить только risk level
    indicator.classList.remove('risk-low', 'risk-medium', 'risk-high', 'risk-extreme');
    indicator.classList.add('leverage-risk-indicator', riskClass);
    indicator.title = 'Ликв. = порог до ликвидации. Волатильность по дневным свечам (D).';
}

/**
 * Update risk indicator for arbitrary elements (e.g. Strategy Builder Properties).
 * Fetches instrument/price/volatility and updates the risk text.
 * Also updates slider.max from exchange maxLeverage (Bug #2 fix).
 * @param {Object} opts - Elements: symbolEl, capitalEl, positionSizeTypeEl, positionSizeEl, leverageVal (number), riskIndicatorEl, rangeEl (optional slider)
 */
export async function updateLeverageRiskForElements(opts) {
    const { symbolEl, capitalEl, positionSizeTypeEl, positionSizeEl, leverageVal, riskIndicatorEl, rangeEl } = opts;
    if (!riskIndicatorEl || leverageVal == null) return;

    const rawSymbol = symbolEl?.value?.trim()?.toUpperCase() || '';

    // If no symbol selected, hide risk indicator or show placeholder
    if (!rawSymbol) {
        riskIndicatorEl.textContent = '';
        riskIndicatorEl.classList.remove('risk-low', 'risk-medium', 'risk-high', 'risk-extreme');
        riskIndicatorEl.style.display = 'none';
        return;
    }

    // Show indicator when symbol is selected
    riskIndicatorEl.style.display = '';

    const symbol = rawSymbol;
    const capital = parseFloat(capitalEl?.value) || 10000;
    const positionSizeType = positionSizeTypeEl?.value || 'percent';
    const positionSize = parseFloat(positionSizeEl?.value) || 100;

    const [info, currentPrice, volatility] = await Promise.all([
        fetchInstrumentInfo(symbol),
        fetchCurrentPrice(symbol),
        fetchVolatility(symbol)
    ]);

    // Bug #2 fix: update slider max from exchange maxLeverage
    if (info && info.maxLeverage && rangeEl) {
        const exchMax = parseInt(info.maxLeverage, 10) || 100;
        if (parseInt(rangeEl.max, 10) !== exchMax) {
            rangeEl.max = exchMax;
            rangeEl.title = `Кредитное плечо 1–${exchMax}x (лимит биржи для ${symbol})`;
            // Clamp current value to new max
            const cur = parseInt(rangeEl.value, 10);
            if (cur > exchMax) rangeEl.value = exchMax;
        }
    }

    let margin = capital;
    let positionValue = 100000;
    if (positionSizeType === 'percent') {
        margin = capital * (positionSize / 100);
        positionValue = margin * leverageVal;
    } else if (positionSizeType === 'fixed_amount') {
        margin = positionSize;
        positionValue = margin * leverageVal;
    } else if (positionSizeType === 'contracts' && currentPrice) {
        positionValue = positionSize * currentPrice;
    } else {
        positionValue = margin * leverageVal;
    }
    updateRiskIndicator(riskIndicatorEl, leverageVal, volatility, positionValue);
}

// Expose to global scope for inline handlers (backwards compatibility)
if (typeof window !== 'undefined') {
    window.updateLeverageDisplay = updateLeverageDisplay;
}
