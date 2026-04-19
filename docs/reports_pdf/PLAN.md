# 📄 P2-5: Backtesting Reports PDF — План

**Дата:** 2026-02-26
**Статус:** ⏳ В работе
**Оценка:** 3 дня (24 часа)

---

## 🎯 Цель

Реализовать автоматическую генерацию PDF отчётов:
- 166 метрик с графиками
- Email рассылка отчётов
- Scheduled backtests (Celery)
- HTML export

---

## 🏗️ Архитектура

```
backend/reports/
├── __init__.py
├── generator.py            # ReportGenerator (главный класс)
├── pdf_generator.py        # ReportLab integration
├── email_sender.py         # Email reports
├── templates/
│   ├── backtest_report.html
│   ├── optimization_report.html
│   └── styles.css
└── tests/
    ├── test_generator.py
    └── test_pdf.py
```

---

## 📝 План работ

### День 1: Generator + Templates (8 часов)
- [ ] ReportGenerator класс
- [ ] HTML templates
- [ ] CSS стили
- [ ] Metrics visualization

### День 2: PDF + Email (8 часов)
- [ ] PDF generation (ReportLab)
- [ ] Email integration
- [ ] Attachments

### День 3: API + Tests (8 часов)
- [ ] API endpoints
- [ ] Celery tasks
- [ ] Тесты
- [ ] Документация

---

## 🔧 Зависимости

### requirements-reports.txt

```txt
# PDF Generation
reportlab>=4.0.0
weasyprint>=59.0

# Email
aiosmtplib>=3.0.0
email-validator>=2.1.0

# Templates
jinja2>=3.1.0

# Scheduling
celery>=5.3.0
```

---

## 📊 Ожидаемые результаты

### Отчёты

**Backtest Report:**
- Strategy overview
- 166 metrics (grouped)
- Equity curve chart
- Drawdown chart
- Trades table
- Monthly returns heatmap

**Optimization Report:**
- Optimization summary
- Parameter sensitivity
- Efficient frontier
- Top 10 results

### Email

**Функции:**
- PDF attachment
- HTML body
- Summary metrics
- Charts inline

---

## ✅ Критерии приёмки

- [ ] PDF generation работает
- [ ] 166 метрик отображаются
- [ ] Графики в PDF
- [ ] Email integration работает
- [ ] API endpoints созданы
- [ ] Тесты проходят (>80%)

---

*План создан: 2026-02-26*
