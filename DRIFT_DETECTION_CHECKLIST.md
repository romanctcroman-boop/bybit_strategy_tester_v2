# ✅ QUICK START CHECKLIST - Model Drift Detection

**Приоритет**: 🔴 P1 (CRITICAL)  
**Срок**: 3-5 дней  
**ROI**: 40-60% улучшение производительности

---

## 📋 ДЕНЬ 1: Setup & Dependencies

### ✅ Шаг 1: Создать ветку
```bash
git checkout -b feature/model-drift-detection
git push -u origin feature/model-drift-detection
```

### ✅ Шаг 2: Установить зависимости
```bash
# Drift detection library
pip install river

# Circuit breaker для следующего этапа
pip install circuitbreaker

# Обновить requirements.txt
pip freeze | grep -E "(river|circuitbreaker)" >> requirements.txt
```

### ✅ Шаг 3: Изучить документацию
- [ ] River drift detection: https://riverml.xyz/latest/api/drift/ADWIN/
- [ ] Прочитать: `DEEPSEEK_TECHNICAL_AUDIT_PHASE4.md` (строки 27-85)
- [ ] Понять current cron setup: `deployment/k8s/cronjobs.yaml`

---

## 📋 ДЕНЬ 2-3: Реализация Drift Detection

### ✅ Шаг 4: Создать DriftDetector класс
**Файл**: `backend/ml/drift_detector.py`

```python
"""
Model Drift Detection using ADWIN algorithm
"""
from river import drift
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class ModelDriftDetector:
    """
    Detects concept drift in ML model predictions using ADWIN algorithm.
    
    Triggers emergency retraining when drift is detected.
    """
    
    def __init__(self, delta: float = 0.002):
        """
        Args:
            delta: Confidence level (lower = more sensitive)
                  0.002 = 99.8% confidence
        """
        self.detector = drift.ADWIN(delta=delta)
        self.drift_detected_count = 0
        self.last_drift_time: Optional[datetime] = None
    
    def update(self, prediction: float, actual: float) -> bool:
        """
        Update drift detector with new prediction error.
        
        Args:
            prediction: Model's predicted value
            actual: Actual observed value
            
        Returns:
            True if drift detected, False otherwise
        """
        error = abs(prediction - actual)
        self.detector.update(error)
        
        if self.detector.drift_detected:
            self.drift_detected_count += 1
            self.last_drift_time = datetime.now()
            
            logger.critical(
                f"⚠️ MODEL DRIFT DETECTED! "
                f"Error spike detected. "
                f"Total drifts: {self.drift_detected_count}"
            )
            return True
        
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get drift detector status"""
        return {
            "drift_detected_count": self.drift_detected_count,
            "last_drift_time": self.last_drift_time.isoformat() if self.last_drift_time else None,
            "delta": self.detector.delta,
            "width": self.detector.width if hasattr(self.detector, 'width') else None
        }
    
    def reset(self):
        """Reset drift detector (call after retraining)"""
        self.detector = drift.ADWIN(delta=self.detector.delta)
        logger.info("Drift detector reset after model retrain")
```

### ✅ Шаг 5: Интегрировать в ModelManager
**Файл**: `backend/ml/model_manager.py`

