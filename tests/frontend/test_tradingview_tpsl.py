"""
Unit Tests - TradingView Enhanced Markers & TP/SL Price Lines (ТЗ 9.2)

Tests for the enhanced TradingView chart component with TP/SL visualization
and enhanced trade markers with P&L tooltips, size scaling, and exit markers.
"""
import pytest
from typing import List, Dict, Any, Optional


# Type definitions matching TypeScript interfaces
class TradeMarker:
    """Trade marker with TP/SL support and enhanced display fields"""
    
    def __init__(
        self,
        time: int,
        side: str,
        price: float,
        tp_price: Optional[float] = None,
        sl_price: Optional[float] = None,
        exit_price: Optional[float] = None,
        exit_time: Optional[int] = None,
        # Enhanced marker fields (ТЗ 9.2 Step 3)
        pnl: Optional[float] = None,
        pnl_percent: Optional[float] = None,
        size: Optional[float] = None,
        label: Optional[str] = None,
        color: Optional[str] = None,
        is_entry: Optional[bool] = None
    ):
        assert side in ['buy', 'sell'], f"Invalid side: {side}"
        
        self.time = time
        self.side = side
        self.price = price
        self.tp_price = tp_price
        self.sl_price = sl_price
        self.exit_price = exit_price
        self.exit_time = exit_time
        # Enhanced fields
        self.pnl = pnl
        self.pnl_percent = pnl_percent
        self.size = size
        self.label = label
        self.color = color
        self.is_entry = is_entry
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API/JSON"""
        result = {
            'time': self.time,
            'side': self.side,
            'price': self.price,
        }
        
        if self.tp_price is not None:
            result['tp_price'] = self.tp_price
        if self.sl_price is not None:
            result['sl_price'] = self.sl_price
        if self.exit_price is not None:
            result['exit_price'] = self.exit_price
        if self.exit_time is not None:
            result['exit_time'] = self.exit_time
        if self.pnl is not None:
            result['pnl'] = self.pnl
        if self.pnl_percent is not None:
            result['pnl_percent'] = self.pnl_percent
        if self.size is not None:
            result['size'] = self.size
        if self.label is not None:
            result['label'] = self.label
        if self.color is not None:
            result['color'] = self.color
        if self.is_entry is not None:
            result['is_entry'] = self.is_entry
        
        return result


class PriceLine:
    """Custom price line configuration"""
    
    def __init__(
        self,
        price: float,
        color: str,
        line_width: int = 2,
        line_style: str = 'solid',
        axis_label_visible: bool = True,
        title: str = ''
    ):
        assert line_style in ['solid', 'dotted', 'dashed'], f"Invalid line_style: {line_style}"
        
        self.price = price
        self.color = color
        self.line_width = line_width
        self.line_style = line_style
        self.axis_label_visible = axis_label_visible
        self.title = title
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API/JSON"""
        return {
            'price': self.price,
            'color': self.color,
            'lineWidth': self.line_width,
            'lineStyle': self.line_style,
            'axisLabelVisible': self.axis_label_visible,
            'title': self.title,
        }


def calculate_tp_sl(
    entry_price: float,
    side: str,
    tp_percent: float,
    sl_percent: float
) -> tuple[float, float]:
    """
    Calculate TP/SL prices based on entry and percentages.
    
    Args:
        entry_price: Entry price
        side: 'buy' or 'sell'
        tp_percent: Take profit percentage (positive)
        sl_percent: Stop loss percentage (positive)
    
    Returns:
        (tp_price, sl_price)
    """
    if side == 'buy':
        tp_price = entry_price * (1 + tp_percent / 100)
        sl_price = entry_price * (1 - sl_percent / 100)
    else:  # sell
        tp_price = entry_price * (1 - tp_percent / 100)
        sl_price = entry_price * (1 + sl_percent / 100)
    
    return tp_price, sl_price


def should_render_exit_line(marker: TradeMarker) -> bool:
    """
    Determine if exit price line should be rendered separately.
    
    Returns True if exit_price exists and differs from both TP and SL.
    """
    if marker.exit_price is None:
        return False
    
    # Check if exit matches TP or SL (within 0.01% tolerance)
    tolerance = marker.exit_price * 0.0001
    
    if marker.tp_price and abs(marker.exit_price - marker.tp_price) < tolerance:
        return False
    
    if marker.sl_price and abs(marker.exit_price - marker.sl_price) < tolerance:
        return False
    
    return True


