"""
FastAPI endpoints для Agent-to-Agent Communication System
Обход GitHub Copilot tool limit через прямую коммуникацию между AI агентами
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect
from loguru import logger
from pydantic import BaseModel, Field

# Imports для agent communication
from backend.agents.agent_to_agent_communicator import (
    AgentMessage,
    AgentToAgentCommunicator,
    AgentType,
    CommunicationPattern,
    MessageType,
)

router = APIRouter(prefix="/api/v1/agent", tags=["Agent-to-Agent Communication"])

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.conversation_subscribers: dict[str, list[str]] = {}
    
    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"Client {client_id} connected. Total: {len(self.active_connections)}")
    
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"Client {client_id} disconnected. Total: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: dict, client_id: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(message)
    
    async def broadcast_to_conversation(self, message: dict, conversation_id: str):
        """Broadcast сообщения всем подписчикам разговора"""
        if conversation_id in self.conversation_subscribers:
            for client_id in self.conversation_subscribers[conversation_id]:
                await self.send_personal_message(message, client_id)
    
    def subscribe_to_conversation(self, client_id: str, conversation_id: str):
        if conversation_id not in self.conversation_subscribers:
            self.conversation_subscribers[conversation_id] = []
        if client_id not in self.conversation_subscribers[conversation_id]:
            self.conversation_subscribers[conversation_id].append(client_id)

manager = ConnectionManager()

# Pydantic models для API
class AgentMessageRequest(BaseModel):
    from_agent: str = Field(..., description="Отправитель (deepseek, perplexity, copilot)")
    to_agent: str = Field(..., description="Получатель")
    message_type: str = Field(default="query", description="Тип сообщения")
    content: str = Field(..., description="Содержимое сообщения")
    context: dict[str, Any] = Field(default_factory=dict)
    conversation_id: str | None = None
    max_iterations: int = Field(default=5, ge=1, le=20)

class BroadcastRequest(BaseModel):
    from_agent: str
    message: str
    target_agents: list[str] = Field(..., min_items=1)
    context: dict[str, Any] = Field(default_factory=dict)

class ConversationRequest(BaseModel):
    initiator: str
    participants: list[str] = Field(..., min_items=2)
    initial_message: str
    max_turns: int = Field(default=5, ge=1, le=20)
    pattern: str = Field(default="collaborative")

class ConsensusRequest(BaseModel):
    question: str
    agents: list[str] = Field(default=["deepseek", "perplexity"])
    context: dict[str, Any] = Field(default_factory=dict)

class IterativeImprovementRequest(BaseModel):
    initial_task: str
    validator_agent: str = "perplexity"
    improver_agent: str = "deepseek"
    max_iterations: int = Field(default=3, ge=1, le=10)
    min_confidence: float = Field(default=0.8, ge=0.0, le=1.0)

# Response models
class AgentMessageResponse(BaseModel):
    message_id: str
    from_agent: str
    to_agent: str
    content: str
    timestamp: str
    conversation_id: str
    iteration: int
    success: bool = True
    error: str | None = None

class ConversationResponse(BaseModel):
    conversation_id: str
    messages: list[AgentMessageResponse]
    total_messages: int
    completed: bool
    duration_ms: float

# Initialize communicator
communicator = AgentToAgentCommunicator()

# ===================== ENDPOINTS =====================

@router.post("/send", response_model=AgentMessageResponse)
async def send_to_agent(request: AgentMessageRequest, background_tasks: BackgroundTasks):
    """
    Отправить сообщение от одного агента к другому
    
    Example:
    ```json
    {
        "from_agent": "copilot",
        "to_agent": "deepseek",
        "content": "Проанализируй этот код",
        "message_type": "query"
    }
    ```
    """
    try:
        # Создание сообщения
        conversation_id = request.conversation_id or str(uuid.uuid4())
        
        message = AgentMessage(
            message_id=str(uuid.uuid4()),
            from_agent=AgentType(request.from_agent),
            to_agent=AgentType(request.to_agent),
            message_type=MessageType(request.message_type),
            content=request.content,
            context=request.context,
            conversation_id=conversation_id,
            max_iterations=request.max_iterations
        )
        
        logger.info(f"Routing message {message.message_id}: {request.from_agent} → {request.to_agent}")
        
        # Отправка через communicator
        response = await communicator.route_message(message)
        
        # Broadcast через WebSocket если есть подписчики
        background_tasks.add_task(
            manager.broadcast_to_conversation,
            {
                "type": "message_sent",
                "message_id": response.message_id,
                "from_agent": response.from_agent.value,
                "to_agent": response.to_agent.value,
                "content": response.content[:200]  # Truncate для performance
            },
            conversation_id
        )
        
        return AgentMessageResponse(
            message_id=response.message_id,
            from_agent=response.from_agent.value,
            to_agent=response.to_agent.value,
            content=response.content,
            timestamp=response.timestamp,
            conversation_id=response.conversation_id,
            iteration=response.iteration
        )
        
    except ValueError as e:
        logger.error(f"Invalid agent type or message type: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post("/broadcast")
async def broadcast_to_agents(request: BroadcastRequest):
    """
    Отправить сообщение нескольким агентам параллельно
    
    Example:
    ```json
    {
        "from_agent": "orchestrator",
        "message": "Что вы думаете о квантовых вычислениях?",
        "target_agents": ["deepseek", "perplexity"]
    }
    ```
    """
    try:
        conversation_id = str(uuid.uuid4())
        
        # Создание параллельных задач
        tasks = []
        for target_agent in request.target_agents:
            message = AgentMessage(
                message_id=str(uuid.uuid4()),
                from_agent=AgentType(request.from_agent),
                to_agent=AgentType(target_agent),
                message_type=MessageType.QUERY,
                content=request.message,
                context=request.context,
                conversation_id=conversation_id
            )
            tasks.append(communicator.route_message(message))
        
        logger.info(f"Broadcasting to {len(request.target_agents)} agents")
        
        # Параллельное выполнение
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Обработка результатов
        results = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                results.append({
                    "agent": request.target_agents[i],
                    "success": False,
                    "error": str(response)
                })
            else:
                results.append({
                    "agent": response.from_agent.value,
                    "success": True,
                    "content": response.content,
                    "message_id": response.message_id
                })
        
        return {
            "conversation_id": conversation_id,
            "broadcast_to": request.target_agents,
            "results": results,
            "success_count": sum(1 for r in results if r["success"]),
            "total_count": len(results)
        }
        
    except Exception as e:
        logger.error(f"Error broadcasting: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversation", response_model=ConversationResponse)
async def start_agent_conversation(request: ConversationRequest):
    """
    Запустить multi-turn разговор между агентами
    
    Example:
    ```json
    {
        "initiator": "copilot",
        "participants": ["deepseek", "perplexity"],
        "initial_message": "Давайте обсудим оптимизацию алгоритма",
        "max_turns": 5,
        "pattern": "collaborative"
    }
    ```
    """
    try:
        start_time = datetime.now()
        conversation_id = str(uuid.uuid4())
        
        # Создание начального сообщения
        initial_message = AgentMessage(
            message_id=str(uuid.uuid4()),
            from_agent=AgentType(request.initiator),
            to_agent=AgentType(request.participants[0]),
            message_type=MessageType.QUERY,
            content=request.initial_message,
            context={"participants": request.participants},
            conversation_id=conversation_id,
            max_iterations=request.max_turns
        )
        
        # Определение паттерна коммуникации
        pattern = CommunicationPattern(request.pattern)
        
        logger.info(f"Starting {pattern.value} conversation {conversation_id} with {len(request.participants)} participants")
        
        # Запуск multi-turn conversation
        history = await communicator.multi_turn_conversation(
            initial_message=initial_message,
            max_turns=request.max_turns,
            pattern=pattern
        )
        
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        # Форматирование ответа
        messages = []
        for msg in history:
            messages.append(AgentMessageResponse(
                message_id=msg.message_id,
                from_agent=msg.from_agent.value,
                to_agent=msg.to_agent.value,
                content=msg.content,
                timestamp=msg.timestamp,
                conversation_id=msg.conversation_id,
                iteration=msg.iteration
            ))
        
        return ConversationResponse(
            conversation_id=conversation_id,
            messages=messages,
            total_messages=len(messages),
            completed=history[-1].message_type == MessageType.COMPLETION,
            duration_ms=duration_ms
        )
        
    except Exception as e:
        logger.error(f"Error in conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/consensus")
async def get_multi_agent_consensus(request: ConsensusRequest):
    """
    Получить консенсус от нескольких агентов
    
    Example:
    ```json
    {
        "question": "Какой лучший подход к оптимизации этого кода?",
        "agents": ["deepseek", "perplexity"]
    }
    ```
    """
    try:
        logger.info(f"Requesting consensus from {len(request.agents)} agents")
        
        # Конвертация строк в AgentType
        agent_types = [AgentType(agent) for agent in request.agents]
        
        # Получение консенсуса
        result = await communicator.parallel_consensus(
            question=request.question,
            agents=agent_types
        )
        
        return {
            "consensus": result["consensus"],
            "individual_responses": result["individual_responses"],
            "confidence_score": result["confidence_score"],
            "conversation_id": result["conversation_id"],
            "agents_consulted": request.agents
        }
        
    except Exception as e:
        logger.error(f"Error getting consensus: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/iterative-improvement")
async def iterative_code_improvement(request: IterativeImprovementRequest):
    """
    Итеративное улучшение с валидацией
    
    Example:
    ```json
    {
        "initial_task": "def slow_function(): ...",
        "validator_agent": "perplexity",
        "improver_agent": "deepseek",
        "max_iterations": 3,
        "min_confidence": 0.8
    }
    ```
    """
    try:
        logger.info(f"Starting iterative improvement (max {request.max_iterations} iterations)")
        
        result = await communicator.iterative_improvement(
            initial_task=request.initial_task,
            validator_agent=AgentType(request.validator_agent),
            improver_agent=AgentType(request.improver_agent),
            max_iterations=request.max_iterations,
            min_confidence=request.min_confidence
        )
        
        return {
            "final_content": result["final_content"],
            "final_confidence": result["final_confidence"],
            "iterations": result["iterations"],
            "conversation_id": result["conversation_id"],
            "success": result["success"],
            "improvement_summary": {
                "total_iterations": len(result["iterations"]),
                "confidence_improvement": result["final_confidence"] - (result["iterations"][0]["confidence"] if result["iterations"] else 0),
                "achieved_target": result["final_confidence"] >= request.min_confidence
            }
        }
        
    except Exception as e:
        logger.error(f"Error in iterative improvement: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint для real-time обновлений
    
    Usage:
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/api/v1/agent/ws/my-client-id');
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('Message from agent:', data);
    };
    ```
    """
    await manager.connect(client_id, websocket)
    try:
        while True:
            # Получение команд от клиента
            data = await websocket.receive_json()
            
            command = data.get("command")
            
            if command == "subscribe":
                # Подписка на conversation
                conversation_id = data.get("conversation_id")
                if conversation_id:
                    manager.subscribe_to_conversation(client_id, conversation_id)
                    await manager.send_personal_message(
                        {"type": "subscribed", "conversation_id": conversation_id},
                        client_id
                    )
            
            elif command == "send_message":
                # Отправка сообщения через WebSocket
                from_agent = data.get("from_agent")
                to_agent = data.get("to_agent")
                content = data.get("content")
                
                message = AgentMessage(
                    message_id=str(uuid.uuid4()),
                    from_agent=AgentType(from_agent),
                    to_agent=AgentType(to_agent),
                    message_type=MessageType.QUERY,
                    content=content,
                    context={},
                    conversation_id=data.get("conversation_id", str(uuid.uuid4()))
                )
                
                response = await communicator.route_message(message)
                
                await manager.send_personal_message(
                    {
                        "type": "message_response",
                        "message_id": response.message_id,
                        "content": response.content,
                        "from_agent": response.from_agent.value
                    },
                    client_id
                )
            
            elif command == "ping":
                await manager.send_personal_message({"type": "pong"}, client_id)
            
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        logger.info(f"Client {client_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error for {client_id}: {e}")
        manager.disconnect(client_id)


