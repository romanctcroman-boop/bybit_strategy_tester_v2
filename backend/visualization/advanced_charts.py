"""
Advanced Chart Visualizations (ТЗ 3.7.2)

Creates professional-grade charts for backtest analysis:
- Equity curve with drawdown overlay
- PnL distribution histograms  
- Parameter heatmaps for optimization results

Uses Plotly for interactive, web-ready visualizations.
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, List, Optional, Union
import logging

logger = logging.getLogger(__name__)


def create_equity_curve(
    equity_data: Union[pd.Series, pd.DataFrame],
    title: str = "Equity Curve",
    show_drawdown: bool = True,
    height: int = 600,
) -> go.Figure:
    """
    Create equity curve with optional drawdown overlay.
    
    Args:
        equity_data: Series or DataFrame with timestamp index and equity values
                    If DataFrame, expects 'equity' column
        title: Chart title
        show_drawdown: Whether to show drawdown on secondary subplot
        height: Chart height in pixels
        
    Returns:
        Plotly Figure object
        
    Example:
        >>> equity = pd.Series([100, 105, 103, 108, 110], 
        ...                    index=pd.date_range('2025-01-01', periods=5))
        >>> fig = create_equity_curve(equity, show_drawdown=True)
        >>> fig.show()
    """
    logger.info(f"Creating equity curve: {title}")
    
    # Convert to Series if DataFrame
    if isinstance(equity_data, pd.DataFrame):
        if 'equity' not in equity_data.columns:
            raise ValueError("DataFrame must have 'equity' column")
        equity = equity_data['equity']
    else:
        equity = equity_data
    
    # Calculate drawdown
    cummax = equity.cummax()
    drawdown = (equity - cummax) / cummax * 100
    
    # Create subplots if showing drawdown
    if show_drawdown:
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            subplot_titles=(title, 'Drawdown (%)'),
            row_heights=[0.7, 0.3],
        )
        
        # Equity curve
        fig.add_trace(
            go.Scatter(
                x=equity.index,
                y=equity.values,
                name='Equity',
                line=dict(color='#2E86AB', width=2),
                fill='tozeroy',
                fillcolor='rgba(46, 134, 171, 0.1)',
            ),
            row=1, col=1
        )
        
        # Drawdown
        fig.add_trace(
            go.Scatter(
                x=drawdown.index,
                y=drawdown.values,
                name='Drawdown',
                line=dict(color='#E63946', width=1.5),
                fill='tozeroy',
                fillcolor='rgba(230, 57, 70, 0.2)',
            ),
            row=2, col=1
        )
        
        # Update axes
        fig.update_xaxes(title_text="Time", row=2, col=1)
        fig.update_yaxes(title_text="Equity ($)", row=1, col=1)
        fig.update_yaxes(title_text="Drawdown (%)", row=2, col=1)
        
    else:
        # Single plot
        fig = go.Figure()
        
        fig.add_trace(
            go.Scatter(
                x=equity.index,
                y=equity.values,
                name='Equity',
                line=dict(color='#2E86AB', width=2),
                fill='tozeroy',
                fillcolor='rgba(46, 134, 171, 0.1)',
            )
        )
        
        fig.update_xaxes(title_text="Time")
        fig.update_yaxes(title_text="Equity ($)")
        fig.update_layout(title=title)
    
    # Common layout settings
    fig.update_layout(
        height=height,
        hovermode='x unified',
        showlegend=True,
        template='plotly_white',
        margin=dict(l=60, r=30, t=80, b=50),
    )
    
    logger.info(f"Equity curve created: {len(equity)} points")
    return fig


def create_drawdown_overlay(
    equity_data: Union[pd.Series, pd.DataFrame],
    title: str = "Equity & Drawdown Analysis",
    height: int = 600,
) -> go.Figure:
    """
    Create equity curve with drawdown shown as overlay on same chart.
    
    Args:
        equity_data: Series or DataFrame with timestamp index and equity values
        title: Chart title
        height: Chart height in pixels
        
    Returns:
        Plotly Figure object with dual y-axes
    """
    logger.info(f"Creating drawdown overlay: {title}")
    
    # Convert to Series if DataFrame
    if isinstance(equity_data, pd.DataFrame):
        if 'equity' not in equity_data.columns:
            raise ValueError("DataFrame must have 'equity' column")
        equity = equity_data['equity']
    else:
        equity = equity_data
    
    # Calculate drawdown
    cummax = equity.cummax()
    drawdown = (equity - cummax) / cummax * 100
    
    # Create figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Equity curve on primary y-axis
    fig.add_trace(
        go.Scatter(
            x=equity.index,
            y=equity.values,
            name='Equity',
            line=dict(color='#2E86AB', width=2.5),
        ),
        secondary_y=False,
    )
    
    # Drawdown on secondary y-axis
    fig.add_trace(
        go.Scatter(
            x=drawdown.index,
            y=drawdown.values,
            name='Drawdown',
            line=dict(color='#E63946', width=1.5, dash='dot'),
            fill='tozeroy',
            fillcolor='rgba(230, 57, 70, 0.15)',
        ),
        secondary_y=True,
    )
    
    # Update axes
    fig.update_xaxes(title_text="Time")
    fig.update_yaxes(title_text="Equity ($)", secondary_y=False)
    fig.update_yaxes(title_text="Drawdown (%)", secondary_y=True)
    
    # Layout
    fig.update_layout(
        title=title,
        height=height,
        hovermode='x unified',
        showlegend=True,
        template='plotly_white',
        margin=dict(l=60, r=60, t=80, b=50),
    )
    
    logger.info(f"Drawdown overlay created: {len(equity)} points")
    return fig


def create_pnl_distribution(
    trades: Union[pd.DataFrame, List[float]],
    pnl_column: str = 'pnl',
    title: str = "PnL Distribution",
    bins: int = 30,
    height: int = 500,
) -> go.Figure:
    """
    Create PnL distribution histogram with statistics overlay.
    
    Args:
        trades: DataFrame with trade data or list of PnL values
        pnl_column: Column name for PnL values (if DataFrame)
        title: Chart title
        bins: Number of histogram bins
        height: Chart height in pixels
        
    Returns:
        Plotly Figure object
        
    Example:
        >>> trades = pd.DataFrame({'pnl': [100, -50, 75, 200, -25, 150]})
        >>> fig = create_pnl_distribution(trades)
        >>> fig.show()
    """
    logger.info(f"Creating PnL distribution: {title}")
    
    # Extract PnL values
    if isinstance(trades, pd.DataFrame):
        if pnl_column not in trades.columns:
            raise ValueError(f"DataFrame must have '{pnl_column}' column")
        pnl_values = trades[pnl_column].dropna().values
    else:
        pnl_values = np.array(trades)
    
    if len(pnl_values) == 0:
        raise ValueError("No PnL values provided")
    
    # Calculate statistics
    mean_pnl = np.mean(pnl_values)
    median_pnl = np.median(pnl_values)
    std_pnl = np.std(pnl_values)
    
    # Create histogram
    fig = go.Figure()
    
    fig.add_trace(
        go.Histogram(
            x=pnl_values,
            nbinsx=bins,
            name='PnL Distribution',
            marker=dict(
                color=pnl_values,
                colorscale=[[0, '#E63946'], [0.5, '#F1FAEE'], [1, '#2E86AB']],
                line=dict(color='#1D3557', width=1),
            ),
            hovertemplate='PnL: %{x:.2f}<br>Count: %{y}<extra></extra>',
        )
    )
    
    # Add mean line
    fig.add_vline(
        x=mean_pnl,
        line_dash="dash",
        line_color="#457B9D",
        annotation_text=f"Mean: ${mean_pnl:.2f}",
        annotation_position="top",
    )
    
    # Add median line
    fig.add_vline(
        x=median_pnl,
        line_dash="dot",
        line_color="#A8DADC",
        annotation_text=f"Median: ${median_pnl:.2f}",
        annotation_position="bottom",
    )
    
    # Add zero line
    fig.add_vline(
        x=0,
        line_dash="solid",
        line_color="black",
        line_width=1,
    )
    
    # Layout
    fig.update_layout(
        title=title,
        xaxis_title="PnL ($)",
        yaxis_title="Frequency",
        height=height,
        showlegend=False,
        template='plotly_white',
        margin=dict(l=60, r=30, t=100, b=50),
        annotations=[
            dict(
                text=f"Stats: Mean=${mean_pnl:.2f}, Median=${median_pnl:.2f}, StdDev=${std_pnl:.2f}",
                xref="paper", yref="paper",
                x=0.5, y=1.05,
                showarrow=False,
                font=dict(size=12, color='#1D3557'),
            )
        ]
    )
    
    logger.info(f"PnL distribution created: {len(pnl_values)} trades, mean=${mean_pnl:.2f}")
    return fig


def create_parameter_heatmap(
    optimization_results: pd.DataFrame,
    param_x: str,
    param_y: str,
    metric: str = 'total_return',
    title: Optional[str] = None,
    height: int = 600,
    width: int = 800,
) -> go.Figure:
    """
    Create heatmap for optimization parameter analysis.
    
    Args:
        optimization_results: DataFrame with columns [param_x, param_y, metric]
        param_x: Parameter name for x-axis
        param_y: Parameter name for y-axis
        metric: Metric to visualize (e.g., 'total_return', 'sharpe_ratio')
        title: Chart title (auto-generated if None)
        height: Chart height in pixels
        width: Chart width in pixels
        
    Returns:
        Plotly Figure object
        
    Example:
        >>> results = pd.DataFrame({
        ...     'ma_fast': [5, 5, 10, 10],
        ...     'ma_slow': [20, 30, 20, 30],
        ...     'total_return': [0.05, 0.08, 0.12, 0.06],
        ... })
        >>> fig = create_parameter_heatmap(results, 'ma_fast', 'ma_slow', 'total_return')
        >>> fig.show()
    """
    logger.info(f"Creating parameter heatmap: {param_x} vs {param_y} -> {metric}")
    
    # Validate columns
    required_cols = [param_x, param_y, metric]
    missing_cols = [col for col in required_cols if col not in optimization_results.columns]
    if missing_cols:
        raise ValueError(f"Missing columns: {missing_cols}")
    
    # Pivot data for heatmap
    heatmap_data = optimization_results.pivot_table(
        values=metric,
        index=param_y,
        columns=param_x,
        aggfunc='mean',  # In case of duplicates
    )
    
    # Auto-generate title if not provided
    if title is None:
        title = f"Parameter Optimization: {param_x} vs {param_y}"
    
    # Create heatmap
    fig = go.Figure()
    
    fig.add_trace(
        go.Heatmap(
            z=heatmap_data.values,
            x=heatmap_data.columns,
            y=heatmap_data.index,
            colorscale='RdYlGn',  # Red (bad) -> Yellow -> Green (good)
            text=np.round(heatmap_data.values, 4),
            texttemplate='%{text}',
            textfont={"size": 10},
            colorbar=dict(title=metric.replace('_', ' ').title()),
            hovertemplate=(
                f'{param_x}: %{{x}}<br>'
                f'{param_y}: %{{y}}<br>'
                f'{metric}: %{{z:.4f}}<extra></extra>'
            ),
        )
    )
    
    # Find best parameters
    best_idx = heatmap_data.stack().idxmax()
    best_value = heatmap_data.loc[best_idx]
    
    # Add marker for best point
    fig.add_trace(
        go.Scatter(
            x=[best_idx[1]],
            y=[best_idx[0]],
            mode='markers',
            marker=dict(
                size=15,
                color='white',
                symbol='star',
                line=dict(color='black', width=2),
            ),
            name=f'Best: {best_value:.4f}',
            hovertemplate=f'Best parameters<br>{param_x}: %{{x}}<br>{param_y}: %{{y}}<extra></extra>',
        )
    )
    
    # Layout
    fig.update_layout(
        title=title,
        xaxis_title=param_x.replace('_', ' ').title(),
        yaxis_title=param_y.replace('_', ' ').title(),
        height=height,
        width=width,
        template='plotly_white',
        margin=dict(l=80, r=100, t=80, b=60),
    )
    
    logger.info(
        f"Parameter heatmap created: {heatmap_data.shape[0]}x{heatmap_data.shape[1]} grid, "
        f"best {metric}={best_value:.4f} at {param_x}={best_idx[1]}, {param_y}={best_idx[0]}"
    )
    
    return fig