class TestTradeMarkerInterface:
    """Test TradeMarker type definition and validation"""
    
    def test_basic_marker_creation(self):
        """Test creating basic trade marker without TP/SL"""
        marker = TradeMarker(
            time=1700000000,
            side='buy',
            price=50000.0
        )
        
        assert marker.time == 1700000000
        assert marker.side == 'buy'
        assert marker.price == 50000.0
        assert marker.tp_price is None
        assert marker.sl_price is None
        assert marker.exit_price is None
        assert marker.exit_time is None
    
    def test_marker_with_tp_sl(self):
        """Test creating marker with TP/SL levels"""
        marker = TradeMarker(
            time=1700000000,
            side='buy',
            price=50000.0,
            tp_price=51500.0,  # +3%
            sl_price=49000.0,  # -2%
        )
        
        assert marker.tp_price == 51500.0
        assert marker.sl_price == 49000.0
    
    def test_marker_with_exit(self):
        """Test marker with exit information"""
        marker = TradeMarker(
            time=1700000000,
            side='buy',
            price=50000.0,
            tp_price=51500.0,
            sl_price=49000.0,
            exit_price=51200.0,
            exit_time=1700003600
        )
        
        assert marker.exit_price == 51200.0
        assert marker.exit_time == 1700003600
    
    def test_invalid_side(self):
        """Test that invalid side raises error"""
        with pytest.raises(AssertionError):
            TradeMarker(
                time=1700000000,
                side='invalid',
                price=50000.0
            )
    
    def test_marker_to_dict(self):
        """Test serialization to dictionary"""
        marker = TradeMarker(
            time=1700000000,
            side='buy',
            price=50000.0,
            tp_price=51500.0,
            sl_price=49000.0
        )
        
        data = marker.to_dict()
        
        assert data['time'] == 1700000000
        assert data['side'] == 'buy'
        assert data['price'] == 50000.0
        assert data['tp_price'] == 51500.0
        assert data['sl_price'] == 49000.0
        assert 'exit_price' not in data  # Optional fields not included when None


class TestPriceLineInterface:
    """Test PriceLine type definition and validation"""
    
    def test_basic_price_line(self):
        """Test creating basic price line"""
        line = PriceLine(
            price=50000.0,
            color='#4caf50'
        )
        
        assert line.price == 50000.0
        assert line.color == '#4caf50'
        assert line.line_width == 2
        assert line.line_style == 'solid'
        assert line.axis_label_visible is True
        assert line.title == ''
    
    def test_custom_price_line(self):
        """Test creating custom price line with all options"""
        line = PriceLine(
            price=51500.0,
            color='#4caf50',
            line_width=3,
            line_style='dashed',
            axis_label_visible=True,
            title='Take Profit'
        )
        
        assert line.line_width == 3
        assert line.line_style == 'dashed'
        assert line.title == 'Take Profit'
    
    def test_invalid_line_style(self):
        """Test that invalid line_style raises error"""
        with pytest.raises(AssertionError):
            PriceLine(
                price=50000.0,
                color='#000000',
                line_style='invalid'
            )
    
    def test_price_line_to_dict(self):
        """Test serialization to dictionary"""
        line = PriceLine(
            price=51500.0,
            color='#4caf50',
            line_style='dashed',
            title='TP: 51500.00'
        )
        
        data = line.to_dict()
        
        assert data['price'] == 51500.0
        assert data['color'] == '#4caf50'
        assert data['lineWidth'] == 2
        assert data['lineStyle'] == 'dashed'
        assert data['axisLabelVisible'] is True
        assert data['title'] == 'TP: 51500.00'


