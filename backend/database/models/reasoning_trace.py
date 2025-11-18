"""
Reasoning Trace Models для Knowledge Base
Хранение цепочек reasoning для explainability и auto-enrichment
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base


class ReasoningTrace(Base):
    """
    Трассировка reasoning запросов через мультиагентную систему
    
    Используется для:
        - Audit trail всех AI запросов
        - Chain-of-thought visualization
        - Auto-enrichment новых стратегий из прошлого опыта
        - Debugging и explainability
    """
    __tablename__ = "reasoning_traces"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Request identification
    request_id = Column(String(36), unique=True, index=True, nullable=False)  # UUID
    parent_request_id = Column(String(36), index=True, nullable=True)  # For pipeline steps
    
    # Task context
    task_type = Column(String(50), index=True, nullable=False)  # code-generation, reasoning, etc.
    agent = Column(String(20), index=True, nullable=False)  # copilot, deepseek, sonar-pro
    step_number = Column(Integer, default=0)  # Pipeline step number
    
    # Input/Output
    prompt = Column(Text, nullable=False)  # Original prompt
    system_prompt = Column(Text, nullable=True)  # System context
    result = Column(Text, nullable=True)  # Agent response
    context = Column(JSON, nullable=True)  # Additional context (project structure, etc.)
    
    # Metadata
    model = Column(String(50), nullable=True)  # deepseek-coder, sonar-pro, etc.
    tokens_used = Column(Integer, nullable=True)  # Total tokens consumed
    execution_time = Column(Float, nullable=True)  # Seconds
    status = Column(String(20), default="pending")  # pending, success, error
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    chain_of_thought = relationship("ChainOfThought", back_populates="trace", cascade="all, delete-orphan")
    strategy_evolutions = relationship("StrategyEvolution", back_populates="reasoning_trace")
    
    def __repr__(self):
        return f"<ReasoningTrace(request_id={self.request_id}, agent={self.agent}, task={self.task_type})>"
    
    def to_dict(self):
        """Сериализация для API"""
        return {
            "id": self.id,
            "request_id": self.request_id,
            "parent_request_id": self.parent_request_id,
            "task_type": self.task_type,
            "agent": self.agent,
            "step_number": self.step_number,
            "prompt": self.prompt,
            "result": self.result,
            "model": self.model,
            "tokens_used": self.tokens_used,
            "execution_time": self.execution_time,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "chain_of_thought": [cot.to_dict() for cot in self.chain_of_thought]
        }


class ChainOfThought(Base):
    """
    Подробная декомпозиция reasoning процесса (step-by-step)
    
    Для каждого ReasoningTrace может быть несколько шагов мышления:
        1. Анализ задачи
        2. Формулировка гипотез
        3. Выбор подхода
        4. Генерация решения
        5. Валидация результата
    """
    __tablename__ = "chain_of_thought"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Link to parent trace
    trace_id = Column(Integer, ForeignKey("reasoning_traces.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Step details
    step_number = Column(Integer, nullable=False)  # 1, 2, 3...
    step_name = Column(String(100), nullable=False)  # "analyze", "hypothesize", "generate", etc.
    thought = Column(Text, nullable=False)  # Reasoning at this step
    decision = Column(String(200), nullable=True)  # Decision made at this step
    confidence = Column(Float, nullable=True)  # 0.0 - 1.0 confidence score
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    trace = relationship("ReasoningTrace", back_populates="chain_of_thought")
    
    def __repr__(self):
        return f"<ChainOfThought(trace_id={self.trace_id}, step={self.step_number}, name={self.step_name})>"
    
    def to_dict(self):
        """Сериализация для API"""
        return {
            "id": self.id,
            "step_number": self.step_number,
            "step_name": self.step_name,
            "thought": self.thought,
            "decision": self.decision,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class StrategyEvolution(Base):
    """
    История эволюции торговых стратегий
    
    Отслеживает:
        - Версионирование стратегий
        - Reasoning chains для каждого изменения
        - Performance дельты между версиями
        - Approval/rejection workflow
    """
    __tablename__ = "strategy_evolution"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Strategy identification
    strategy_id = Column(Integer, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False)  # 1, 2, 3...
    parent_version = Column(Integer, nullable=True)  # Previous version (null for v1)
    
    # Changes description
    changes_description = Column(Text, nullable=True)  # Human-readable summary
    changes_diff = Column(JSON, nullable=True)  # Code diff or parameter changes
    reasoning_trace_id = Column(Integer, ForeignKey("reasoning_traces.id"), nullable=True)  # Link to reasoning
    
    # Performance comparison
    performance_before = Column(JSON, nullable=True)  # Metrics from parent_version
    performance_after = Column(JSON, nullable=True)  # Metrics from this version
    performance_delta = Column(JSON, nullable=True)  # Calculated improvement
    
    # Approval workflow
    status = Column(String(20), default="pending")  # pending, approved, rejected, testing
    approved_by = Column(String(100), nullable=True)  # User or "auto"
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    reasoning_trace = relationship("ReasoningTrace", back_populates="strategy_evolutions")
    
    def __repr__(self):
        return f"<StrategyEvolution(strategy_id={self.strategy_id}, version={self.version}, status={self.status})>"
    
    def to_dict(self):
        """Сериализация для API"""
        return {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "version": self.version,
            "parent_version": self.parent_version,
            "changes_description": self.changes_description,
            "changes_diff": self.changes_diff,
            "performance_before": self.performance_before,
            "performance_after": self.performance_after,
            "performance_delta": self.performance_delta,
            "status": self.status,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "reasoning_trace": self.reasoning_trace.to_dict() if self.reasoning_trace else None
        }


class ReasoningKnowledgeBase(Base):
    """
    Knowledge Base для auto-enrichment
    
    Индексирует успешные reasoning chains для:
        - Похожие задачи → похожие решения
        - Best practices extraction
        - Anti-patterns detection
        - Auto-suggestion при новых запросах
    """
    __tablename__ = "reasoning_knowledge_base"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Pattern identification
    pattern_type = Column(String(50), index=True, nullable=False)  # best_practice, anti_pattern, optimization
    task_category = Column(String(50), index=True, nullable=False)  # trend_following, mean_reversion, etc.
    
    # Pattern details
    pattern_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    example_trace_id = Column(Integer, ForeignKey("reasoning_traces.id"), nullable=True)  # Reference example
    
    # Usage statistics
    usage_count = Column(Integer, default=0)  # How many times this pattern was suggested
    success_rate = Column(Float, default=0.0)  # % of successful applications (0.0 - 1.0)
    avg_performance_improvement = Column(Float, nullable=True)  # Average Sharpe ratio improvement
    
    # Metadata
    tags = Column(JSON, nullable=True)  # ["momentum", "wyckoff", "volume_profile"]
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    last_used_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<ReasoningKnowledgeBase(pattern={self.pattern_name}, type={self.pattern_type})>"
    
    def to_dict(self):
        """Сериализация для API"""
        return {
            "id": self.id,
            "pattern_type": self.pattern_type,
            "task_category": self.task_category,
            "pattern_name": self.pattern_name,
            "description": self.description,
            "usage_count": self.usage_count,
            "success_rate": self.success_rate,
            "avg_performance_improvement": self.avg_performance_improvement,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None
        }