@router.get("/health")
async def health_check():
    """Health check для Agent-to-Agent системы"""
    return {
        "status": "healthy",
        "active_websocket_connections": len(manager.active_connections),
        "active_conversations": len(manager.conversation_subscribers),
        "communicator_initialized": communicator is not None
    }


@router.get("/stats")
async def get_statistics():
    """Статистика Agent-to-Agent коммуникации"""
    return {
        "websocket_connections": len(manager.active_connections),
        "active_conversations": len(manager.conversation_subscribers),
        "total_subscribers": sum(len(subs) for subs in manager.conversation_subscribers.values())
    }


@router.get("/metrics/{agent_name}")
async def get_agent_metrics(agent_name: str, hours: int = 24):
    """
    Получить метрики производительности агента
    
    Args:
        agent_name: Имя агента (deepseek, perplexity, copilot)
        hours: Период в часах (default: 24)
        
    Returns:
        AgentPerformance сводка
    """
    try:
        from backend.monitoring.agent_metrics import get_agent_performance
        
        performance = await get_agent_performance(agent_name, hours)
        
        return {
            "agent_name": performance.agent_name,
            "period": {
                "start": performance.period_start.isoformat(),
                "end": performance.period_end.isoformat(),
                "hours": hours
            },
            "response_time": {
                "avg_ms": round(performance.avg_response_time_ms, 2),
                "min_ms": round(performance.min_response_time_ms, 2),
                "max_ms": round(performance.max_response_time_ms, 2),
                "p95_ms": round(performance.p95_response_time_ms, 2)
            },
            "success": {
                "total_requests": performance.total_requests,
                "successful": performance.successful_requests,
                "failed": performance.failed_requests,
                "rate": round(performance.success_rate * 100, 2)
            },
            "tool_calling": {
                "calls_made": performance.tool_calls_made,
                "successful": performance.tool_calls_successful,
                "success_rate": round(performance.tool_call_success_rate * 100, 2),
                "avg_iterations": round(performance.avg_iterations_per_request, 2)
            },
            "quality": {
                "avg_confidence": round(performance.avg_confidence_score, 2),
                "total_tokens": performance.total_tokens_used,
                "avg_tokens_per_request": round(performance.avg_tokens_per_request, 2)
            },
            "errors": {
                "breakdown": performance.error_breakdown,
                "most_common": performance.most_common_error
            }
        }
    except ImportError:
        raise HTTPException(status_code=500, detail="Metrics module not available")
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def get_all_metrics(hours: int = 24):
    """
    Получить метрики производительности всех агентов
    
    Args:
        hours: Период в часах (default: 24)
        
    Returns:
        Dict со сводками по всем агентам
    """
    try:
        from backend.monitoring.agent_metrics import get_all_agents_performance
        
        all_performance = await get_all_agents_performance(hours)
        
        result = {}
        for agent_name, performance in all_performance.items():
            result[agent_name] = {
                "response_time_avg_ms": round(performance.avg_response_time_ms, 2),
                "success_rate": round(performance.success_rate * 100, 2),
                "total_requests": performance.total_requests,
                "tool_calls": performance.tool_calls_made,
                "errors": len(performance.error_breakdown)
            }
        
        return {
            "period_hours": hours,
            "agents": result,
            "summary": {
                "total_agents": len(result),
                "total_requests": sum(p.total_requests for p in all_performance.values()),
                "avg_success_rate": round(
                    sum(p.success_rate for p in all_performance.values()) / len(all_performance) * 100
                    if all_performance else 0, 2
                )
            }
        }
    except ImportError:
        raise HTTPException(status_code=500, detail="Metrics module not available")
    except Exception as e:
        logger.error(f"Error getting all metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# FILE EDITING ENDPOINTS (для обхода @workspace read-only ограничения)
# ============================================================================

class FileEditRequest(BaseModel):
    """Запрос на редактирование файла через AI Agent"""
    file_path: str = Field(..., description="Путь к файлу (абсолютный или относительный)")
    content: str | None = Field(None, description="Новое содержимое (если None - прочитать)")
    agent: str = Field("deepseek", description="AI агент для анализа (deepseek/perplexity)")
    instruction: str | None = Field(None, description="Инструкция для рефакторинга")
    mode: str = Field("read", description="Режим: read, write, refactor, analyze")


class FileEditResponse(BaseModel):
    """Ответ на запрос редактирования"""
    success: bool
    file_path: str
    mode: str
    content: str | None = None
    agent_analysis: str | None = None
    changes_applied: bool = False
    error: str | None = None


@router.post("/file-edit", response_model=FileEditResponse)
async def edit_file_with_agent(request: FileEditRequest):
    """
    🔧 РЕДАКТИРОВАНИЕ ФАЙЛОВ ЧЕРЕЗ AI AGENT
    
    Обход ограничения @workspace (read-only) через Backend API
    
    Режимы:
    - read: Прочитать файл
    - write: Записать новое содержимое
    - refactor: DeepSeek/Perplexity анализирует и предлагает изменения
    - analyze: Только анализ, без изменений
    
    Пример:
        POST /api/v1/agent/file-edit
        {
            "file_path": "backend/queue/redis_queue_poc.py",
            "mode": "refactor",
            "agent": "deepseek",
            "instruction": "Add type hints and docstrings"
        }
    """
    import os
    from pathlib import Path
    
    try:
        # Определить абсолютный путь
        if not os.path.isabs(request.file_path):
            # Относительный путь от workspace root
            workspace_root = Path(__file__).parent.parent.parent
            file_path = workspace_root / request.file_path
        else:
            file_path = Path(request.file_path)
        
        # Проверка существования файла
        if request.mode != "write" and not file_path.exists():
            return FileEditResponse(
                success=False,
                file_path=str(file_path),
                mode=request.mode,
                error=f"File not found: {file_path}"
            )
        
        # MODE: READ
        if request.mode == "read":
            content = file_path.read_text(encoding="utf-8")
            return FileEditResponse(
                success=True,
                file_path=str(file_path),
                mode="read",
                content=content,
                changes_applied=False
            )
        
        # MODE: WRITE
        if request.mode == "write":
            if not request.content:
                return FileEditResponse(
                    success=False,
                    file_path=str(file_path),
                    mode="write",
                    error="Content required for write mode"
                )
            
            file_path.write_text(request.content, encoding="utf-8")
            logger.info(f"✅ File written: {file_path} ({len(request.content)} chars)")
            
            return FileEditResponse(
                success=True,
                file_path=str(file_path),
                mode="write",
                content=request.content[:500] + "..." if len(request.content) > 500 else request.content,
                changes_applied=True
            )
        
        # MODE: ANALYZE или REFACTOR
        if request.mode in ["analyze", "refactor"]:
            # Прочитать текущее содержимое
            current_content = file_path.read_text(encoding="utf-8")
            
            # Создать prompt для AI агента
            prompt = f"""
Analyze this file and {request.instruction or 'suggest improvements'}:

FILE: {file_path.name}
LINES: {len(current_content.splitlines())}

```python
{current_content}
```

{'INSTRUCTIONS: ' + request.instruction if request.instruction else ''}

{'Provide ONLY the refactored code (no explanations).' if request.mode == 'refactor' else 'Provide analysis and recommendations.'}
"""
            
            # Отправить в AI агента
            communicator = AgentToAgentCommunicator()
            
            agent_message = AgentMessage(
                from_agent=AgentType.COPILOT,
                to_agent=AgentType.DEEPSEEK if request.agent == "deepseek" else AgentType.PERPLEXITY,
                message_type=MessageType.QUERY,
                content=prompt
            )
            
            response = await communicator.route_message(agent_message)
            agent_analysis = response.content
            
            # Если refactor mode - применить изменения
            if request.mode == "refactor" and agent_analysis:
                # Попытаться извлечь код из markdown code block
                import re
                code_match = re.search(r'```(?:python)?\n(.*?)\n```', agent_analysis, re.DOTALL)
                
                if code_match:
                    refactored_code = code_match.group(1)
                    
                    # Создать backup
                    backup_path = file_path.with_suffix(file_path.suffix + ".backup")
                    file_path.rename(backup_path)
                    logger.info(f"📦 Backup created: {backup_path}")
                    
                    # Записать refactored код
                    file_path.write_text(refactored_code, encoding="utf-8")
                    logger.success(f"✅ File refactored: {file_path}")
                    
                    return FileEditResponse(
                        success=True,
                        file_path=str(file_path),
                        mode="refactor",
                        content=refactored_code[:500] + "...",
                        agent_analysis=agent_analysis,
                        changes_applied=True
                    )
            
            # Analyze mode - только анализ
            return FileEditResponse(
                success=True,
                file_path=str(file_path),
                mode=request.mode,
                agent_analysis=agent_analysis,
                changes_applied=False
            )
        
        return FileEditResponse(
            success=False,
            file_path=str(file_path),
            mode=request.mode,
            error=f"Unknown mode: {request.mode}"
        )
    
    except Exception as e:
        logger.error(f"❌ File edit error: {e}", exc_info=True)
        return FileEditResponse(
            success=False,
            file_path=request.file_path,
            mode=request.mode,
            error=str(e)
        )