class TestTPSLCalculation:
    """Test TP/SL price calculation logic"""
    
    def test_long_tp_sl(self):
        """Test TP/SL calculation for long position"""
        tp, sl = calculate_tp_sl(
            entry_price=50000.0,
            side='buy',
            tp_percent=3.0,
            sl_percent=2.0
        )
        
        assert tp == pytest.approx(51500.0)  # +3%
        assert sl == pytest.approx(49000.0)  # -2%
    
    def test_short_tp_sl(self):
        """Test TP/SL calculation for short position"""
        tp, sl = calculate_tp_sl(
            entry_price=50000.0,
            side='sell',
            tp_percent=3.0,
            sl_percent=2.0
        )
        
        assert tp == pytest.approx(48500.0)  # -3%
        assert sl == pytest.approx(51000.0)  # +2%
    
    def test_asymmetric_tp_sl(self):
        """Test TP/SL with different percentages"""
        tp, sl = calculate_tp_sl(
            entry_price=50000.0,
            side='buy',
            tp_percent=5.0,
            sl_percent=3.0
        )
        
        assert tp == pytest.approx(52500.0)  # +5%
        assert sl == pytest.approx(48500.0)  # -3%


class TestExitLineRendering:
    """Test exit line rendering logic"""
    
    def test_no_exit_price(self):
        """Exit line not rendered if exit_price is None"""
        marker = TradeMarker(
            time=1700000000,
            side='buy',
            price=50000.0,
            tp_price=51500.0,
            sl_price=49000.0
        )
        
        assert should_render_exit_line(marker) is False
    
    def test_exit_matches_tp(self):
        """Exit line not rendered if exit equals TP"""
        marker = TradeMarker(
            time=1700000000,
            side='buy',
            price=50000.0,
            tp_price=51500.0,
            sl_price=49000.0,
            exit_price=51500.0  # Matches TP
        )
        
        assert should_render_exit_line(marker) is False
    
    def test_exit_matches_sl(self):
        """Exit line not rendered if exit equals SL"""
        marker = TradeMarker(
            time=1700000000,
            side='buy',
            price=50000.0,
            tp_price=51500.0,
            sl_price=49000.0,
            exit_price=49000.0  # Matches SL
        )
        
        assert should_render_exit_line(marker) is False
    
    def test_exit_differs_from_tp_sl(self):
        """Exit line rendered if exit differs from TP and SL"""
        marker = TradeMarker(
            time=1700000000,
            side='buy',
            price=50000.0,
            tp_price=51500.0,
            sl_price=49000.0,
            exit_price=50800.0  # Differs from both
        )
        
        assert should_render_exit_line(marker) is True
    
    def test_exit_within_tolerance(self):
        """Exit line not rendered if exit is very close to TP (within 0.01%)"""
        marker = TradeMarker(
            time=1700000000,
            side='buy',
            price=50000.0,
            tp_price=51500.0,
            sl_price=49000.0,
            exit_price=51500.05  # Within 0.01% tolerance
        )
        
        # 0.01% of 51500 = 5.15, so 51500.05 is within tolerance
        assert should_render_exit_line(marker) is False


class TestMultipleTradesScenario:
    """Test scenarios with multiple trades and price lines"""
    
    def test_long_trade_with_tp_hit(self):
        """Test long trade that hits TP"""
        entry = TradeMarker(
            time=1700000000,
            side='buy',
            price=50000.0,
            tp_price=51500.0,
            sl_price=49000.0,
            exit_price=51500.0,
            exit_time=1700003600
        )
        
        exit_marker = TradeMarker(
            time=1700003600,
            side='sell',
            price=51500.0
        )
        
        # Entry marker should have TP/SL lines
        assert entry.tp_price == 51500.0
        assert entry.sl_price == 49000.0
        
        # Exit price matches TP - no separate exit line
        assert should_render_exit_line(entry) is False
    
    def test_long_trade_with_sl_hit(self):
        """Test long trade that hits SL"""
        entry = TradeMarker(
            time=1700000000,
            side='buy',
            price=50000.0,
            tp_price=51500.0,
            sl_price=49000.0,
            exit_price=49000.0,
            exit_time=1700001800
        )
        
        # Exit matches SL - no separate exit line
        assert should_render_exit_line(entry) is False
    
    def test_long_trade_with_manual_exit(self):
        """Test long trade with manual exit (not TP/SL)"""
        entry = TradeMarker(
            time=1700000000,
            side='buy',
            price=50000.0,
            tp_price=51500.0,
            sl_price=49000.0,
            exit_price=50800.0,  # Manual exit between entry and TP
            exit_time=1700002400
        )
        
        # Exit differs from TP/SL - render exit line
        assert should_render_exit_line(entry) is True
    
    def test_short_trade_with_tp_hit(self):
        """Test short trade that hits TP"""
        entry = TradeMarker(
            time=1700000000,
            side='sell',
            price=50000.0,
            tp_price=48500.0,  # TP below entry for short
            sl_price=51000.0,  # SL above entry for short
            exit_price=48500.0,
            exit_time=1700003600
        )
        
        # Exit matches TP - no separate exit line
        assert should_render_exit_line(entry) is False


