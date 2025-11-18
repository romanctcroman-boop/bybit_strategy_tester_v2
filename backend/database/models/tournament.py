"""
Database models для Tournament System
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from backend.database.base import Base


class TournamentStatusEnum(str, enum.Enum):
    """Статус турнира"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Tournament(Base):
    """
    Таблица турниров
    
    Хранит информацию о турнирах стратегий
    """
    __tablename__ = "tournaments"
    
    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(String(100), unique=True, nullable=False, index=True)
    tournament_name = Column(String(255), nullable=False)
    
    status = Column(SQLEnum(TournamentStatusEnum), default=TournamentStatusEnum.PENDING, nullable=False, index=True)
    
    # Timestamps
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Statistics
    total_participants = Column(Integer, default=0)
    successful_backtests = Column(Integer, default=0)
    failed_backtests = Column(Integer, default=0)
    
    # Winner info
    winner_id = Column(String(100), nullable=True)
    winner_name = Column(String(255), nullable=True)
    winner_score = Column(Float, nullable=True)
    
    # Configuration
    scoring_weights = Column(JSON, nullable=True)  # {"sharpe_ratio": 0.3, ...}
    max_workers = Column(Integer, default=5)
    
    # Relationships
    participants = relationship("TournamentParticipant", back_populates="tournament", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        {"comment": "Tournament competitions between trading strategies"}
    )


class TournamentParticipant(Base):
    """
    Таблица участников турнира
    
    Связь между турниром и стратегией с результатами
    """
    __tablename__ = "tournament_participants"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign keys
    tournament_id = Column(Integer, ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Strategy info
    strategy_id = Column(String(100), nullable=False, index=True)
    strategy_name = Column(String(255), nullable=False)
    strategy_code = Column(Text, nullable=True)  # Optional: store strategy code
    
    # Performance metrics
    total_return = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, default=0.0)
    sortino_ratio = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)
    profit_factor = Column(Float, default=0.0)
    
    # Trade statistics
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    avg_win = Column(Float, default=0.0)
    avg_loss = Column(Float, default=0.0)
    
    # Risk metrics
    volatility = Column(Float, default=0.0)
    var_95 = Column(Float, default=0.0)
    
    # Tournament results
    final_score = Column(Float, default=0.0)
    rank = Column(Integer, nullable=True)
    
    # Execution info
    backtest_duration = Column(Float, default=0.0)
    errors = Column(JSON, nullable=True)  # List of error messages
    
    # Timestamps
    executed_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    tournament = relationship("Tournament", back_populates="participants")
    
    # Indexes
    __table_args__ = (
        {"comment": "Tournament participants with backtest results"}
    )


class TournamentHistory(Base):
    """
    История турниров для tracking
    
    Агрегированная статистика по стратегиям
    """
    __tablename__ = "tournament_history"
    
    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(String(100), nullable=False, index=True)
    strategy_name = Column(String(255), nullable=False)
    
    # Aggregate statistics
    total_tournaments = Column(Integer, default=0)
    total_wins = Column(Integer, default=0)
    total_top3 = Column(Integer, default=0)
    total_top10 = Column(Integer, default=0)
    
    # Performance aggregates
    avg_score = Column(Float, default=0.0)
    avg_rank = Column(Float, default=0.0)
    best_score = Column(Float, default=0.0)
    worst_score = Column(Float, default=0.0)
    
    # Win rate history
    avg_return = Column(Float, default=0.0)
    avg_sharpe = Column(Float, default=0.0)
    avg_win_rate = Column(Float, default=0.0)
    
    # Recent performance (last 5 tournaments)
    recent_scores = Column(JSON, nullable=True)  # List of last 5 scores
    recent_ranks = Column(JSON, nullable=True)  # List of last 5 ranks
    
    # Timestamps
    first_tournament_at = Column(DateTime, nullable=True)
    last_tournament_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        {"comment": "Aggregated tournament history per strategy"}
    )
