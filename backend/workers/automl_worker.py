"""
AutoML Worker for Kubernetes Jobs

Distributed Optuna optimization worker that:
- Connects to shared PostgreSQL storage
- Executes trials from study
- Reports progress to backend API
- Exposes Prometheus metrics

Environment Variables:
- AUTOML_STUDY_ID: Study identifier
- AUTOML_WORKER_ID: Worker identifier (pod name)
- OPTUNA_STORAGE_URL: PostgreSQL storage URL
- BACKEND_API_URL: Backend API endpoint
- AUTOML_SAMPLER: Sampler type (tpe, random, cmaes)
- AUTOML_PRUNER: Pruner type (median, hyperband, none)

Usage (Kubernetes Job):
    python -m backend.workers.automl_worker

Author: Bybit Strategy Tester Team
Phase: 4.4 (ML-Powered Features - Kubernetes AutoML Jobs)
"""

import logging
import os
import sys
import time
from typing import Any

import optuna
import requests
from prometheus_client import Counter, Gauge, Histogram, start_http_server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Prometheus metrics
TRIAL_COUNTER = Counter(
    'automl_trials_total',
    'Total number of trials executed',
    ['study_id', 'worker_id', 'state']
)

TRIAL_DURATION = Histogram(
    'automl_trial_duration_seconds',
    'Duration of trial execution',
    ['study_id', 'worker_id']
)

ACTIVE_TRIALS = Gauge(
    'automl_active_trials',
    'Number of currently active trials',
    ['study_id', 'worker_id']
)

WORKER_STATUS = Gauge(
    'automl_worker_status',
    'Worker status (1=running, 0=stopped)',
    ['study_id', 'worker_id']
)


