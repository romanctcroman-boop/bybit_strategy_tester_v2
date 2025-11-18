# Week 1 Monitoring - Quick Reference

**Start Date**: November 18, 2025  
**Status**: ✅ DAY 1 COMPLETE

---

## 🚀 Quick Start

### Manual Check (Anytime)
```powershell
py monitor_staging_quick_wins.py
```

### Automatic Monitoring (6 hours)
```powershell
.\scripts\monitor_staging_scheduler.ps1 -DurationHours 6 -CheckIntervalMinutes 60
```

### View Daily Report
```powershell
Get-Content logs\staging_report_day1_20251118.md
```

---

## 📅 Daily Schedule

### Day 1-2 (Nov 18-19) - Intensive Monitoring
- **09:00**: Morning check
- **14:00**: Afternoon check
- **18:00**: Evening review + daily report

### Day 3-7 (Nov 20-24) - Standard Monitoring
- **09:00**: Morning check
- **18:00**: Evening review + daily report

---

## 📊 What to Monitor

### Critical Metrics
- ✅ Budget exceeded < 1%
- ✅ No increase in 429 errors
- ✅ Even key distribution (5-20%)
- ✅ p95 latency < +10ms

### Commands
```powershell
# Budget exceeded
Get-Content logs/*.log | Select-String "Budget exceeded" | Measure-Object

# Key distribution
Get-Content logs/*.log | Select-String "Key selected:" | Group-Object

# 429 errors
Get-Content logs/*.log | Select-String "429" | Measure-Object
```

---

## 🎯 Success Criteria (End of Week 1)

- [ ] Budget exceeded < 1% (7 days)
- [ ] No 429 increase (vs baseline)
- [ ] Even key distribution
- [ ] Performance acceptable
- [ ] No critical incidents
- [ ] 7 daily reports completed

**If all OK**: ✅ Production deployment (Week 2)

---

## 📁 Reports Location

- **Daily Reports**: `logs/staging_report_day[1-7]_*.md`
- **Hourly Checks**: `logs/staging_checks/check_*.txt`
- **Backend Logs**: `logs/agent_background_service.log`

---

## ⚠️ If Issues Detected

1. Check `STAGING_DEPLOYMENT_GUIDE.md` - Incident Response
2. Run `py monitor_staging_quick_wins.py` for diagnostics
3. Review logs in `logs/` directory

### Quick Rollback
```powershell
Stop-Process -Name "python" -Force
Copy-Item .env.backup.20251118_114228 .env -Force
.\start.ps1
```

---

## 📞 Documentation

- `STAGING_DEPLOYMENT_GUIDE.md` - Full monitoring guide
- `STAGING_DEPLOYMENT_SUCCESS.md` - Deployment summary
- `DEPLOYMENT_CHECKLIST.md` - 4-week plan

---

**Status**: ✅ Week 1 started, all systems operational  
**Next Milestone**: Day 7 staging report (Nov 24)