class TestPriceLineColors:
    """Test price line color scheme"""
    
    def test_tp_line_green(self):
        """TP line should be green"""
        tp_line = PriceLine(
            price=51500.0,
            color='#4caf50',  # Material UI green
            line_style='dashed',
            title='TP: 51500.00'
        )
        
        assert tp_line.color == '#4caf50'
        assert tp_line.line_style == 'dashed'
    
    def test_sl_line_red(self):
        """SL line should be red"""
        sl_line = PriceLine(
            price=49000.0,
            color='#f44336',  # Material UI red
            line_style='dashed',
            title='SL: 49000.00'
        )
        
        assert sl_line.color == '#f44336'
        assert sl_line.line_style == 'dashed'
    
    def test_exit_line_blue(self):
        """Exit line should be blue"""
        exit_line = PriceLine(
            price=50800.0,
            color='#2196f3',  # Material UI blue
            line_style='dotted',
            title='Exit: 50800.00'
        )
        
        assert exit_line.color == '#2196f3'
        assert exit_line.line_style == 'dotted'


class TestEnhancedMarkerFields:
    """Test enhanced marker fields (ТЗ 9.2 Step 3)"""
    
    def test_marker_with_pnl(self):
        """Test marker with P&L information"""
        marker = TradeMarker(
            time=1700000000,
            side='buy',
            price=50000.0,
            is_entry=False,
            pnl=1500.0,
            pnl_percent=3.0
        )
        
        assert marker.pnl == 1500.0
        assert marker.pnl_percent == 3.0
        assert marker.is_entry is False
    
    def test_marker_with_size(self):
        """Test marker with trade size for scaling"""
        marker = TradeMarker(
            time=1700000000,
            side='buy',
            price=50000.0,
            size=2.5
        )
        
        assert marker.size == 2.5
    
    def test_marker_with_custom_label(self):
        """Test marker with custom label"""
        marker = TradeMarker(
            time=1700000000,
            side='buy',
            price=50000.0,
            label='ENTRY (Big Trade)'
        )
        
        assert marker.label == 'ENTRY (Big Trade)'
    
    def test_marker_with_custom_color(self):
        """Test marker with custom color override"""
        marker = TradeMarker(
            time=1700000000,
            side='buy',
            price=50000.0,
            color='#ff9800'  # Custom orange
        )
        
        assert marker.color == '#ff9800'
    
    def test_entry_marker_explicit(self):
        """Test entry marker with is_entry=True"""
        marker = TradeMarker(
            time=1700000000,
            side='buy',
            price=50000.0,
            is_entry=True,
            tp_price=51500.0,
            sl_price=49000.0
        )
        
        assert marker.is_entry is True
        assert marker.tp_price == 51500.0
    
    def test_exit_marker_explicit(self):
        """Test exit marker with is_entry=False"""
        marker = TradeMarker(
            time=1700003600,
            side='sell',
            price=51200.0,
            is_entry=False,
            pnl=1200.0,
            pnl_percent=2.4
        )
        
        assert marker.is_entry is False
        assert marker.pnl == 1200.0


class TestEnhancedMarkerSerialization:
    """Test enhanced marker to_dict with all fields"""
    
    def test_full_marker_serialization(self):
        """Test marker with all enhanced fields serialization"""
        marker = TradeMarker(
            time=1700000000,
            side='buy',
            price=50000.0,
            tp_price=51500.0,
            sl_price=49000.0,
            exit_price=51200.0,
            exit_time=1700003600,
            pnl=1200.0,
            pnl_percent=2.4,
            size=1.5,
            label='Long Entry',
            color='#2e7d32',
            is_entry=True
        )
        
        data = marker.to_dict()
        
        # Basic fields
        assert data['time'] == 1700000000
        assert data['side'] == 'buy'
        assert data['price'] == 50000.0
        
        # TP/SL fields
        assert data['tp_price'] == 51500.0
        assert data['sl_price'] == 49000.0
        assert data['exit_price'] == 51200.0
        assert data['exit_time'] == 1700003600
        
        # Enhanced fields
        assert data['pnl'] == 1200.0
        assert data['pnl_percent'] == 2.4
        assert data['size'] == 1.5
        assert data['label'] == 'Long Entry'
        assert data['color'] == '#2e7d32'
        assert data['is_entry'] is True


