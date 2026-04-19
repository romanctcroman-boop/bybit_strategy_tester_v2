"""
📄 Backtesting Reports Generator

Generate professional PDF/HTML reports for backtest results.

@version: 1.0.0
@date: 2026-02-26
"""

from .email_sender import EmailSender
from .generator import ReportData, ReportGenerator
from .pdf_generator import PDFGenerator

__all__ = [
    "EmailSender",
    "PDFGenerator",
    "ReportData",
    "ReportGenerator",
]