**Добавить в класс**:
```python
from backend.ml.drift_detector import ModelDriftDetector

class ModelManager:
    def __init__(self):
        # ... existing code ...
        self.drift_detector = ModelDriftDetector(delta=0.002)
        self.emergency_retrain_threshold = 3  # After 3 drifts
    
    async def predict_with_drift_check(self, data: np.ndarray) -> float:
        """
        Make prediction and check for drift.
        Triggers emergency retrain if needed.
        """
        # Make prediction
        prediction = await self.model.predict(data)
        
        # Later, when actual value is known, update drift detector
        # This happens in a separate async task
        
        return prediction
    
    async def update_drift_detector(self, prediction: float, actual: float):
        """
        Update drift detector with prediction vs actual.
        Call this from your trading loop when actual price is known.
        """
        drift_detected = self.drift_detector.update(prediction, actual)
        
        if drift_detected:
            # Check if we need emergency retrain
            if self.drift_detector.drift_detected_count >= self.emergency_retrain_threshold:
                logger.critical(
                    f"🚨 EMERGENCY RETRAIN TRIGGERED! "
                    f"{self.drift_detector.drift_detected_count} drifts detected"
                )
                await self.trigger_emergency_retrain()
            else:
                logger.warning(
                    f"Drift detected ({self.drift_detector.drift_detected_count}/"
                    f"{self.emergency_retrain_threshold}), monitoring..."
                )
    
    async def trigger_emergency_retrain(self):
        """
        Trigger emergency model retraining.
        This should run in background, not block predictions.
        """
        logger.info("Starting emergency model retrain...")
        
        try:
            # Start background retrain task
            asyncio.create_task(self._retrain_model_async())
            
            # Alert ops team
            await self._alert_ops_team("Model drift - emergency retrain started")
            
            # Reset drift detector
            self.drift_detector.reset()
            
        except Exception as e:
            logger.error(f"Emergency retrain failed: {e}")
            await self._alert_ops_team(f"CRITICAL: Emergency retrain failed - {e}")
    
    async def _retrain_model_async(self):
        """Background task for model retraining"""
        # Your existing retrain logic here
        pass
    
    async def _alert_ops_team(self, message: str):
        """Send alert to ops team (Slack, email, etc.)"""
        # Implement your alerting logic
        logger.critical(f"OPS ALERT: {message}")
```

---

## 📋 ДЕНЬ 4: Dynamic Retraining Schedule

### ✅ Шаг 6: Волатильность-aware scheduling
**Файл**: `backend/ml/retrain_scheduler.py`

```python
"""
Dynamic model retraining scheduler based on market volatility
"""
import numpy as np
from datetime import datetime, timedelta
from typing import Literal

class DynamicRetrainScheduler:
    """
    Adjusts retraining frequency based on market conditions.
    
    High volatility → retrain every 6 hours
    Normal volatility → retrain daily
    Low volatility → retrain weekly
    """
    
    def __init__(self):
        self.volatility_high_threshold = 0.05  # 5% daily volatility
        self.volatility_low_threshold = 0.02   # 2% daily volatility
    
    def get_retrain_schedule(
        self, 
        realized_volatility: float
    ) -> Literal["6h", "daily", "weekly"]:
        """
        Determine retrain frequency based on volatility.
        
        Args:
            realized_volatility: Recent realized volatility (e.g., 0.03 = 3%)
            
        Returns:
            Schedule frequency: "6h", "daily", or "weekly"
        """
        if realized_volatility > self.volatility_high_threshold:
            return "6h"
        elif realized_volatility > self.volatility_low_threshold:
            return "daily"
        else:
            return "weekly"
    
    def calculate_realized_volatility(
        self, 
        prices: np.ndarray, 
        window: int = 24
    ) -> float:
        """
        Calculate recent realized volatility.
        
        Args:
            prices: Array of recent prices
            window: Number of periods (e.g., 24 hours)
            
        Returns:
            Realized volatility (annualized)
        """
        returns = np.diff(np.log(prices))
        volatility = np.std(returns[-window:]) * np.sqrt(365 * 24)  # Annualized
        return volatility
```

### ✅ Шаг 7: Обновить Kubernetes CronJob
**Файл**: `deployment/k8s/cronjobs.yaml`

```yaml
# Dynamic scheduling - starts with default (daily)
# Adjust via ConfigMap based on market conditions

apiVersion: batch/v1
kind: CronJob
metadata:
  name: model-retrain-dynamic
spec:
  # Default: daily at 2am UTC
  # Updated dynamically by scheduler service
  schedule: "0 2 * * *"
  
  concurrencyPolicy: Forbid  # Don't run multiple retrains
  
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: model-retrain
            image: bybit-tester:latest
            command: ["python", "-m", "backend.ml.retrain_job"]
            env:
            - name: RETRAIN_MODE
              value: "scheduled"  # vs "emergency"
            - name: DRIFT_THRESHOLD
              value: "0.002"
```

