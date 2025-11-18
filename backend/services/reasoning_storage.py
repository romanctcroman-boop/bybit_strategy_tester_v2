"""
Reasoning Storage Service
Автоматическое логирование reasoning chains для Knowledge Base
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_

from backend.database.models.reasoning_trace import (
    ReasoningTrace,
    ChainOfThought,
    StrategyEvolution,
    ReasoningKnowledgeBase
)

logger = logging.getLogger(__name__)


class ReasoningStorageService:
    """
    Service для работы с reasoning traces
    
    Features:
        - Автоматическое логирование всех AI запросов
        - Chain-of-thought декомпозиция
        - Query API для анализа
        - Auto-enrichment suggestions
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    # ═══════════════════════════════════════════════════════════════════════
    # CREATE OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════
    
    def create_trace(
        self,
        request_id: str,
        task_type: str,
        agent: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        parent_request_id: Optional[str] = None,
        step_number: int = 0
    ) -> ReasoningTrace:
        """
        Создать новый reasoning trace
        
        Args:
            request_id: Уникальный ID запроса (UUID)
            task_type: Тип задачи (code-generation, reasoning, etc.)
            agent: Агент (copilot, deepseek, sonar-pro)
            prompt: Промпт пользователя
            system_prompt: Системный промпт (optional)
            context: Дополнительный контекст (optional)
            parent_request_id: ID родительского запроса для pipeline (optional)
            step_number: Номер шага в pipeline (optional)
        
        Returns:
            ReasoningTrace объект
        """
        trace = ReasoningTrace(
            request_id=request_id,
            parent_request_id=parent_request_id,
            task_type=task_type,
            agent=agent,
            step_number=step_number,
            prompt=prompt,
            system_prompt=system_prompt,
            context=context,
            status="pending"
        )
        
        self.db.add(trace)
        self.db.commit()
        self.db.refresh(trace)
        
        logger.info(f"Created reasoning trace: {request_id} ({task_type} via {agent})")
        
        return trace
    
    def update_trace_result(
        self,
        request_id: str,
        result: str,
        model: Optional[str] = None,
        tokens_used: Optional[int] = None,
        execution_time: Optional[float] = None,
        status: str = "success",
        error_message: Optional[str] = None
    ) -> Optional[ReasoningTrace]:
        """
        Обновить результат reasoning trace
        
        Args:
            request_id: UUID запроса
            result: Результат от агента
            model: Модель использованная агентом
            tokens_used: Количество токенов
            execution_time: Время выполнения (секунды)
            status: success/error
            error_message: Сообщение об ошибке (если есть)
        
        Returns:
            Обновлённый ReasoningTrace или None
        """
        trace = self.get_trace_by_request_id(request_id)
        
        if not trace:
            logger.warning(f"Trace not found for request_id: {request_id}")
            return None
        
        trace.result = result
        trace.model = model
        trace.tokens_used = tokens_used
        trace.execution_time = execution_time
        trace.status = status
        trace.error_message = error_message
        trace.completed_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(trace)
        
        logger.info(f"Updated reasoning trace: {request_id} (status={status}, time={execution_time}s)")
        
        return trace
    
    def add_chain_of_thought_step(
        self,
        request_id: str,
        step_number: int,
        step_name: str,
        thought: str,
        decision: Optional[str] = None,
        confidence: Optional[float] = None
    ) -> Optional[ChainOfThought]:
        """
        Добавить шаг chain-of-thought reasoning
        
        Args:
            request_id: UUID запроса
            step_number: Номер шага (1, 2, 3...)
            step_name: Название шага (analyze, hypothesize, etc.)
            thought: Reasoning на этом шаге
            decision: Принятое решение (optional)
            confidence: Уверенность 0.0-1.0 (optional)
        
        Returns:
            ChainOfThought объект или None
        """
        trace = self.get_trace_by_request_id(request_id)
        
        if not trace:
            logger.warning(f"Trace not found for request_id: {request_id}")
            return None
        
        cot_step = ChainOfThought(
            trace_id=trace.id,
            step_number=step_number,
            step_name=step_name,
            thought=thought,
            decision=decision,
            confidence=confidence
        )
        
        self.db.add(cot_step)
        self.db.commit()
        self.db.refresh(cot_step)
        
        logger.debug(f"Added chain-of-thought step {step_number} for {request_id}")
        
        return cot_step
    
    # ═══════════════════════════════════════════════════════════════════════
    # READ OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_trace_by_request_id(self, request_id: str) -> Optional[ReasoningTrace]:
        """Получить trace по request_id"""
        return self.db.query(ReasoningTrace).filter(
            ReasoningTrace.request_id == request_id
        ).first()
    
    def get_trace_by_id(self, trace_id: int) -> Optional[ReasoningTrace]:
        """Получить trace по ID"""
        return self.db.query(ReasoningTrace).filter(
            ReasoningTrace.id == trace_id
        ).first()
    
    def get_pipeline_traces(self, parent_request_id: str) -> List[ReasoningTrace]:
        """
        Получить все traces из pipeline по parent_request_id
        
        Возвращает отсортированный список по step_number
        """
        return self.db.query(ReasoningTrace).filter(
            ReasoningTrace.parent_request_id == parent_request_id
        ).order_by(ReasoningTrace.step_number).all()
    
    def get_recent_traces(
        self,
        limit: int = 50,
        task_type: Optional[str] = None,
        agent: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[ReasoningTrace]:
        """
        Получить последние traces с фильтрами
        
        Args:
            limit: Максимум записей
            task_type: Фильтр по типу задачи (optional)
            agent: Фильтр по агенту (optional)
            status: Фильтр по статусу (optional)
        
        Returns:
            Список ReasoningTrace
        """
        query = self.db.query(ReasoningTrace)
        
        if task_type:
            query = query.filter(ReasoningTrace.task_type == task_type)
        if agent:
            query = query.filter(ReasoningTrace.agent == agent)
        if status:
            query = query.filter(ReasoningTrace.status == status)
        
        return query.order_by(desc(ReasoningTrace.created_at)).limit(limit).all()
    
    def search_traces_by_prompt(
        self,
        search_term: str,
        limit: int = 20
    ) -> List[ReasoningTrace]:
        """
        Полнотекстовый поиск по промптам
        
        Args:
            search_term: Поисковый запрос
            limit: Максимум результатов
        
        Returns:
            Список ReasoningTrace
        """
        return self.db.query(ReasoningTrace).filter(
            or_(
                ReasoningTrace.prompt.ilike(f"%{search_term}%"),
                ReasoningTrace.result.ilike(f"%{search_term}%")
            )
        ).order_by(desc(ReasoningTrace.created_at)).limit(limit).all()
    
    # ═══════════════════════════════════════════════════════════════════════
    # STRATEGY EVOLUTION
    # ═══════════════════════════════════════════════════════════════════════
    
    def create_strategy_evolution(
        self,
        strategy_id: int,
        version: int,
        parent_version: Optional[int],
        changes_description: Optional[str],
        changes_diff: Optional[Dict[str, Any]],
        reasoning_trace_id: Optional[int],
        performance_before: Optional[Dict[str, Any]] = None,
        performance_after: Optional[Dict[str, Any]] = None
    ) -> StrategyEvolution:
        """
        Создать запись об эволюции стратегии
        
        Args:
            strategy_id: ID стратегии
            version: Номер версии
            parent_version: Родительская версия (optional)
            changes_description: Описание изменений
            changes_diff: Diff изменений (JSON)
            reasoning_trace_id: ID связанного reasoning trace
            performance_before: Метрики до изменений (optional)
            performance_after: Метрики после изменений (optional)
        
        Returns:
            StrategyEvolution объект
        """
        # Calculate performance delta if both are provided
        performance_delta = None
        if performance_before and performance_after:
            performance_delta = {
                key: performance_after.get(key, 0) - performance_before.get(key, 0)
                for key in performance_before.keys()
            }
        
        evolution = StrategyEvolution(
            strategy_id=strategy_id,
            version=version,
            parent_version=parent_version,
            changes_description=changes_description,
            changes_diff=changes_diff,
            reasoning_trace_id=reasoning_trace_id,
            performance_before=performance_before,
            performance_after=performance_after,
            performance_delta=performance_delta,
            status="pending"
        )
        
        self.db.add(evolution)
        self.db.commit()
        self.db.refresh(evolution)
        
        logger.info(f"Created strategy evolution: strategy_id={strategy_id}, version={version}")
        
        return evolution
    
    def approve_strategy_evolution(
        self,
        evolution_id: int,
        approved_by: str
    ) -> Optional[StrategyEvolution]:
        """
        Approve strategy evolution
        
        Args:
            evolution_id: ID эволюции
            approved_by: Имя пользователя или "auto"
        
        Returns:
            Обновлённый StrategyEvolution или None
        """
        evolution = self.db.query(StrategyEvolution).filter(
            StrategyEvolution.id == evolution_id
        ).first()
        
        if not evolution:
            return None
        
        evolution.status = "approved"
        evolution.approved_by = approved_by
        evolution.approved_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(evolution)
        
        logger.info(f"Approved strategy evolution {evolution_id} by {approved_by}")
        
        return evolution
    
    def reject_strategy_evolution(
        self,
        evolution_id: int,
        rejection_reason: str
    ) -> Optional[StrategyEvolution]:
        """
        Reject strategy evolution
        
        Args:
            evolution_id: ID эволюции
            rejection_reason: Причина отклонения
        
        Returns:
            Обновлённый StrategyEvolution или None
        """
        evolution = self.db.query(StrategyEvolution).filter(
            StrategyEvolution.id == evolution_id
        ).first()
        
        if not evolution:
            return None
        
        evolution.status = "rejected"
        evolution.rejection_reason = rejection_reason
        
        self.db.commit()
        self.db.refresh(evolution)
        
        logger.info(f"Rejected strategy evolution {evolution_id}: {rejection_reason}")
        
        return evolution
    
    def get_strategy_history(self, strategy_id: int) -> List[StrategyEvolution]:
        """
        Получить полную историю эволюции стратегии
        
        Args:
            strategy_id: ID стратегии
        
        Returns:
            Список StrategyEvolution отсортированный по версии
        """
        return self.db.query(StrategyEvolution).filter(
            StrategyEvolution.strategy_id == strategy_id
        ).order_by(StrategyEvolution.version).all()
    
    # ═══════════════════════════════════════════════════════════════════════
    # KNOWLEDGE BASE (AUTO-ENRICHMENT)
    # ═══════════════════════════════════════════════════════════════════════
    
    def add_pattern_to_knowledge_base(
        self,
        pattern_type: str,
        task_category: str,
        pattern_name: str,
        description: str,
        example_trace_id: Optional[int] = None,
        tags: Optional[List[str]] = None
    ) -> ReasoningKnowledgeBase:
        """
        Добавить паттерн в Knowledge Base
        
        Args:
            pattern_type: best_practice, anti_pattern, optimization
            task_category: trend_following, mean_reversion, etc.
            pattern_name: Название паттерна
            description: Описание
            example_trace_id: ID примера trace (optional)
            tags: Теги для поиска (optional)
        
        Returns:
            ReasoningKnowledgeBase объект
        """
        kb_entry = ReasoningKnowledgeBase(
            pattern_type=pattern_type,
            task_category=task_category,
            pattern_name=pattern_name,
            description=description,
            example_trace_id=example_trace_id,
            tags=tags or []
        )
        
        self.db.add(kb_entry)
        self.db.commit()
        self.db.refresh(kb_entry)
        
        logger.info(f"Added pattern to KB: {pattern_name} ({pattern_type})")
        
        return kb_entry
    
    def suggest_patterns(
        self,
        task_category: str,
        limit: int = 5
    ) -> List[ReasoningKnowledgeBase]:
        """
        Предложить best practices для категории задачи
        
        Args:
            task_category: Категория задачи
            limit: Максимум предложений
        
        Returns:
            Список ReasoningKnowledgeBase отсортированный по success_rate
        """
        return self.db.query(ReasoningKnowledgeBase).filter(
            and_(
                ReasoningKnowledgeBase.task_category == task_category,
                ReasoningKnowledgeBase.pattern_type == "best_practice"
            )
        ).order_by(desc(ReasoningKnowledgeBase.success_rate)).limit(limit).all()
    
    def update_pattern_statistics(
        self,
        pattern_id: int,
        success: bool,
        performance_improvement: Optional[float] = None
    ) -> Optional[ReasoningKnowledgeBase]:
        """
        Обновить статистику использования паттерна
        
        Args:
            pattern_id: ID паттерна
            success: Успешно применён или нет
            performance_improvement: Улучшение performance (optional)
        
        Returns:
            Обновлённый ReasoningKnowledgeBase или None
        """
        pattern = self.db.query(ReasoningKnowledgeBase).filter(
            ReasoningKnowledgeBase.id == pattern_id
        ).first()
        
        if not pattern:
            return None
        
        # Update usage count
        pattern.usage_count += 1
        
        # Update success rate (running average)
        if success:
            new_success_count = (pattern.success_rate * (pattern.usage_count - 1)) + 1
            pattern.success_rate = new_success_count / pattern.usage_count
        else:
            new_success_count = pattern.success_rate * (pattern.usage_count - 1)
            pattern.success_rate = new_success_count / pattern.usage_count
        
        # Update performance improvement (running average)
        if performance_improvement is not None:
            if pattern.avg_performance_improvement is None:
                pattern.avg_performance_improvement = performance_improvement
            else:
                total = (pattern.avg_performance_improvement * (pattern.usage_count - 1)) + performance_improvement
                pattern.avg_performance_improvement = total / pattern.usage_count
        
        pattern.last_used_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(pattern)
        
        logger.info(f"Updated pattern statistics: {pattern.pattern_name} (usage={pattern.usage_count}, success_rate={pattern.success_rate:.2f})")
        
        return pattern
    
    # ═══════════════════════════════════════════════════════════════════════
    # STATISTICS & ANALYTICS
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_agent_statistics(self, agent: str, days: int = 7) -> Dict[str, Any]:
        """
        Получить статистику работы агента за период
        
        Args:
            agent: Имя агента (copilot, deepseek, sonar-pro)
            days: Количество дней для анализа
        
        Returns:
            Dict со статистикой
        """
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        traces = self.db.query(ReasoningTrace).filter(
            and_(
                ReasoningTrace.agent == agent,
                ReasoningTrace.created_at >= cutoff_date
            )
        ).all()
        
        if not traces:
            return {
                "agent": agent,
                "period_days": days,
                "total_requests": 0
            }
        
        total_requests = len(traces)
        successful = sum(1 for t in traces if t.status == "success")
        failed = sum(1 for t in traces if t.status == "error")
        
        total_tokens = sum(t.tokens_used for t in traces if t.tokens_used)
        total_time = sum(t.execution_time for t in traces if t.execution_time)
        
        return {
            "agent": agent,
            "period_days": days,
            "total_requests": total_requests,
            "successful_requests": successful,
            "failed_requests": failed,
            "success_rate": successful / total_requests if total_requests > 0 else 0,
            "total_tokens_used": total_tokens,
            "total_execution_time": total_time,
            "avg_execution_time": total_time / total_requests if total_requests > 0 else 0,
            "avg_tokens_per_request": total_tokens / total_requests if total_requests > 0 else 0
        }
