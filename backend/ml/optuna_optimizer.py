"""
ML Optimizer using Optuna for hyperparameter tuning

Quick Win #3: Tournament + ML Integration
Provides automatic parameter optimization for trading strategies
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import json

import optuna
from optuna import Trial
from optuna.samplers import TPESampler
from optuna.pruners import MedianPruner
import pandas as pd
import numpy as np


logger = logging.getLogger(__name__)


@dataclass
class OptimizationConfig:
    """Configuration for strategy optimization"""
    n_trials: int = 100
    timeout: Optional[float] = None  # seconds
    n_jobs: int = 1  # parallel jobs
    objectives: List[str] = None  # ["sharpe_ratio", "max_drawdown"]
    sampler: str = "tpe"  # tpe, random, grid
    pruner: str = "median"  # median, none
    
    def __post_init__(self):
        if self.objectives is None:
            self.objectives = ["sharpe_ratio", "max_drawdown"]


@dataclass
class OptimizationResult:
    """Results of optimization"""
    best_params: Dict[str, Any]
    best_value: float  # for single objective
    best_values: List[float]  # for multi-objective
    n_trials: int
    study_name: str
    optimization_time: float
    all_trials: List[Dict[str, Any]]
    convergence_plot_data: Optional[Dict] = None


class StrategyOptimizer:
    """
    Optuna-based hyperparameter optimizer for trading strategies
    
    Features:
    - Multi-objective optimization
    - Early stopping (pruning)
    - Parallel execution support
    - Integration with Sandbox execution
    - Auto-logging to Knowledge Base
    
    Example:
        optimizer = StrategyOptimizer()
        
        result = await optimizer.optimize_strategy(
            strategy_code="...",
            data=df,
            param_space={
                "rsi_period": {"type": "int", "low": 5, "high": 30},
                "threshold": {"type": "float", "low": 0.01, "high": 0.1}
            },
            objectives=["sharpe_ratio", "max_drawdown"],
            n_trials=100
        )
    """
    
    def __init__(self, config: Optional[OptimizationConfig] = None):
        """
        Initialize optimizer
        
        Args:
            config: Optimization configuration
        """
        self.config = config or OptimizationConfig()
        self.sandbox_executor = None  # Will be injected
        self.reasoning_storage = None  # Will be injected
    
    def set_sandbox_executor(self, executor):
        """Inject sandbox executor dependency"""
        self.sandbox_executor = executor
    
    def set_reasoning_storage(self, storage):
        """Inject reasoning storage dependency"""
        self.reasoning_storage = storage
    
    async def optimize_strategy(
        self,
        strategy_code: str,
        data: pd.DataFrame,
        param_space: Dict[str, Dict[str, Any]],
        objectives: Optional[List[str]] = None,
        n_trials: Optional[int] = None,
        timeout: Optional[float] = None,
        study_name: Optional[str] = None
    ) -> OptimizationResult:
        """
        Optimize strategy hyperparameters
        
        Args:
            strategy_code: Strategy source code
            data: Historical data for backtesting
            param_space: Parameter search space
                Example: {
                    "rsi_period": {"type": "int", "low": 10, "high": 30},
                    "threshold": {"type": "float", "low": 0.01, "high": 0.1, "step": 0.01}
                }
            objectives: Objectives to optimize (default: ["sharpe_ratio", "max_drawdown"])
            n_trials: Number of trials (default from config)
            timeout: Timeout in seconds (default from config)
            study_name: Name for the study (default: auto-generated)
        
        Returns:
            OptimizationResult with best parameters and metrics
        """
        objectives = objectives or self.config.objectives
        n_trials = n_trials or self.config.n_trials
        timeout = timeout or self.config.timeout
        study_name = study_name or f"strategy_opt_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        logger.info(f"Starting optimization: {study_name}")
        logger.info(f"Objectives: {objectives}, Trials: {n_trials}")
        logger.info(f"Parameter space: {list(param_space.keys())}")
        
        start_time = datetime.now()
        
        # Create study
        directions = self._get_directions(objectives)
        study = optuna.create_study(
            study_name=study_name,
            directions=directions,
            sampler=self._get_sampler(),
            pruner=self._get_pruner()
        )
        
        # Define objective function
        async def objective(trial: Trial) -> tuple:
            """Objective function for Optuna"""
            # Sample parameters
            params = self._sample_parameters(trial, param_space)
            
            logger.debug(f"Trial {trial.number}: Testing params {params}")
            
            # Execute strategy with these parameters
            if self.sandbox_executor:
                # Use sandbox for safe execution
                result = await self._execute_in_sandbox(
                    strategy_code, data, params, trial.number
                )
            else:
                # Fallback: direct execution (less safe)
                result = await self._execute_directly(
                    strategy_code, data, params, trial.number
                )
            
            # Extract objective values
            values = []
            for obj in objectives:
                if obj == "sharpe_ratio":
                    values.append(result.get("sharpe_ratio", -999))
                elif obj == "max_drawdown":
                    # Minimize drawdown (negate for maximization)
                    values.append(-abs(result.get("max_drawdown", 999)))
                elif obj == "total_return":
                    values.append(result.get("total_return", -999))
                elif obj == "sortino_ratio":
                    values.append(result.get("sortino_ratio", -999))
                elif obj == "win_rate":
                    values.append(result.get("win_rate", 0))
                elif obj == "profit_factor":
                    values.append(result.get("profit_factor", 0))
                else:
                    logger.warning(f"Unknown objective: {obj}, using 0")
                    values.append(0)
            
            # Store trial metadata
            trial.set_user_attr("params", params)
            trial.set_user_attr("metrics", result)
            trial.set_user_attr("executed_at", datetime.now().isoformat())
            
            return tuple(values) if len(values) > 1 else values[0]
        
        # Wrap async objective for Optuna (which expects sync)
        # Use get_event_loop() for nested async contexts
        def sync_objective(trial: Trial):
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in async context - create task
                import nest_asyncio
                nest_asyncio.apply()
                return loop.run_until_complete(objective(trial))
            else:
                return asyncio.run(objective(trial))
        
        # Run optimization
        try:
            study.optimize(
                sync_objective,
                n_trials=n_trials,
                timeout=timeout,
                n_jobs=self.config.n_jobs,
                show_progress_bar=True
            )
        except Exception as e:
            logger.error(f"Optimization failed: {e}", exc_info=True)
            raise
        
        end_time = datetime.now()
        optimization_time = (end_time - start_time).total_seconds()
        
        # Extract results
        if len(objectives) > 1:
            # Multi-objective: get Pareto front
            best_trials = study.best_trials
            best_params = best_trials[0].params if best_trials else {}
            best_values = [t.values for t in best_trials]
            best_value = None
        else:
            # Single objective
            best_params = study.best_params
            best_value = study.best_value
            best_values = [best_value]
        
        # Collect all trials
        all_trials = [
            {
                "number": t.number,
                "params": t.params,
                "values": t.values,
                "state": t.state.name,
                "datetime": t.datetime_start.isoformat() if t.datetime_start else None
            }
            for t in study.trials
        ]
        
        # Create result
        result = OptimizationResult(
            best_params=best_params,
            best_value=best_value,
            best_values=best_values,
            n_trials=len(study.trials),
            study_name=study_name,
            optimization_time=optimization_time,
            all_trials=all_trials
        )
        
        logger.info(f"Optimization complete: {len(study.trials)} trials in {optimization_time:.1f}s")
        logger.info(f"Best params: {best_params}")
        logger.info(f"Best value(s): {best_values}")
        
        # Store in Knowledge Base (if available)
        if self.reasoning_storage:
            await self._store_optimization_trace(
                study_name, param_space, result, objectives
            )
        
        return result
    
    def _get_directions(self, objectives: List[str]) -> List[str]:
        """Get optimization directions for objectives"""
        directions = []
        for obj in objectives:
            if obj in ["max_drawdown", "volatility", "var_95"]:
                directions.append("minimize")
            else:
                directions.append("maximize")
        return directions
    
    def _get_sampler(self):
        """Get Optuna sampler"""
        if self.config.sampler == "tpe":
            return TPESampler(seed=42)
        elif self.config.sampler == "random":
            return optuna.samplers.RandomSampler(seed=42)
        else:
            return TPESampler(seed=42)
    
    def _get_pruner(self):
        """Get Optuna pruner"""
        if self.config.pruner == "median":
            return MedianPruner(n_startup_trials=10, n_warmup_steps=5)
        elif self.config.pruner == "none":
            return optuna.pruners.NopPruner()
        else:
            return MedianPruner()
    
    def _sample_parameters(
        self, 
        trial: Trial, 
        param_space: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Sample parameters from search space"""
        params = {}
        
        for name, config in param_space.items():
            param_type = config.get("type", "float")
            
            if param_type == "int":
                params[name] = trial.suggest_int(
                    name, 
                    config["low"], 
                    config["high"],
                    step=config.get("step", 1)
                )
            elif param_type == "float":
                params[name] = trial.suggest_float(
                    name,
                    config["low"],
                    config["high"],
                    step=config.get("step"),
                    log=config.get("log", False)
                )
            elif param_type == "categorical":
                params[name] = trial.suggest_categorical(
                    name,
                    config["choices"]
                )
            else:
                logger.warning(f"Unknown parameter type: {param_type}")
                params[name] = config.get("default", 0)
        
        return params
    
    async def _execute_in_sandbox(
        self,
        strategy_code: str,
        data: pd.DataFrame,
        params: Dict[str, Any],
        trial_number: int
    ) -> Dict[str, Any]:
        """Execute strategy in sandbox"""
        if not self.sandbox_executor:
            raise RuntimeError("Sandbox executor not configured")
        
        try:
            result = await self.sandbox_executor.execute(
                code=strategy_code,
                data=data.to_dict(),
                params=params,
                timeout=300
            )
            
            if result.get("success"):
                return result.get("metrics", {})
            else:
                logger.error(f"Trial {trial_number} failed: {result.get('error')}")
                # Return bad metrics to penalize this trial
                return self._get_failed_metrics()
                
        except Exception as e:
            logger.error(f"Sandbox execution failed: {e}")
            return self._get_failed_metrics()
    
    async def _execute_directly(
        self,
        strategy_code: str,
        data: pd.DataFrame,
        params: Dict[str, Any],
        trial_number: int
    ) -> Dict[str, Any]:
        """
        Direct execution fallback (LESS SAFE!)
        Use only for testing without sandbox
        """
        logger.warning("Direct execution mode - no sandbox isolation!")
        
        # TODO: Implement safe direct execution
        # For now, return mock metrics
        return {
            "sharpe_ratio": np.random.uniform(-1, 3),
            "max_drawdown": np.random.uniform(0.05, 0.30),
            "total_return": np.random.uniform(-0.2, 0.5),
            "win_rate": np.random.uniform(0.3, 0.7)
        }
    
    def _get_failed_metrics(self) -> Dict[str, Any]:
        """Return very bad metrics for failed trials"""
        return {
            "sharpe_ratio": -999,
            "max_drawdown": 0.99,
            "total_return": -0.99,
            "sortino_ratio": -999,
            "win_rate": 0.0,
            "profit_factor": 0.0
        }
    
    async def _store_optimization_trace(
        self,
        study_name: str,
        param_space: Dict[str, Dict[str, Any]],
        result: OptimizationResult,
        objectives: List[str]
    ):
        """Store optimization in Knowledge Base"""
        if not self.reasoning_storage:
            return
        
        try:
            await self.reasoning_storage.store_reasoning_trace(
                agent_type="optuna",
                task_type="hyperparameter_optimization",
                input_prompt=f"Optimize parameters: {list(param_space.keys())}",
                reasoning_chain={
                    "study_name": study_name,
                    "param_space": param_space,
                    "objectives": objectives,
                    "n_trials": result.n_trials,
                    "optimization_time": result.optimization_time,
                    "all_trials": result.all_trials[:50]  # Limit to first 50
                },
                final_conclusion=f"Best params: {result.best_params}",
                tokens_used=result.n_trials * 100,  # Estimate
                processing_time=result.optimization_time
            )
            logger.info(f"Optimization trace stored: {study_name}")
        except Exception as e:
            logger.error(f"Failed to store optimization trace: {e}")


# Quick example usage
if __name__ == "__main__":
    async def example():
        optimizer = StrategyOptimizer()
        
        # Mock data
        data = pd.DataFrame({
            "open": np.random.rand(100),
            "high": np.random.rand(100),
            "low": np.random.rand(100),
            "close": np.random.rand(100),
            "volume": np.random.rand(100)
        })
        
        # Define parameter space
        param_space = {
            "rsi_period": {"type": "int", "low": 10, "high": 30},
            "rsi_overbought": {"type": "int", "low": 60, "high": 80},
            "rsi_oversold": {"type": "int", "low": 20, "high": 40},
            "stop_loss": {"type": "float", "low": 0.01, "high": 0.05, "step": 0.005}
        }
        
        # Run optimization
        result = await optimizer.optimize_strategy(
            strategy_code="# RSI strategy",
            data=data,
            param_space=param_space,
            objectives=["sharpe_ratio", "max_drawdown"],
            n_trials=20
        )
        
        print(f"\n✅ Optimization complete!")
        print(f"Best params: {result.best_params}")
        print(f"Best values: {result.best_values}")
        print(f"Time: {result.optimization_time:.1f}s")
    
    asyncio.run(example())