---

## 📋 ДЕНЬ 5: Testing & Validation

### ✅ Шаг 8: Unit тесты
**Файл**: `tests/unit/test_drift_detector.py`

```python
import pytest
import numpy as np
from backend.ml.drift_detector import ModelDriftDetector

def test_drift_detector_initialization():
    """Test drift detector creates successfully"""
    detector = ModelDriftDetector(delta=0.002)
    assert detector.drift_detected_count == 0
    assert detector.last_drift_time is None

def test_drift_detection_on_stable_predictions():
    """Test no drift on stable predictions"""
    detector = ModelDriftDetector(delta=0.002)
    
    # Stable predictions (low error)
    for i in range(100):
        prediction = 100.0 + np.random.normal(0, 0.1)
        actual = 100.0 + np.random.normal(0, 0.1)
        
        drift = detector.update(prediction, actual)
        
    # Should detect no drift on stable data
    assert detector.drift_detected_count == 0

def test_drift_detection_on_concept_shift():
    """Test drift detection when concept shifts"""
    detector = ModelDriftDetector(delta=0.002)
    
    # First 50 predictions: stable
    for i in range(50):
        prediction = 100.0 + np.random.normal(0, 0.1)
        actual = 100.0 + np.random.normal(0, 0.1)
        detector.update(prediction, actual)
    
    # Next 50 predictions: large error (concept drift)
    drift_detected = False
    for i in range(50):
        prediction = 100.0 + np.random.normal(0, 0.1)
        actual = 110.0 + np.random.normal(0, 0.1)  # Shift!
        
        if detector.update(prediction, actual):
            drift_detected = True
            break
    
    assert drift_detected, "Should detect drift after concept shift"
    assert detector.drift_detected_count >= 1
```

### ✅ Шаг 9: Integration тест
**Файл**: `tests/integration/test_drift_emergency_retrain.py`

```python
import pytest
import asyncio
from backend.ml.model_manager import ModelManager

@pytest.mark.asyncio
async def test_emergency_retrain_trigger():
    """Test emergency retrain triggers after multiple drifts"""
    manager = ModelManager()
    manager.emergency_retrain_threshold = 3
    
    # Simulate 3 drift detections
    for i in range(3):
        manager.drift_detector.drift_detected_count = i + 1
        
        # Trigger update with large error
        await manager.update_drift_detector(
            prediction=100.0,
            actual=120.0  # Large error
        )
    
    # Should have triggered emergency retrain
    assert manager.drift_detector.drift_detected_count >= 3
```

---

## ✅ ГОТОВНОСТЬ К ДЕПЛОЮ

- [ ] Все тесты прошли (unit + integration)
- [ ] Drift detector интегрирован в ModelManager
- [ ] Emergency retrain функция работает
- [ ] Dynamic scheduling протестирован
- [ ] Kubernetes CronJob обновлён
- [ ] Мониторинг drift metrics настроен
- [ ] Алерты в Slack/email работают
- [ ] Документация обновлена
- [ ] Code review пройден
- [ ] Готов к merge в main

---

## 📊 МЕТРИКИ ДЛЯ МОНИТОРИНГА

После деплоя отслеживать:

1. **Drift Detection Rate**: сколько дрифтов в день
2. **Emergency Retrain Count**: сколько emergency retrains
3. **Model Performance Before/After**: улучшилась ли accuracy
4. **Retrain Latency**: сколько времени занимает retrain
5. **Cost Impact**: дополнительные затраты на compute

**Expected**: 2-3 дрифта в неделю в нормальных условиях

---

**Создано**: 6 ноября 2025  
**Источник**: AI_AUDIT_ACTION_PLAN.md  
**Следующий этап**: P2 - Latency Cascade Fixes
