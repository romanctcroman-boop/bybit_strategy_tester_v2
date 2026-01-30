"""
Universal Math Engine v2.4.0 - Advanced Visualization Module.

Provides comprehensive visualization capabilities for trading analysis:
- Equity curves and drawdown plots
- Performance heatmaps
- 3D optimization surfaces
- Correlation matrices
- Trade distribution charts
- Interactive dashboards

Author: Claude AI
Date: 2025-01-24
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Conditional imports for visualization libraries
try:
    import matplotlib.pyplot as plt  # noqa: F401
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    Figure = Any
    Axes = Any

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False


class ChartType(Enum):
    """Types of charts available."""

    LINE = "line"
    CANDLESTICK = "candlestick"
    BAR = "bar"
    HISTOGRAM = "histogram"
    SCATTER = "scatter"
    HEATMAP = "heatmap"
    SURFACE_3D = "surface_3d"
    PIE = "pie"
    AREA = "area"
    BOX = "box"
    VIOLIN = "violin"


class ColorScheme(Enum):
    """Color schemes for charts."""

    DEFAULT = "default"
    DARK = "dark"
    LIGHT = "light"
    TRADINGVIEW = "tradingview"
    BLOOMBERG = "bloomberg"
    PROFESSIONAL = "professional"


@dataclass
class ChartStyle:
    """Configuration for chart styling."""

    color_scheme: ColorScheme = ColorScheme.DEFAULT
    background_color: str = "#FFFFFF"
    grid_color: str = "#E0E0E0"
    text_color: str = "#333333"
    positive_color: str = "#26A69A"  # Green
    negative_color: str = "#EF5350"  # Red
    neutral_color: str = "#42A5F5"  # Blue
    font_family: str = "Arial"
    font_size: int = 12
    line_width: float = 1.5
    marker_size: int = 6
    grid_alpha: float = 0.3
    figure_width: int = 1200
    figure_height: int = 800

    def to_plotly_template(self) -> Dict[str, Any]:
        """Convert to Plotly template configuration."""
        return {
            "layout": {
                "paper_bgcolor": self.background_color,
                "plot_bgcolor": self.background_color,
                "font": {
                    "family": self.font_family,
                    "size": self.font_size,
                    "color": self.text_color,
                },
                "xaxis": {
                    "gridcolor": self.grid_color,
                    "gridwidth": 1,
                    "showgrid": True,
                },
                "yaxis": {
                    "gridcolor": self.grid_color,
                    "gridwidth": 1,
                    "showgrid": True,
                },
            }
        }

    def to_matplotlib_style(self) -> Dict[str, Any]:
        """Convert to Matplotlib style configuration."""
        return {
            "figure.facecolor": self.background_color,
            "axes.facecolor": self.background_color,
            "axes.edgecolor": self.grid_color,
            "axes.labelcolor": self.text_color,
            "xtick.color": self.text_color,
            "ytick.color": self.text_color,
            "grid.color": self.grid_color,
            "grid.alpha": self.grid_alpha,
            "font.family": self.font_family,
            "font.size": self.font_size,
            "lines.linewidth": self.line_width,
            "lines.markersize": self.marker_size,
        }


@dataclass
class TradeVisualization:
    """Data structure for trade visualization."""

    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    direction: str  # "long" or "short"
    pnl: float
    pnl_percent: float
    size: float

    @property
    def is_profitable(self) -> bool:
        """Check if trade was profitable."""
        return self.pnl > 0

    @property
    def duration_hours(self) -> float:
        """Get trade duration in hours."""
        return (self.exit_time - self.entry_time).total_seconds() / 3600


@dataclass
class EquityData:
    """Data structure for equity curve visualization."""

    timestamps: np.ndarray
    equity: np.ndarray
    drawdown: np.ndarray
    drawdown_pct: np.ndarray
    peak_equity: np.ndarray

    @classmethod
    def from_equity_series(
        cls, timestamps: np.ndarray, equity: np.ndarray
    ) -> "EquityData":
        """Create EquityData from raw equity series."""
        peak_equity = np.maximum.accumulate(equity)
        drawdown = peak_equity - equity
        drawdown_pct = np.where(peak_equity > 0, drawdown / peak_equity * 100, 0)

        return cls(
            timestamps=timestamps,
            equity=equity,
            drawdown=drawdown,
            drawdown_pct=drawdown_pct,
            peak_equity=peak_equity,
        )


# =============================================================================
# Base Chart Classes
# =============================================================================


class BaseChart(ABC):
    """Abstract base class for all charts."""

    def __init__(self, style: Optional[ChartStyle] = None):
        """
        Initialize chart.

        Args:
            style: Chart styling configuration
        """
        self.style = style or ChartStyle()
        self._data: Dict[str, Any] = {}
        self._title: str = ""
        self._xlabel: str = ""
        self._ylabel: str = ""

    @abstractmethod
    def render(self) -> Any:
        """Render the chart and return figure object."""
        pass

    def set_title(self, title: str) -> "BaseChart":
        """Set chart title."""
        self._title = title
        return self

    def set_labels(self, xlabel: str, ylabel: str) -> "BaseChart":
        """Set axis labels."""
        self._xlabel = xlabel
        self._ylabel = ylabel
        return self

    @abstractmethod
    def save(self, filepath: str) -> None:
        """Save chart to file."""
        pass

    @abstractmethod
    def to_html(self) -> str:
        """Export chart as HTML string."""
        pass


from abc import abstractmethod


class PlotlyChart(BaseChart):
    """Base class for Plotly-based charts."""

    def __init__(self, style: Optional[ChartStyle] = None):
        """Initialize Plotly chart."""
        super().__init__(style)
        self._fig: Optional[go.Figure] = None

    def render(self) -> go.Figure:
        """Render and return Plotly figure."""
        if not HAS_PLOTLY:
            raise ImportError("Plotly is required for this chart type")
        return self._fig

    def save(self, filepath: str) -> None:
        """Save chart to file."""
        if self._fig is not None:
            if filepath.endswith(".html"):
                self._fig.write_html(filepath)
            else:
                self._fig.write_image(filepath)

    def to_html(self) -> str:
        """Export chart as HTML string."""
        if self._fig is not None:
            return self._fig.to_html(include_plotlyjs="cdn")
        return ""

    def show(self) -> None:
        """Display the chart."""
        if self._fig is not None:
            self._fig.show()


class MatplotlibChart(BaseChart):
    """Base class for Matplotlib-based charts."""

    def __init__(self, style: Optional[ChartStyle] = None):
        """Initialize Matplotlib chart."""
        super().__init__(style)
        self._fig: Optional[Figure] = None
        self._axes: Optional[Axes] = None

    def render(self) -> Figure:
        """Render and return Matplotlib figure."""
        if not HAS_MATPLOTLIB:
            raise ImportError("Matplotlib is required for this chart type")
        return self._fig

    def save(self, filepath: str, dpi: int = 150) -> None:
        """Save chart to file."""
        if self._fig is not None:
            self._fig.savefig(filepath, dpi=dpi, bbox_inches="tight")

    def to_html(self) -> str:
        """Export chart as HTML (SVG embedded)."""
        import base64
        import io

        if self._fig is not None:
            buf = io.BytesIO()
            self._fig.savefig(buf, format="svg")
            buf.seek(0)
            svg_data = base64.b64encode(buf.read()).decode("utf-8")
            return f'<img src="data:image/svg+xml;base64,{svg_data}" />'
        return ""


# =============================================================================
# Trading Charts
# =============================================================================


class EquityCurveChart(PlotlyChart):
    """Equity curve visualization with drawdown."""

    def __init__(
        self,
        equity_data: EquityData,
        benchmark_equity: Optional[np.ndarray] = None,
        style: Optional[ChartStyle] = None,
    ):
        """
        Initialize equity curve chart.

        Args:
            equity_data: Equity curve data
            benchmark_equity: Optional benchmark comparison
            style: Chart styling
        """
        super().__init__(style)
        self.equity_data = equity_data
        self.benchmark_equity = benchmark_equity
        self._build_chart()

    def _build_chart(self) -> None:
        """Build the equity curve chart."""
        if not HAS_PLOTLY:
            return

        # Create subplots: equity on top, drawdown on bottom
        self._fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.7, 0.3],
            subplot_titles=("Equity Curve", "Drawdown"),
        )

        # Convert timestamps for plotting
        x_data = self.equity_data.timestamps

        # Equity curve
        self._fig.add_trace(
            go.Scatter(
                x=x_data,
                y=self.equity_data.equity,
                mode="lines",
                name="Equity",
                line=dict(color=self.style.neutral_color, width=self.style.line_width),
                fill="tozeroy",
                fillcolor="rgba(66, 165, 245, 0.1)",
            ),
            row=1,
            col=1,
        )

        # Peak equity line
        self._fig.add_trace(
            go.Scatter(
                x=x_data,
                y=self.equity_data.peak_equity,
                mode="lines",
                name="Peak Equity",
                line=dict(color=self.style.positive_color, width=1, dash="dot"),
            ),
            row=1,
            col=1,
        )

        # Benchmark if provided
        if self.benchmark_equity is not None:
            self._fig.add_trace(
                go.Scatter(
                    x=x_data,
                    y=self.benchmark_equity,
                    mode="lines",
                    name="Benchmark",
                    line=dict(color="#9E9E9E", width=1, dash="dash"),
                ),
                row=1,
                col=1,
            )

        # Drawdown area
        self._fig.add_trace(
            go.Scatter(
                x=x_data,
                y=-self.equity_data.drawdown_pct,
                mode="lines",
                name="Drawdown %",
                line=dict(color=self.style.negative_color, width=self.style.line_width),
                fill="tozeroy",
                fillcolor="rgba(239, 83, 80, 0.3)",
            ),
            row=2,
            col=1,
        )

        # Update layout
        self._fig.update_layout(
            title=self._title or "Equity Curve Analysis",
            height=self.style.figure_height,
            width=self.style.figure_width,
            showlegend=True,
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
            hovermode="x unified",
        )

        self._fig.update_yaxes(title_text="Equity ($)", row=1, col=1)
        self._fig.update_yaxes(title_text="Drawdown (%)", row=2, col=1)
        self._fig.update_xaxes(title_text="Date", row=2, col=1)


class TradeScatterChart(PlotlyChart):
    """Trade entry/exit scatter visualization."""

    def __init__(
        self,
        trades: List[TradeVisualization],
        prices: np.ndarray,
        timestamps: np.ndarray,
        style: Optional[ChartStyle] = None,
    ):
        """
        Initialize trade scatter chart.

        Args:
            trades: List of trade visualizations
            prices: Price series for background
            timestamps: Timestamps for price series
            style: Chart styling
        """
        super().__init__(style)
        self.trades = trades
        self.prices = prices
        self.timestamps = timestamps
        self._build_chart()

    def _build_chart(self) -> None:
        """Build the trade scatter chart."""
        if not HAS_PLOTLY:
            return

        self._fig = go.Figure()

        # Price line
        self._fig.add_trace(
            go.Scatter(
                x=self.timestamps,
                y=self.prices,
                mode="lines",
                name="Price",
                line=dict(color="#9E9E9E", width=1),
            )
        )

        # Separate winning and losing trades
        for trade in self.trades:
            color = (
                self.style.positive_color
                if trade.is_profitable
                else self.style.negative_color
            )
            symbol = "triangle-up" if trade.direction == "long" else "triangle-down"

            # Entry marker
            self._fig.add_trace(
                go.Scatter(
                    x=[trade.entry_time],
                    y=[trade.entry_price],
                    mode="markers",
                    marker=dict(color=color, size=10, symbol=symbol),
                    name=f"Entry ({trade.direction})",
                    showlegend=False,
                    hovertemplate=(
                        f"<b>Entry</b><br>"
                        f"Time: %{{x}}<br>"
                        f"Price: %{{y:.2f}}<br>"
                        f"Direction: {trade.direction}<br>"
                        f"Size: {trade.size:.4f}"
                    ),
                )
            )

            # Exit marker
            exit_symbol = "x" if not trade.is_profitable else "star"
            self._fig.add_trace(
                go.Scatter(
                    x=[trade.exit_time],
                    y=[trade.exit_price],
                    mode="markers",
                    marker=dict(color=color, size=10, symbol=exit_symbol),
                    name="Exit",
                    showlegend=False,
                    hovertemplate=(
                        f"<b>Exit</b><br>"
                        f"Time: %{{x}}<br>"
                        f"Price: %{{y:.2f}}<br>"
                        f"PnL: ${trade.pnl:.2f} ({trade.pnl_percent:.2f}%)"
                    ),
                )
            )

            # Connect entry and exit
            self._fig.add_trace(
                go.Scatter(
                    x=[trade.entry_time, trade.exit_time],
                    y=[trade.entry_price, trade.exit_price],
                    mode="lines",
                    line=dict(color=color, width=1, dash="dot"),
                    showlegend=False,
                    hoverinfo="skip",
                )
            )

        self._fig.update_layout(
            title=self._title or "Trade Analysis",
            height=self.style.figure_height,
            width=self.style.figure_width,
            showlegend=True,
            hovermode="closest",
        )


class PerformanceHeatmap(PlotlyChart):
    """Parameter optimization heatmap."""

    def __init__(
        self,
        x_values: np.ndarray,
        y_values: np.ndarray,
        z_values: np.ndarray,
        x_label: str = "Parameter 1",
        y_label: str = "Parameter 2",
        z_label: str = "Performance",
        style: Optional[ChartStyle] = None,
    ):
        """
        Initialize performance heatmap.

        Args:
            x_values: X-axis parameter values
            y_values: Y-axis parameter values
            z_values: Performance metric values (2D array)
            x_label: Label for x-axis
            y_label: Label for y-axis
            z_label: Label for colorbar
            style: Chart styling
        """
        super().__init__(style)
        self.x_values = x_values
        self.y_values = y_values
        self.z_values = z_values
        self.x_label = x_label
        self.y_label = y_label
        self.z_label = z_label
        self._build_chart()

    def _build_chart(self) -> None:
        """Build the heatmap chart."""
        if not HAS_PLOTLY:
            return

        # Find best parameter combination
        best_idx = np.unravel_index(np.argmax(self.z_values), self.z_values.shape)
        best_x = self.x_values[best_idx[1]]
        best_y = self.y_values[best_idx[0]]
        best_val = self.z_values[best_idx]

        self._fig = go.Figure()

        # Heatmap
        self._fig.add_trace(
            go.Heatmap(
                x=self.x_values,
                y=self.y_values,
                z=self.z_values,
                colorscale="RdYlGn",
                colorbar=dict(title=self.z_label),
                hovertemplate=(
                    f"{self.x_label}: %{{x}}<br>"
                    f"{self.y_label}: %{{y}}<br>"
                    f"{self.z_label}: %{{z:.4f}}<extra></extra>"
                ),
            )
        )

        # Mark best point
        self._fig.add_trace(
            go.Scatter(
                x=[best_x],
                y=[best_y],
                mode="markers",
                marker=dict(
                    color="white",
                    size=15,
                    symbol="star",
                    line=dict(color="black", width=2),
                ),
                name=f"Best: {best_val:.4f}",
                hovertemplate=(
                    f"<b>Best Parameters</b><br>"
                    f"{self.x_label}: {best_x}<br>"
                    f"{self.y_label}: {best_y}<br>"
                    f"{self.z_label}: {best_val:.4f}<extra></extra>"
                ),
            )
        )

        self._fig.update_layout(
            title=self._title or "Parameter Optimization Heatmap",
            xaxis_title=self.x_label,
            yaxis_title=self.y_label,
            height=self.style.figure_height,
            width=self.style.figure_width,
        )


class Surface3DChart(PlotlyChart):
    """3D surface visualization for optimization."""

    def __init__(
        self,
        x_values: np.ndarray,
        y_values: np.ndarray,
        z_values: np.ndarray,
        x_label: str = "Parameter 1",
        y_label: str = "Parameter 2",
        z_label: str = "Performance",
        style: Optional[ChartStyle] = None,
    ):
        """
        Initialize 3D surface chart.

        Args:
            x_values: X-axis parameter values
            y_values: Y-axis parameter values
            z_values: Performance metric values (2D array)
            x_label: Label for x-axis
            y_label: Label for y-axis
            z_label: Label for z-axis
            style: Chart styling
        """
        super().__init__(style)
        self.x_values = x_values
        self.y_values = y_values
        self.z_values = z_values
        self.x_label = x_label
        self.y_label = y_label
        self.z_label = z_label
        self._build_chart()

    def _build_chart(self) -> None:
        """Build the 3D surface chart."""
        if not HAS_PLOTLY:
            return

        # Create meshgrid
        x_mesh, y_mesh = np.meshgrid(self.x_values, self.y_values)

        self._fig = go.Figure()

        # Surface
        self._fig.add_trace(
            go.Surface(
                x=x_mesh,
                y=y_mesh,
                z=self.z_values,
                colorscale="Viridis",
                colorbar=dict(title=self.z_label),
                contours=dict(z=dict(show=True, usecolormap=True, project_z=True)),
            )
        )

        # Find and mark best point
        best_idx = np.unravel_index(np.argmax(self.z_values), self.z_values.shape)
        best_x = self.x_values[best_idx[1]]
        best_y = self.y_values[best_idx[0]]
        best_z = self.z_values[best_idx]

        self._fig.add_trace(
            go.Scatter3d(
                x=[best_x],
                y=[best_y],
                z=[best_z],
                mode="markers",
                marker=dict(color="red", size=10, symbol="diamond"),
                name=f"Best: {best_z:.4f}",
            )
        )

        self._fig.update_layout(
            title=self._title or "3D Optimization Surface",
            scene=dict(
                xaxis_title=self.x_label,
                yaxis_title=self.y_label,
                zaxis_title=self.z_label,
                camera=dict(eye=dict(x=1.5, y=1.5, z=1.2)),
            ),
            height=self.style.figure_height,
            width=self.style.figure_width,
        )


class CorrelationMatrixChart(PlotlyChart):
    """Correlation matrix heatmap."""

    def __init__(
        self,
        correlation_matrix: np.ndarray,
        labels: List[str],
        style: Optional[ChartStyle] = None,
    ):
        """
        Initialize correlation matrix chart.

        Args:
            correlation_matrix: Correlation matrix (NxN)
            labels: Labels for each variable
            style: Chart styling
        """
        super().__init__(style)
        self.correlation_matrix = correlation_matrix
        self.labels = labels
        self._build_chart()

    def _build_chart(self) -> None:
        """Build the correlation matrix chart."""
        if not HAS_PLOTLY:
            return

        # Create text annotations
        text = np.round(self.correlation_matrix, 2).astype(str)

        self._fig = go.Figure()

        self._fig.add_trace(
            go.Heatmap(
                x=self.labels,
                y=self.labels,
                z=self.correlation_matrix,
                colorscale="RdBu",
                zmid=0,
                colorbar=dict(title="Correlation"),
                text=text,
                texttemplate="%{text}",
                textfont={"size": 10},
            )
        )

        self._fig.update_layout(
            title=self._title or "Correlation Matrix",
            height=max(400, len(self.labels) * 50),
            width=max(400, len(self.labels) * 50),
            xaxis=dict(tickangle=45),
            yaxis=dict(autorange="reversed"),
        )


class TradeDistributionChart(PlotlyChart):
    """Trade P&L distribution visualization."""

    def __init__(self, pnl_values: np.ndarray, style: Optional[ChartStyle] = None):
        """
        Initialize trade distribution chart.

        Args:
            pnl_values: Array of trade P&L values
            style: Chart styling
        """
        super().__init__(style)
        self.pnl_values = pnl_values
        self._build_chart()

    def _build_chart(self) -> None:
        """Build the distribution chart."""
        if not HAS_PLOTLY:
            return

        # Separate winners and losers
        winners = self.pnl_values[self.pnl_values > 0]
        losers = self.pnl_values[self.pnl_values < 0]

        self._fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=(
                "P&L Distribution",
                "Cumulative P&L",
                "Win/Loss Distribution",
                "P&L by Trade Number",
            ),
        )

        # Histogram
        self._fig.add_trace(
            go.Histogram(
                x=self.pnl_values,
                nbinsx=50,
                marker_color=np.where(
                    self.pnl_values > 0,
                    self.style.positive_color,
                    self.style.negative_color,
                ).tolist()
                if len(self.pnl_values) < 100
                else self.style.neutral_color,
                name="P&L",
            ),
            row=1,
            col=1,
        )

        # Add normal distribution fit line
        mean_pnl = np.mean(self.pnl_values)
        std_pnl = np.std(self.pnl_values)
        x_range = np.linspace(min(self.pnl_values), max(self.pnl_values), 100)
        normal_pdf = (
            1
            / (std_pnl * np.sqrt(2 * np.pi))
            * np.exp(-0.5 * ((x_range - mean_pnl) / std_pnl) ** 2)
        )
        # Scale to histogram
        normal_pdf = (
            normal_pdf
            * len(self.pnl_values)
            * (max(self.pnl_values) - min(self.pnl_values))
            / 50
        )

        self._fig.add_trace(
            go.Scatter(
                x=x_range,
                y=normal_pdf,
                mode="lines",
                name="Normal Fit",
                line=dict(color="red", dash="dash"),
            ),
            row=1,
            col=1,
        )

        # Cumulative P&L
        cumulative_pnl = np.cumsum(self.pnl_values)
        self._fig.add_trace(
            go.Scatter(
                x=list(range(len(cumulative_pnl))),
                y=cumulative_pnl,
                mode="lines",
                name="Cumulative P&L",
                line=dict(color=self.style.neutral_color),
            ),
            row=1,
            col=2,
        )

        # Win/Loss pie chart
        win_count = len(winners)
        loss_count = len(losers)
        self._fig.add_trace(
            go.Pie(
                labels=["Winners", "Losers"],
                values=[win_count, loss_count],
                marker_colors=[self.style.positive_color, self.style.negative_color],
                textinfo="percent+value",
            ),
            row=2,
            col=1,
        )

        # P&L by trade number
        colors = [
            self.style.positive_color if pnl > 0 else self.style.negative_color
            for pnl in self.pnl_values
        ]
        self._fig.add_trace(
            go.Bar(
                x=list(range(len(self.pnl_values))),
                y=self.pnl_values,
                marker_color=colors,
                name="Trade P&L",
            ),
            row=2,
            col=2,
        )

        self._fig.update_layout(
            title=self._title or "Trade Distribution Analysis",
            height=self.style.figure_height,
            width=self.style.figure_width,
            showlegend=True,
        )


class MonthlyReturnsHeatmap(PlotlyChart):
    """Monthly returns heatmap visualization."""

    def __init__(
        self,
        returns: np.ndarray,
        timestamps: np.ndarray,
        style: Optional[ChartStyle] = None,
    ):
        """
        Initialize monthly returns heatmap.

        Args:
            returns: Array of returns
            timestamps: Array of timestamps
            style: Chart styling
        """
        super().__init__(style)
        self.returns = returns
        self.timestamps = timestamps
        self._build_chart()

    def _build_chart(self) -> None:
        """Build the monthly returns heatmap."""
        if not HAS_PLOTLY:
            return

        # Convert to monthly returns
        monthly_data: Dict[Tuple[int, int], float] = {}

        for ret, ts in zip(self.returns, self.timestamps):
            if isinstance(ts, (int, float)):
                dt = datetime.fromtimestamp(ts)
            else:
                dt = ts

            key = (dt.year, dt.month)
            if key not in monthly_data:
                monthly_data[key] = 1.0
            monthly_data[key] *= 1 + ret

        # Convert to percentage returns
        for key in monthly_data:
            monthly_data[key] = (monthly_data[key] - 1) * 100

        if not monthly_data:
            self._fig = go.Figure()
            return

        # Get unique years and months
        years = sorted(set(k[0] for k in monthly_data.keys()))
        months = list(range(1, 13))
        month_names = [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ]

        # Create matrix
        z_data = []
        for year in years:
            row = []
            for month in months:
                value = monthly_data.get((year, month), np.nan)
                row.append(value)
            z_data.append(row)

        z_data = np.array(z_data)

        # Create annotations
        annotations = []
        for i, year in enumerate(years):
            for j, month in enumerate(months):
                value = z_data[i, j]
                if not np.isnan(value):
                    annotations.append(
                        dict(
                            x=month_names[j],
                            y=str(year),
                            text=f"{value:.1f}%",
                            showarrow=False,
                            font=dict(
                                color="white" if abs(value) > 5 else "black", size=10
                            ),
                        )
                    )

        self._fig = go.Figure()

        self._fig.add_trace(
            go.Heatmap(
                x=month_names,
                y=[str(y) for y in years],
                z=z_data,
                colorscale="RdYlGn",
                zmid=0,
                colorbar=dict(title="Return %"),
            )
        )

        self._fig.update_layout(
            title=self._title or "Monthly Returns Heatmap",
            annotations=annotations,
            height=max(400, len(years) * 60),
            width=self.style.figure_width,
            xaxis_title="Month",
            yaxis_title="Year",
        )


# =============================================================================
# Dashboard Builder
# =============================================================================


@dataclass
class DashboardPanel:
    """Configuration for a dashboard panel."""

    chart: BaseChart
    row: int
    col: int
    rowspan: int = 1
    colspan: int = 1


class TradingDashboard:
    """Comprehensive trading dashboard builder."""

    def __init__(
        self, title: str = "Trading Dashboard", style: Optional[ChartStyle] = None
    ):
        """
        Initialize trading dashboard.

        Args:
            title: Dashboard title
            style: Dashboard styling
        """
        self.title = title
        self.style = style or ChartStyle()
        self._panels: List[DashboardPanel] = []
        self._rows = 1
        self._cols = 1

    def add_panel(
        self, chart: BaseChart, row: int, col: int, rowspan: int = 1, colspan: int = 1
    ) -> "TradingDashboard":
        """
        Add a chart panel to the dashboard.

        Args:
            chart: Chart to add
            row: Row position (1-indexed)
            col: Column position (1-indexed)
            rowspan: Number of rows to span
            colspan: Number of columns to span

        Returns:
            Self for chaining
        """
        self._panels.append(
            DashboardPanel(
                chart=chart, row=row, col=col, rowspan=rowspan, colspan=colspan
            )
        )

        self._rows = max(self._rows, row + rowspan - 1)
        self._cols = max(self._cols, col + colspan - 1)

        return self

    def build(self) -> go.Figure:
        """Build and return the dashboard figure."""
        if not HAS_PLOTLY:
            raise ImportError("Plotly is required for dashboards")

        # Create subplot grid
        specs = []
        for _ in range(self._rows):
            row_specs = []
            for _ in range(self._cols):
                row_specs.append({})
            specs.append(row_specs)

        # Mark spans
        for panel in self._panels:
            specs[panel.row - 1][panel.col - 1] = {
                "rowspan": panel.rowspan,
                "colspan": panel.colspan,
            }
            # Mark spanned cells as None
            for r in range(panel.row - 1, panel.row - 1 + panel.rowspan):
                for c in range(panel.col - 1, panel.col - 1 + panel.colspan):
                    if r != panel.row - 1 or c != panel.col - 1:
                        specs[r][c] = None

        fig = make_subplots(
            rows=self._rows,
            cols=self._cols,
            specs=specs,
            subplot_titles=[
                panel.chart._title or f"Panel {i + 1}"
                for i, panel in enumerate(self._panels)
            ],
        )

        # Add traces from each panel
        for panel in self._panels:
            panel_fig = panel.chart.render()
            if panel_fig is not None and hasattr(panel_fig, "data"):
                for trace in panel_fig.data:
                    fig.add_trace(trace, row=panel.row, col=panel.col)

        fig.update_layout(
            title=self.title,
            height=self.style.figure_height * self._rows // 2,
            width=self.style.figure_width,
            showlegend=True,
        )

        return fig

    def to_html(self) -> str:
        """Export dashboard as HTML."""
        fig = self.build()
        return fig.to_html(include_plotlyjs="cdn")

    def save(self, filepath: str) -> None:
        """Save dashboard to file."""
        fig = self.build()
        if filepath.endswith(".html"):
            fig.write_html(filepath)
        else:
            fig.write_image(filepath)


# =============================================================================
# Quick Visualization Functions
# =============================================================================


def plot_equity_curve(
    timestamps: np.ndarray,
    equity: np.ndarray,
    title: str = "Equity Curve",
    show: bool = True,
) -> EquityCurveChart:
    """
    Quick function to plot equity curve.

    Args:
        timestamps: Array of timestamps
        equity: Array of equity values
        title: Chart title
        show: Whether to display immediately

    Returns:
        EquityCurveChart instance
    """
    equity_data = EquityData.from_equity_series(timestamps, equity)
    chart = EquityCurveChart(equity_data)
    chart.set_title(title)

    if show and HAS_PLOTLY:
        chart.show()

    return chart


def plot_optimization_heatmap(
    param1_values: np.ndarray,
    param2_values: np.ndarray,
    performance: np.ndarray,
    param1_name: str = "Parameter 1",
    param2_name: str = "Parameter 2",
    metric_name: str = "Sharpe Ratio",
    title: str = "Parameter Optimization",
    show: bool = True,
) -> PerformanceHeatmap:
    """
    Quick function to plot optimization heatmap.

    Args:
        param1_values: First parameter values
        param2_values: Second parameter values
        performance: Performance matrix
        param1_name: Name of first parameter
        param2_name: Name of second parameter
        metric_name: Name of performance metric
        title: Chart title
        show: Whether to display immediately

    Returns:
        PerformanceHeatmap instance
    """
    chart = PerformanceHeatmap(
        x_values=param1_values,
        y_values=param2_values,
        z_values=performance,
        x_label=param1_name,
        y_label=param2_name,
        z_label=metric_name,
    )
    chart.set_title(title)

    if show and HAS_PLOTLY:
        chart.show()

    return chart


def plot_trade_distribution(
    pnl_values: np.ndarray, title: str = "Trade Distribution", show: bool = True
) -> TradeDistributionChart:
    """
    Quick function to plot trade distribution.

    Args:
        pnl_values: Array of trade P&L values
        title: Chart title
        show: Whether to display immediately

    Returns:
        TradeDistributionChart instance
    """
    chart = TradeDistributionChart(pnl_values)
    chart.set_title(title)

    if show and HAS_PLOTLY:
        chart.show()

    return chart


def plot_correlation_matrix(
    data: np.ndarray,
    labels: List[str],
    title: str = "Correlation Matrix",
    show: bool = True,
) -> CorrelationMatrixChart:
    """
    Quick function to plot correlation matrix.

    Args:
        data: Data matrix (columns are variables)
        labels: Variable labels
        title: Chart title
        show: Whether to display immediately

    Returns:
        CorrelationMatrixChart instance
    """
    # Calculate correlation matrix
    corr_matrix = np.corrcoef(data.T)

    chart = CorrelationMatrixChart(corr_matrix, labels)
    chart.set_title(title)

    if show and HAS_PLOTLY:
        chart.show()

    return chart


def create_backtest_report(
    equity: np.ndarray,
    timestamps: np.ndarray,
    trades: List[TradeVisualization],
    prices: np.ndarray,
    title: str = "Backtest Report",
) -> TradingDashboard:
    """
    Create comprehensive backtest report dashboard.

    Args:
        equity: Equity curve values
        timestamps: Timestamps
        trades: List of trades
        prices: Price series
        title: Report title

    Returns:
        TradingDashboard instance
    """
    # Create individual charts
    equity_data = EquityData.from_equity_series(timestamps, equity)
    equity_chart = EquityCurveChart(equity_data)
    equity_chart.set_title("Equity Curve")

    trade_scatter = TradeScatterChart(trades, prices, timestamps)
    trade_scatter.set_title("Trade Entry/Exit Points")

    pnl_values = np.array([t.pnl for t in trades])
    distribution_chart = TradeDistributionChart(pnl_values)
    distribution_chart.set_title("P&L Distribution")

    # Build dashboard
    dashboard = TradingDashboard(title=title)
    dashboard.add_panel(equity_chart, row=1, col=1, colspan=2)
    dashboard.add_panel(trade_scatter, row=2, col=1)
    dashboard.add_panel(distribution_chart, row=2, col=2)

    return dashboard


# =============================================================================
# Export Utilities
# =============================================================================


def export_charts_to_html(
    charts: List[BaseChart], filepath: str, title: str = "Trading Charts"
) -> None:
    """
    Export multiple charts to a single HTML file.

    Args:
        charts: List of charts to export
        filepath: Output HTML file path
        title: HTML page title
    """
    html_parts = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        f"<title>{title}</title>",
        '<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>',
        "<style>",
        "body { font-family: Arial, sans-serif; margin: 20px; }",
        ".chart-container { margin-bottom: 40px; }",
        "</style>",
        "</head>",
        "<body>",
        f"<h1>{title}</h1>",
    ]

    for _i, chart in enumerate(charts):
        html_parts.append('<div class="chart-container">')
        html_parts.append(chart.to_html())
        html_parts.append("</div>")

    html_parts.extend(["</body>", "</html>"])

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(html_parts))


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Enums
    "ChartType",
    "ColorScheme",
    # Data classes
    "ChartStyle",
    "TradeVisualization",
    "EquityData",
    "DashboardPanel",
    # Base classes
    "BaseChart",
    "PlotlyChart",
    "MatplotlibChart",
    # Chart classes
    "EquityCurveChart",
    "TradeScatterChart",
    "PerformanceHeatmap",
    "Surface3DChart",
    "CorrelationMatrixChart",
    "TradeDistributionChart",
    "MonthlyReturnsHeatmap",
    # Dashboard
    "TradingDashboard",
    # Quick functions
    "plot_equity_curve",
    "plot_optimization_heatmap",
    "plot_trade_distribution",
    "plot_correlation_matrix",
    "create_backtest_report",
    # Utilities
    "export_charts_to_html",
    # Flags
    "HAS_MATPLOTLIB",
    "HAS_PLOTLY",
]
