"""
Chat History API Router - Milestone 4.3

Provides backend sync for AI Studio conversation history.
Replaces localStorage with persistent server-side storage.

Endpoints:
- GET /api/v1/chat/history - List conversations
- GET /api/v1/chat/history/{id} - Get specific conversation
- POST /api/v1/chat/history - Save new conversation
- PUT /api/v1/chat/history/{id} - Update conversation
- DELETE /api/v1/chat/history/{id} - Delete conversation
- POST /api/v1/chat/history/sync - Bulk sync from localStorage
- DELETE /api/v1/chat/history/clear - Clear all history
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.database.models import ChatConversation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat History"])


# ==============================================================================
# Models
# ==============================================================================


class ChatTab(str, Enum):
    """Available chat tabs in AI Studio"""

    STRATEGY = "strategy"
    RESEARCH = "research"
    RISK = "risk"


class AgentType(str, Enum):
    """AI Agent types"""

    DEEPSEEK = "deepseek"
    PERPLEXITY = "perplexity"
    UNIFIED = "unified"


class ConversationMessage(BaseModel):
    """Single message in conversation"""

    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    reasoning: str | None = Field(None, description="DeepSeek thinking/reasoning")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ConversationCreate(BaseModel):
    """Create new conversation"""

    prompt: str = Field(..., min_length=1, max_length=10000)
    response: str = Field(..., min_length=1)
    reasoning: str | None = Field(None, description="DeepSeek thinking output")
    tab: ChatTab = Field(default=ChatTab.STRATEGY)
    agent: AgentType = Field(default=AgentType.DEEPSEEK)
    timestamp: int | None = Field(None, description="Client timestamp (ms)")


class ConversationUpdate(BaseModel):
    """Update existing conversation"""

    prompt: str | None = Field(None, min_length=1, max_length=10000)
    response: str | None = Field(None)
    tab: ChatTab | None = None
    starred: bool | None = None
    title: str | None = Field(None, max_length=200)


class ConversationResponse(BaseModel):
    """Conversation response model"""

    id: str
    prompt: str
    response: str
    reasoning: str | None = None
    tab: ChatTab
    agent: AgentType
    title: str | None = None
    starred: bool = False
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    """List of conversations"""

    conversations: list[ConversationResponse]
    total: int
    page: int
    per_page: int
    has_more: bool


class SyncRequest(BaseModel):
    """Bulk sync request from localStorage"""

    conversations: list[ConversationCreate]
    clear_existing: bool = Field(
        default=False, description="Clear server history before sync"
    )


class SyncResponse(BaseModel):
    """Sync operation response"""

    synced: int
    skipped: int
    errors: list[str]


def _generate_title(prompt: str) -> str:
    """Generate a title from the prompt"""
    # Take first line or first 50 chars
    first_line = prompt.split("\n")[0].strip()
    if len(first_line) > 50:
        return first_line[:47] + "..."
    return first_line


# ==============================================================================
# Endpoints
# ==============================================================================


@router.get("/history", response_model=ConversationListResponse)
async def list_conversations(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    tab: ChatTab | None = Query(None, description="Filter by tab"),
    starred: bool | None = Query(None, description="Filter starred only"),
    search: str | None = Query(None, description="Search in prompts", alias="q"),
    days: int | None = Query(None, ge=1, le=365, description="Last N days"),
    db: Session = Depends(get_db),
) -> ConversationListResponse:
    """List conversation history with pagination and filters (DB-backed)."""
    try:
        query = db.query(ChatConversation)

        if tab:
            query = query.filter(ChatConversation.tab == tab.value)

        if starred is not None:
            query = query.filter(ChatConversation.starred == starred)

        if search:
            pattern = f"%{search.lower()}%"
            query = query.filter(
                or_(
                    func.lower(ChatConversation.prompt).like(pattern),
                    func.lower(ChatConversation.response).like(pattern),
                )
            )

        if days:
            cutoff = datetime.now(UTC) - timedelta(days=days)
            query = query.filter(ChatConversation.created_at >= cutoff)

        total = query.count()
        start = (page - 1) * per_page
        items = (
            query.order_by(ChatConversation.created_at.desc())
            .offset(start)
            .limit(per_page)
            .all()
        )

        return ConversationListResponse(
            conversations=[
                ConversationResponse(
                    id=c.id,
                    prompt=c.prompt,
                    response=c.response,
                    reasoning=c.reasoning,
                    tab=ChatTab(c.tab),
                    agent=AgentType(c.agent),
                    title=c.title,
                    starred=c.starred,
                    created_at=c.created_at,
                    updated_at=c.updated_at,
                )
                for c in items
            ],
            total=total,
            page=page,
            per_page=per_page,
            has_more=(start + per_page) < total,
        )

    except Exception as e:
        logger.error(f"Failed to list conversations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str, db: Session = Depends(get_db)
) -> ConversationResponse:
    """Get specific conversation by ID (DB-backed)."""
    conversation = db.get(ChatConversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationResponse(
        id=conversation.id,
        prompt=conversation.prompt,
        response=conversation.response,
        reasoning=conversation.reasoning,
        tab=ChatTab(conversation.tab),
        agent=AgentType(conversation.agent),
        title=conversation.title,
        starred=conversation.starred,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


@router.post("/history", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    data: ConversationCreate, db: Session = Depends(get_db)
) -> ConversationResponse:
    """Save new conversation to persistent store."""
    try:
        now = datetime.now(UTC)
        created_at = (
            datetime.fromtimestamp(data.timestamp / 1000, tz=UTC)
            if data.timestamp
            else now
        )

        conversation = ChatConversation(
            id=str(uuid.uuid4()),
            prompt=data.prompt,
            response=data.response,
            reasoning=data.reasoning,
            tab=data.tab.value,
            agent=data.agent.value,
            title=_generate_title(data.prompt),
            starred=False,
            created_at=created_at,
            updated_at=now,
        )

        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        logger.info(
            "Created conversation %s for tab %s", conversation.id, data.tab.value
        )

        return ConversationResponse(
            id=conversation.id,
            prompt=conversation.prompt,
            response=conversation.response,
            reasoning=conversation.reasoning,
            tab=ChatTab(conversation.tab),
            agent=AgentType(conversation.agent),
            title=conversation.title,
            starred=conversation.starred,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )

    except Exception as e:
        logger.error(f"Failed to create conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/history/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: str, data: ConversationUpdate, db: Session = Depends(get_db)
) -> ConversationResponse:
    """Update an existing conversation."""
    conversation = db.get(ChatConversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if data.prompt is not None:
        conversation.prompt = data.prompt
        # Refresh title if user did not provide a new one
        if data.title is None:
            conversation.title = _generate_title(data.prompt)
    if data.response is not None:
        conversation.response = data.response
    if data.tab is not None:
        conversation.tab = data.tab.value
    if data.starred is not None:
        conversation.starred = data.starred
    if data.title is not None:
        conversation.title = data.title

    conversation.updated_at = datetime.now(UTC)

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return ConversationResponse(
        id=conversation.id,
        prompt=conversation.prompt,
        response=conversation.response,
        reasoning=conversation.reasoning,
        tab=ChatTab(conversation.tab),
        agent=AgentType(conversation.agent),
        title=conversation.title,
        starred=conversation.starred,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


# NOTE: /history/clear MUST be defined BEFORE /history/{conversation_id}
# Otherwise FastAPI will match "clear" as a conversation_id
@router.delete("/history/clear", status_code=200)
async def clear_history(db: Session = Depends(get_db)) -> dict:
    """Clear all conversation history."""
    deleted = db.query(ChatConversation).delete()
    db.commit()
    logger.info("Cleared %s conversations", deleted)
    return {"message": "History cleared", "deleted": deleted}


@router.delete("/history/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str, db: Session = Depends(get_db)
) -> None:
    """Delete a conversation."""
    conversation = db.get(ChatConversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    db.delete(conversation)
    db.commit()
    logger.info("Deleted conversation %s", conversation_id)


@router.post("/history/sync", response_model=SyncResponse)
async def sync_conversations(
    data: SyncRequest, db: Session = Depends(get_db)
) -> SyncResponse:
    """
    🔄 Bulk sync from localStorage

    Import conversations from client localStorage to server.
    Useful for migrating existing local history to server-side storage.

    Args:
        data: List of conversations to sync
        clear_existing: If true, clear all existing server history first

    Returns:
        Sync results with counts

    Example:
        POST /chat/history/sync
        {
            "conversations": [...],
            "clear_existing": false
        }
    """
    try:
        if data.clear_existing:
            db.query(ChatConversation).delete()
            db.commit()
            logger.info("Cleared existing conversations for sync")

        synced = 0
        skipped = 0
        errors: list[str] = []

        for conv in data.conversations:
            try:
                now = datetime.now(UTC)
                created_at = (
                    datetime.fromtimestamp(conv.timestamp / 1000, tz=UTC)
                    if conv.timestamp
                    else now
                )

                conversation = ChatConversation(
                    id=str(uuid.uuid4()),
                    prompt=conv.prompt,
                    response=conv.response,
                    reasoning=conv.reasoning,
                    tab=conv.tab.value,
                    agent=conv.agent.value,
                    title=_generate_title(conv.prompt),
                    starred=False,
                    created_at=created_at,
                    updated_at=now,
                )

                db.add(conversation)
                synced += 1

            except Exception as e:
                errors.append(f"Failed to sync conversation: {e!s}")
                skipped += 1

        db.commit()
        logger.info("Synced %s conversations, skipped %s", synced, skipped)

        return SyncResponse(synced=synced, skipped=skipped, errors=errors)

    except Exception as e:
        logger.error(f"Sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/stats")
async def get_history_stats(db: Session = Depends(get_db)) -> dict:
    """Get conversation history statistics."""
    total = db.query(ChatConversation).count()
    if total == 0:
        return {
            "total": 0,
            "by_tab": {},
            "by_agent": {},
            "starred": 0,
            "oldest": None,
            "newest": None,
        }

    by_tab_rows = (
        db.query(ChatConversation.tab, func.count())
        .group_by(ChatConversation.tab)
        .all()
    )
    by_agent_rows = (
        db.query(ChatConversation.agent, func.count())
        .group_by(ChatConversation.agent)
        .all()
    )
    starred = (
        db.query(func.count())
        .select_from(ChatConversation)
        .filter(ChatConversation.starred.is_(True))
        .scalar()
    )

    oldest = (
        db.query(ChatConversation.created_at)
        .order_by(ChatConversation.created_at.asc())
        .limit(1)
        .scalar()
    )
    newest = (
        db.query(ChatConversation.created_at)
        .order_by(ChatConversation.created_at.desc())
        .limit(1)
        .scalar()
    )

    return {
        "total": total,
        "by_tab": {tab: count for tab, count in by_tab_rows},
        "by_agent": {agent: count for agent, count in by_agent_rows},
        "starred": starred or 0,
        "oldest": oldest.isoformat() if oldest else None,
        "newest": newest.isoformat() if newest else None,
    }