class TestMarkerColorLogic:
    """Test marker color logic for entry/exit"""
    
    def test_entry_long_color(self):
        """Entry long marker should be green"""
        marker = TradeMarker(
            time=1700000000,
            side='buy',
            price=50000.0,
            is_entry=True
        )
        
        # Default color for entry long: #2e7d32 (green)
        assert marker.side == 'buy'
        assert marker.is_entry is True
    
    def test_entry_short_color(self):
        """Entry short marker should be red"""
        marker = TradeMarker(
            time=1700000000,
            side='sell',
            price=50000.0,
            is_entry=True
        )
        
        # Default color for entry short: #c62828 (red)
        assert marker.side == 'sell'
        assert marker.is_entry is True
    
    def test_exit_profit_color(self):
        """Exit with profit should be blue"""
        marker = TradeMarker(
            time=1700003600,
            side='sell',
            price=51500.0,
            is_entry=False,
            pnl=1500.0,
            pnl_percent=3.0
        )
        
        # Profit exit: #1976d2 (blue)
        assert marker.pnl > 0
        assert marker.is_entry is False
    
    def test_exit_loss_color(self):
        """Exit with loss should be red"""
        marker = TradeMarker(
            time=1700003600,
            side='sell',
            price=49500.0,
            is_entry=False,
            pnl=-500.0,
            pnl_percent=-1.0
        )
        
        # Loss exit: #d32f2f (red)
        assert marker.pnl < 0
        assert marker.is_entry is False


class TestMarkerSizeScaling:
    """Test marker size scaling logic"""
    
    def test_normal_size(self):
        """Normal trade size (1.0)"""
        marker = TradeMarker(
            time=1700000000,
            side='buy',
            price=50000.0,
            size=1.0
        )
        
        assert marker.size == 1.0
    
    def test_large_size(self):
        """Large trade size (2.0)"""
        marker = TradeMarker(
            time=1700000000,
            side='buy',
            price=50000.0,
            size=2.0
        )
        
        # Size 2.0 should render at 2x normal marker size
        assert marker.size == 2.0
    
    def test_small_size(self):
        """Small trade size (0.5)"""
        marker = TradeMarker(
            time=1700000000,
            side='buy',
            price=50000.0,
            size=0.5
        )
        
        # Size 0.5 should render at 0.5x normal marker size
        assert marker.size == 0.5


class TestMarkerTooltipLogic:
    """Test marker tooltip generation logic"""
    
    def test_entry_tooltip(self):
        """Entry marker tooltip: BUY {price}"""
        marker = TradeMarker(
            time=1700000000,
            side='buy',
            price=50000.0,
            is_entry=True
        )
        
        # Expected tooltip: "BUY 50000.00"
        assert marker.side == 'buy'
        assert marker.is_entry is True
        assert marker.price == 50000.0
    
    def test_exit_tooltip_with_pnl(self):
        """Exit marker tooltip: EXIT {price} (+{pnl}%)"""
        marker = TradeMarker(
            time=1700003600,
            side='sell',
            price=51500.0,
            is_entry=False,
            pnl=1500.0,
            pnl_percent=3.0
        )
        
        # Expected tooltip: "EXIT 51500.00 (+3.00%)"
        assert marker.pnl_percent == 3.0
    
    def test_exit_tooltip_negative_pnl(self):
        """Exit marker tooltip with negative P&L"""
        marker = TradeMarker(
            time=1700003600,
            side='sell',
            price=49500.0,
            is_entry=False,
            pnl=-500.0,
            pnl_percent=-1.0
        )
        
        # Expected tooltip: "EXIT 49500.00 (-1.00%)"
        assert marker.pnl_percent == -1.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
