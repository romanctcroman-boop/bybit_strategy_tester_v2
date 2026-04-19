"""
📄 PDF Generator

Generate PDF reports using ReportLab.
"""

import logging
from datetime import datetime
from io import BytesIO
from typing import Any

logger = logging.getLogger(__name__)


class PDFGenerator:
    """
    Generate PDF reports using ReportLab.

    Features:
    - Professional layout
    - Charts embedding
    - Tables
    - Custom styling
    """

    def __init__(
        self,
        page_size: str = "A4",
        font_name: str = "Helvetica",
        include_charts: bool = True,
    ):
        """
        Args:
            page_size: Page size (A4, Letter)
            font_name: Default font
            include_charts: Include charts in PDF
        """
        self.page_size = page_size
        self.font_name = font_name
        self.include_charts = include_charts

    def generate(self, report_data: dict[str, Any]) -> bytes:
        """
        Generate PDF from report data.

        Args:
            report_data: Report data dictionary

        Returns:
            PDF bytes
        """
        try:
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_CENTER
            from reportlab.lib.pagesizes import A4, letter
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import cm, inch
            from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

            # Create buffer
            buffer = BytesIO()

            # Setup document
            page_size = A4 if self.page_size == "A4" else letter
            doc = SimpleDocTemplate(
                buffer,
                pagesize=page_size,
                rightMargin=2 * cm,
                leftMargin=2 * cm,
                topMargin=2 * cm,
                bottomMargin=2 * cm,
            )

            # Build PDF content
            story = []
            styles = getSampleStyleSheet()

            # Title
            title_style = ParagraphStyle(
                "CustomTitle",
                parent=styles["Heading1"],
                fontSize=24,
                textColor=colors.HexColor("#1a1a1a"),
                spaceAfter=30,
                alignment=TA_CENTER,
            )

            title = Paragraph(f"Backtest Report: {report_data.get('strategy_name', 'N/A')}", title_style)
            story.append(title)
            story.append(Spacer(1, 0.3 * inch))

            # Summary info
            summary_info = [
                ["Symbol:", report_data.get("symbol", "N/A")],
                ["Timeframe:", report_data.get("timeframe", "N/A")],
                ["Period:", f"{report_data.get('start_date', 'N/A')} to {report_data.get('end_date', 'N/A')}"],
                ["Generated:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            ]

            summary_table = Table(summary_info, colWidths=[2 * inch, 3 * inch])
            summary_table.setStyle(
                TableStyle(
                    [
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.append(summary_table)
            story.append(Spacer(1, 0.5 * inch))

            # Performance Metrics
            metrics_style = ParagraphStyle(
                "MetricsTitle",
                parent=styles["Heading2"],
                fontSize=16,
                textColor=colors.HexColor("#2196F3"),
                spaceAfter=12,
            )

            story.append(Paragraph("Performance Metrics", metrics_style))

            metrics = report_data.get("metrics", {})
            metrics_table_data = [
                ["Metric", "Value"],
                ["Total Return", f"{metrics.get('total_return', 0):.2%}"],
                ["Annual Return", f"{metrics.get('annual_return', 0):.2%}"],
                ["Sharpe Ratio", f"{metrics.get('sharpe_ratio', 0):.2f}"],
                ["Sortino Ratio", f"{metrics.get('sortino_ratio', 0):.2f}"],
                ["Max Drawdown", f"{metrics.get('max_drawdown', 0):.2%}"],
                ["Win Rate", f"{metrics.get('win_rate', 0):.1%}"],
                ["Profit Factor", f"{metrics.get('profit_factor', 0):.2f}"],
                ["Total Trades", str(metrics.get("total_trades", 0))],
            ]

            metrics_table = Table(metrics_table_data, colWidths=[3 * inch, 2 * inch])
            metrics_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2196F3")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 12),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f5f5f5")),
                        ("FONTSIZE", (0, 1), (-1, -1), 10),
                        ("TOPPADDING", (0, 1), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 1), (-1, -1), 8),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ]
                )
            )
            story.append(metrics_table)
            story.append(Spacer(1, 0.5 * inch))

            # Risk Metrics
            story.append(Paragraph("Risk Metrics", metrics_style))

            risk_data = [
                ["Metric", "Value"],
                ["Volatility", f"{metrics.get('volatility', 0):.2%}"],
                ["Avg Drawdown", f"{metrics.get('avg_drawdown', 0):.2%}"],
                ["Drawdown Duration", f"{metrics.get('drawdown_duration', 0):.1f} days"],
                ["VaR 95%", f"{metrics.get('var_95', 0):.2%}"],
                ["CVaR 95%", f"{metrics.get('cvar_95', 0):.2%}"],
            ]

            risk_table = Table(risk_data, colWidths=[3 * inch, 2 * inch])
            risk_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FF5722")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 12),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f5f5f5")),
                        ("FONTSIZE", (0, 1), (-1, -1), 10),
                        ("TOPPADDING", (0, 1), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 1), (-1, -1), 8),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ]
                )
            )
            story.append(risk_table)

            # Trades summary (if included)
            if report_data.get("include_trades", True):
                story.append(PageBreak())
                story.append(Paragraph("Trade History (Last 20)", metrics_style))

                trades = report_data.get("trades", [])[:20]

                if trades:
                    trades_data = [["#", "Date", "Side", "Entry", "Exit", "PnL"]]

                    for i, trade in enumerate(trades):
                        pnl = trade.get("pnl", 0)
                        trades_data.append(
                            [
                                str(i + 1),
                                trade.get("exit_time", "N/A")[:10] if trade.get("exit_time") else "N/A",
                                trade.get("side", "N/A").upper(),
                                f"{trade.get('entry_price', 0):.2f}",
                                f"{trade.get('exit_price', 0):.2f}",
                                f"{pnl:.2f}",
                            ]
                        )

                    trades_table = Table(
                        trades_data, colWidths=[0.5 * inch, 1.2 * inch, 0.8 * inch, 1 * inch, 1 * inch, 1 * inch]
                    )
                    trades_table.setStyle(
                        TableStyle(
                            [
                                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4CAF50")),
                                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                                ("FONTSIZE", (0, 0), (-1, 0), 10),
                                ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#fafafa")),
                                ("FONTSIZE", (0, 1), (-1, -1), 9),
                                ("TOPPADDING", (0, 1), (-1, -1), 6),
                                ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
                                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                            ]
                        )
                    )
                    story.append(trades_table)

            # Build PDF
            doc.build(story)

            # Get PDF bytes
            pdf_bytes = buffer.getvalue()
            buffer.close()

            logger.info(f"Generated PDF report ({len(pdf_bytes)} bytes)")

            return pdf_bytes

        except ImportError:
            logger.warning("ReportLab not installed, generating simple PDF")
            return self._generate_simple_pdf(report_data)
        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            raise

    def _generate_simple_pdf(self, report_data: dict[str, Any]) -> bytes:
        """Generate simple PDF without ReportLab"""
        # Fallback: return minimal PDF
        from reportlab.pdfgen import canvas

        buffer = BytesIO()
        c = canvas.Canvas(buffer)

        c.setFont("Helvetica", 16)
        c.drawString(100, 750, f"Backtest Report: {report_data.get('strategy_name', 'N/A')}")

        c.setFont("Helvetica", 12)
        c.drawString(100, 720, f"Symbol: {report_data.get('symbol', 'N/A')}")
        c.drawString(100, 700, f"Total Return: {report_data.get('metrics', {}).get('total_return', 0):.2%}")
        c.drawString(100, 680, f"Sharpe Ratio: {report_data.get('metrics', {}).get('sharpe_ratio', 0):.2f}")

        c.save()

        pdf_bytes = buffer.getvalue()
        buffer.close()

        return pdf_bytes