class AutoMLWorker:
    """
    Distributed Optuna optimization worker
    
    Runs as Kubernetes Job pod, executes trials from shared study
    """
    
    def __init__(
        self,
        study_id: str,
        worker_id: str,
        storage_url: str,
        backend_api_url: str,
        sampler: str = "tpe",
        pruner: str = "median",
    ):
        """
        Initialize AutoML worker
        
        Args:
            study_id: Study identifier
            worker_id: Worker identifier (pod name)
            storage_url: Optuna storage URL (PostgreSQL)
            backend_api_url: Backend API endpoint
            sampler: Sampler type
            pruner: Pruner type
        """
        self.study_id = study_id
        self.worker_id = worker_id
        self.storage_url = storage_url
        self.backend_api_url = backend_api_url
        self.sampler = sampler
        self.pruner = pruner
        
        # Metrics labels
        self.labels = {
            'study_id': study_id,
            'worker_id': worker_id,
        }
        
        logger.info(f"AutoML Worker initialized: study_id={study_id}, worker_id={worker_id}")
    
    def run(self, n_trials: int | None = None, timeout: int | None = None):
        """
        Run optimization loop
        
        Args:
            n_trials: Number of trials to execute (None = unlimited)
            timeout: Timeout in seconds (None = no timeout)
        """
        logger.info(f"Starting optimization: n_trials={n_trials}, timeout={timeout}")
        
        # Set worker status to running
        WORKER_STATUS.labels(**self.labels).set(1)
        
        try:
            # Load study from storage
            study = self._load_study()
            
            # Run optimization
            study.optimize(
                self._objective,
                n_trials=n_trials,
                timeout=timeout,
                catch=(Exception,),  # Don't stop on individual trial errors
                callbacks=[self._trial_callback],
            )
            
            logger.info("Optimization completed successfully")
            return 0  # Success exit code
        
        except Exception as e:
            logger.error(f"Optimization failed: {e}", exc_info=True)
            return 1  # Failure exit code
        
        finally:
            # Set worker status to stopped
            WORKER_STATUS.labels(**self.labels).set(0)
    
    def _load_study(self) -> optuna.Study:
        """Load study from shared storage"""
        logger.info(f"Loading study from storage: {self.storage_url}")
        
        try:
            study = optuna.load_study(
                study_name=self.study_id,
                storage=self.storage_url,
            )
            
            logger.info(f"Study loaded: {study.study_name}, direction={study.direction}")
            return study
        
        except Exception as e:
            logger.error(f"Failed to load study: {e}")
            raise
    
    def _objective(self, trial: optuna.Trial) -> float | list[float]:
        """
        Objective function for optimization
        
        Args:
            trial: Optuna trial
        
        Returns:
            Objective value(s)
        """
        ACTIVE_TRIALS.labels(**self.labels).inc()
        start_time = time.time()
        
        try:
            # Fetch study config from backend API
            study_config = self._fetch_study_config()
            
            # Sample hyperparameters
            params = self._sample_params(trial, study_config['param_space'])
            
            # Execute backtest with these parameters
            backtest_result = self._execute_backtest(
                strategy_id=study_config['strategy_id'],
                symbol=study_config['symbol'],
                timeframe=study_config['timeframe'],
                start_date=study_config['start_date'],
                end_date=study_config['end_date'],
                params=params,
                trial=trial,
            )
            
            # Extract objective values
            objectives = study_config.get('objectives', ['sharpe_ratio'])
            
            if len(objectives) == 1:
                # Single objective
                value = self._extract_metric(backtest_result, objectives[0])
                
                # Record metrics
                duration = time.time() - start_time
                TRIAL_DURATION.labels(**self.labels).observe(duration)
                TRIAL_COUNTER.labels(**self.labels, state='complete').inc()
                
                return value
            
            else:
                # Multi-objective
                values = [
                    self._extract_metric(backtest_result, obj)
                    for obj in objectives
                ]
                
                # Record metrics
                duration = time.time() - start_time
                TRIAL_DURATION.labels(**self.labels).observe(duration)
                TRIAL_COUNTER.labels(**self.labels, state='complete').inc()
                
                return values
        
        except optuna.TrialPruned:
            # Trial was pruned (early stopping)
            duration = time.time() - start_time
            TRIAL_DURATION.labels(**self.labels).observe(duration)
            TRIAL_COUNTER.labels(**self.labels, state='pruned').inc()
            raise
        
        except Exception as e:
            # Trial failed
            logger.error(f"Trial {trial.number} failed: {e}", exc_info=True)
            duration = time.time() - start_time
            TRIAL_DURATION.labels(**self.labels).observe(duration)
            TRIAL_COUNTER.labels(**self.labels, state='failed').inc()
            raise
        
        finally:
            ACTIVE_TRIALS.labels(**self.labels).dec()
    
    def _fetch_study_config(self) -> dict[str, Any]:
        """Fetch study configuration from backend API"""
        try:
            url = f"{self.backend_api_url}/api/v1/automl/studies/{self.study_id}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            return response.json()
        
        except Exception as e:
            logger.error(f"Failed to fetch study config: {e}")
            # Return default config as fallback
            return {
                'strategy_id': 1,
                'symbol': 'BTCUSDT',
                'timeframe': '1h',
                'start_date': '2024-01-01T00:00:00Z',
                'end_date': '2024-12-31T23:59:59Z',
                'objectives': ['sharpe_ratio'],
                'param_space': {},
            }
    
    def _sample_params(self, trial: optuna.Trial, param_space: dict[str, Any]) -> dict[str, Any]:
        """Sample hyperparameters from search space"""
        params = {}
        
        for param_name, param_config in param_space.items():
            param_type = param_config['type']
            
            if param_type == 'int':
                params[param_name] = trial.suggest_int(
                    param_name,
                    low=param_config['low'],
                    high=param_config['high'],
                    step=param_config.get('step', 1),
                )
            
            elif param_type == 'float':
                params[param_name] = trial.suggest_float(
                    param_name,
                    low=param_config['low'],
                    high=param_config['high'],
                    step=param_config.get('step'),
                )
            
            elif param_type == 'categorical':
                params[param_name] = trial.suggest_categorical(
                    param_name,
                    choices=param_config['choices'],
                )
        
        logger.info(f"Trial {trial.number}: Sampled params: {params}")
        return params
    
    def _execute_backtest(
        self,
        strategy_id: int,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        params: dict[str, Any],
        trial: optuna.Trial,
    ) -> dict[str, Any]:
        """
        Execute backtest via backend API
        
        Args:
            strategy_id: Strategy to test
            symbol: Trading pair
            timeframe: Candle interval
            start_date: Backtest start
            end_date: Backtest end
            params: Strategy parameters
            trial: Optuna trial (for intermediate reporting)
        
        Returns:
            Backtest results (metrics)
        """
        try:
            # Submit backtest request
            url = f"{self.backend_api_url}/api/v1/backtests"
            payload = {
                'strategy_id': strategy_id,
                'symbol': symbol,
                'timeframe': timeframe,
                'start_date': start_date,
                'end_date': end_date,
                'parameters': params,
            }
            
            logger.info(f"Submitting backtest: {payload}")
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            
            backtest_id = response.json()['id']
            logger.info(f"Backtest created: {backtest_id}")
            
            # Poll for completion
            result = self._poll_backtest_completion(backtest_id, trial)
            
            logger.info(f"Backtest {backtest_id} completed: Sharpe={result.get('sharpe_ratio', 'N/A')}")
            return result
        
        except Exception as e:
            logger.error(f"Backtest execution failed: {e}")
            raise
    
    def _poll_backtest_completion(
        self,
        backtest_id: int,
        trial: optuna.Trial,
        poll_interval: int = 5,
        max_wait: int = 600,
    ) -> dict[str, Any]:
        """
        Poll backtest status until completion
        
        Args:
            backtest_id: Backtest ID
            trial: Optuna trial (for intermediate reporting)
            poll_interval: Polling interval (seconds)
            max_wait: Max wait time (seconds)
        
        Returns:
            Backtest results
        """
        url = f"{self.backend_api_url}/api/v1/backtests/{backtest_id}"
        elapsed = 0
        
        while elapsed < max_wait:
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                status = data.get('status')
                progress = data.get('progress', 0)
                
                # Report intermediate progress (for pruning)
                if progress > 0:
                    intermediate_sharpe = data.get('sharpe_ratio', 0.0)
                    trial.report(intermediate_sharpe, step=int(progress))
                    
                    # Check if trial should be pruned
                    if trial.should_prune():
                        logger.info(f"Trial {trial.number} pruned at {progress}%")
                        raise optuna.TrialPruned()
                
                if status == 'completed':
                    return data
                
                elif status == 'failed':
                    raise Exception(f"Backtest {backtest_id} failed")
                
                # Wait before next poll
                time.sleep(poll_interval)
                elapsed += poll_interval
            
            except optuna.TrialPruned:
                raise
            
            except Exception as e:
                logger.warning(f"Polling error: {e}")
                time.sleep(poll_interval)
                elapsed += poll_interval
        
        raise TimeoutError(f"Backtest {backtest_id} did not complete within {max_wait}s")
    
    def _extract_metric(self, backtest_result: dict[str, Any], metric_name: str) -> float:
        """Extract metric from backtest results"""
        metric_mapping = {
            'sharpe_ratio': 'sharpe_ratio',
            'max_drawdown': 'max_drawdown',
            'win_rate': 'win_rate',
            'profit_factor': 'profit_factor',
            'total_pnl': 'total_pnl',
        }
        
        key = metric_mapping.get(metric_name, metric_name)
        
        if key not in backtest_result:
            logger.warning(f"Metric '{metric_name}' not found, returning 0.0")
            return 0.0
        
        return float(backtest_result[key])
    
    def _trial_callback(self, study: optuna.Study, trial: optuna.trial.FrozenTrial):
        """
        Callback after each trial completion
        
        Sends trial result to backend API
        """
        try:
            url = f"{self.backend_api_url}/api/v1/automl/studies/{self.study_id}/trials"
            payload = {
                'trial_number': trial.number,
                'params': trial.params,
                'values': trial.values if hasattr(trial, 'values') else [trial.value],
                'state': trial.state.name,
                'datetime_start': trial.datetime_start.isoformat() if trial.datetime_start else None,
                'datetime_complete': trial.datetime_complete.isoformat() if trial.datetime_complete else None,
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info(f"Trial {trial.number} reported to backend")
        
        except Exception as e:
            logger.warning(f"Failed to report trial: {e}")


def main():
    """Main entry point for Kubernetes Job"""
    # Parse environment variables
    study_id = os.getenv('AUTOML_STUDY_ID')
    worker_id = os.getenv('AUTOML_WORKER_ID', 'unknown')
    storage_url = os.getenv('OPTUNA_STORAGE_URL')
    backend_api_url = os.getenv('BACKEND_API_URL', 'http://backend:8000')
    sampler = os.getenv('AUTOML_SAMPLER', 'tpe')
    pruner = os.getenv('AUTOML_PRUNER', 'median')
    
    # Validation
    if not study_id:
        logger.error("AUTOML_STUDY_ID environment variable not set")
        sys.exit(1)
    
    if not storage_url:
        logger.error("OPTUNA_STORAGE_URL environment variable not set")
        sys.exit(1)
    
    logger.info("=" * 80)
    logger.info("AutoML Worker Starting")
    logger.info(f"Study ID: {study_id}")
    logger.info(f"Worker ID: {worker_id}")
    logger.info(f"Storage: {storage_url}")
    logger.info(f"Backend API: {backend_api_url}")
    logger.info(f"Sampler: {sampler}")
    logger.info(f"Pruner: {pruner}")
    logger.info("=" * 80)
    
    # Start Prometheus metrics server
    metrics_port = int(os.getenv('METRICS_PORT', '9090'))
    start_http_server(metrics_port)
    logger.info(f"Prometheus metrics server started on port {metrics_port}")
    
    # Create worker
    worker = AutoMLWorker(
        study_id=study_id,
        worker_id=worker_id,
        storage_url=storage_url,
        backend_api_url=backend_api_url,
        sampler=sampler,
        pruner=pruner,
    )
    
    # Run optimization (single trial per worker in Kubernetes Job mode)
    # The Job's parallelism/completions settings control total trials
    exit_code = worker.run(n_trials=1)
    
    logger.info(f"Worker exiting with code: {exit_code}")
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
