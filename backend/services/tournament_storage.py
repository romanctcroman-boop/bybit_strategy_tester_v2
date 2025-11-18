"""
Tournament Storage Service для работы с БД
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from backend.database.models.tournament import (
    Tournament,
    TournamentParticipant,
    TournamentHistory,
    TournamentStatusEnum
)
from backend.services.strategy_arena import TournamentResult, StrategyMetrics

logger = logging.getLogger(__name__)


class TournamentStorageService:
    """
    Service для сохранения и извлечения турнирных данных
    
    Features:
        - Create tournament records
        - Save participant results
        - Update tournament history
        - Query tournament statistics
        - Get leaderboards
    """
    
    def __init__(self, db_session: Session):
        self.session = db_session
    
    def create_tournament(
        self,
        tournament_id: str,
        tournament_name: str,
        scoring_weights: Dict[str, float],
        max_workers: int = 5
    ) -> Tournament:
        """Create new tournament record"""
        
        tournament = Tournament(
            tournament_id=tournament_id,
            tournament_name=tournament_name,
            status=TournamentStatusEnum.PENDING,
            started_at=datetime.utcnow(),
            scoring_weights=scoring_weights,
            max_workers=max_workers
        )
        
        self.session.add(tournament)
        self.session.commit()
        self.session.refresh(tournament)
        
        logger.info(f"Created tournament: {tournament_name} (ID: {tournament_id})")
        return tournament
    
    def save_tournament_result(self, result: TournamentResult) -> Tournament:
        """
        Save complete tournament result to database
        
        Creates/updates:
            - Tournament record
            - TournamentParticipant records
            - TournamentHistory records (aggregate stats)
        """
        
        # Get or create tournament
        tournament = self.session.query(Tournament).filter_by(
            tournament_id=result.tournament_id
        ).first()
        
        if not tournament:
            tournament = Tournament(
                tournament_id=result.tournament_id,
                tournament_name=result.tournament_name,
                started_at=result.started_at
            )
            self.session.add(tournament)
        
        # Update tournament fields
        tournament.status = TournamentStatusEnum[result.status.upper()]
        tournament.completed_at = result.completed_at
        tournament.total_participants = result.total_participants
        tournament.successful_backtests = result.successful_backtests
        tournament.failed_backtests = result.failed_backtests
        tournament.winner_id = result.winner_id
        tournament.winner_name = result.winner_name
        
        if result.ranked_strategies:
            tournament.winner_score = result.ranked_strategies[0][1]
        
        self.session.commit()
        self.session.refresh(tournament)
        
        # Save participants
        for strategy_id, metrics in result.strategy_metrics.items():
            self._save_participant(tournament.id, strategy_id, metrics, result.ranked_strategies)
        
        # Update history for each participant
        for strategy_id in result.strategy_metrics.keys():
            self._update_strategy_history(strategy_id)
        
        logger.info(f"Saved tournament result: {result.tournament_name}")
        return tournament
    
    def _save_participant(
        self,
        tournament_id: int,
        strategy_id: str,
        metrics: StrategyMetrics,
        ranked_strategies: List[tuple]
    ):
        """Save tournament participant"""
        
        # Find rank and score
        rank = None
        final_score = 0.0
        for idx, (sid, score) in enumerate(ranked_strategies, 1):
            if sid == strategy_id:
                rank = idx
                final_score = score
                break
        
        participant = TournamentParticipant(
            tournament_id=tournament_id,
            strategy_id=strategy_id,
            strategy_name=metrics.strategy_name,
            total_return=metrics.total_return,
            sharpe_ratio=metrics.sharpe_ratio,
            sortino_ratio=metrics.sortino_ratio,
            max_drawdown=metrics.max_drawdown,
            win_rate=metrics.win_rate,
            profit_factor=metrics.profit_factor,
            total_trades=metrics.total_trades,
            winning_trades=metrics.winning_trades,
            losing_trades=metrics.losing_trades,
            avg_win=metrics.avg_win,
            avg_loss=metrics.avg_loss,
            volatility=metrics.volatility,
            var_95=metrics.var_95,
            final_score=final_score,
            rank=rank,
            backtest_duration=metrics.backtest_duration,
            errors=metrics.errors if metrics.errors else None,
            executed_at=datetime.utcnow()
        )
        
        self.session.add(participant)
        self.session.commit()
    
    def _update_strategy_history(self, strategy_id: str):
        """Update aggregated history for strategy"""
        
        # Get all participations for this strategy
        participations = self.session.query(TournamentParticipant).filter_by(
            strategy_id=strategy_id
        ).order_by(desc(TournamentParticipant.executed_at)).all()
        
        if not participations:
            return
        
        # Calculate aggregates
        total_tournaments = len(participations)
        total_wins = len([p for p in participations if p.rank == 1])
        total_top3 = len([p for p in participations if p.rank and p.rank <= 3])
        total_top10 = len([p for p in participations if p.rank and p.rank <= 10])
        
        scores = [p.final_score for p in participations if p.final_score is not None]
        ranks = [p.rank for p in participations if p.rank is not None]
        
        avg_score = sum(scores) / len(scores) if scores else 0.0
        avg_rank = sum(ranks) / len(ranks) if ranks else 0.0
        best_score = max(scores) if scores else 0.0
        worst_score = min(scores) if scores else 0.0
        
        # Performance aggregates
        returns = [p.total_return for p in participations if p.total_return is not None]
        sharpes = [p.sharpe_ratio for p in participations if p.sharpe_ratio is not None]
        win_rates = [p.win_rate for p in participations if p.win_rate is not None]
        
        avg_return = sum(returns) / len(returns) if returns else 0.0
        avg_sharpe = sum(sharpes) / len(sharpes) if sharpes else 0.0
        avg_win_rate = sum(win_rates) / len(win_rates) if win_rates else 0.0
        
        # Recent performance (last 5)
        recent_scores = scores[:5]
        recent_ranks = ranks[:5]
        
        # Get or create history record
        history = self.session.query(TournamentHistory).filter_by(
            strategy_id=strategy_id
        ).first()
        
        if not history:
            history = TournamentHistory(
                strategy_id=strategy_id,
                strategy_name=participations[0].strategy_name,
                first_tournament_at=participations[-1].executed_at
            )
            self.session.add(history)
        
        # Update history
        history.total_tournaments = total_tournaments
        history.total_wins = total_wins
        history.total_top3 = total_top3
        history.total_top10 = total_top10
        history.avg_score = avg_score
        history.avg_rank = avg_rank
        history.best_score = best_score
        history.worst_score = worst_score
        history.avg_return = avg_return
        history.avg_sharpe = avg_sharpe
        history.avg_win_rate = avg_win_rate
        history.recent_scores = recent_scores
        history.recent_ranks = recent_ranks
        history.last_tournament_at = participations[0].executed_at
        history.updated_at = datetime.utcnow()
        
        self.session.commit()
    
    def get_tournament(self, tournament_id: str) -> Optional[Tournament]:
        """Get tournament by ID"""
        return self.session.query(Tournament).filter_by(
            tournament_id=tournament_id
        ).first()
    
    def get_recent_tournaments(self, limit: int = 10) -> List[Tournament]:
        """Get recent tournaments"""
        return self.session.query(Tournament).order_by(
            desc(Tournament.started_at)
        ).limit(limit).all()
    
    def get_tournament_participants(self, tournament_id: int) -> List[TournamentParticipant]:
        """Get all participants for tournament"""
        return self.session.query(TournamentParticipant).filter_by(
            tournament_id=tournament_id
        ).order_by(TournamentParticipant.rank).all()
    
    def get_strategy_history(self, strategy_id: str) -> Optional[TournamentHistory]:
        """Get aggregated history for strategy"""
        return self.session.query(TournamentHistory).filter_by(
            strategy_id=strategy_id
        ).first()
    
    def get_global_leaderboard(self, limit: int = 100) -> List[TournamentHistory]:
        """
        Get global leaderboard (all-time best strategies)
        
        Sorted by: total_wins DESC, avg_score DESC
        """
        return self.session.query(TournamentHistory).order_by(
            desc(TournamentHistory.total_wins),
            desc(TournamentHistory.avg_score)
        ).limit(limit).all()
    
    def get_tournament_statistics(self) -> Dict[str, Any]:
        """Get overall tournament statistics"""
        
        total_tournaments = self.session.query(func.count(Tournament.id)).scalar()
        total_strategies = self.session.query(func.count(TournamentHistory.id)).scalar()
        
        completed_tournaments = self.session.query(func.count(Tournament.id)).filter(
            Tournament.status == TournamentStatusEnum.COMPLETED
        ).scalar()
        
        return {
            "total_tournaments": total_tournaments or 0,
            "completed_tournaments": completed_tournaments or 0,
            "total_unique_strategies": total_strategies or 0,
            "last_tournament": self.session.query(Tournament).order_by(
                desc(Tournament.started_at)
            ).first()
        }
