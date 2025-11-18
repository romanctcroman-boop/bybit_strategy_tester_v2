"""
Базовый абстрактный класс для всех агентов

Based on agent self-improvement recommendations:
- Единый базовый класс с общими методами
- Стандартизированный интерфейс для всех агентов
- Переиспользуемая логика (retry, validation, metrics)
"""

from abc import ABC, abstractmethod
from backend.utils.time import utc_now
from typing import Any, Optional

from loguru import logger

from backend.agents.base_config import AgentCapability, AgentConfig, AgentType


class BaseAgent(ABC):
    """
    Базовый абстрактный класс для всех агентов
    
    Все агенты должны наследоваться от этого класса и реализовать:
    - send_request() - отправка запроса агенту
    - validate_response() - валидация ответа
    
    Предоставляет общую функциональность:
    - Retry logic
    - Error handling
    - Metrics recording
    - Response validation
    
    Example:
        class MyAgent(BaseAgent):
            async def send_request(self, prompt: str, context: dict) -> str:
                # Implementation
                pass
            
            def validate_response(self, response: str) -> bool:
                return len(response) > 0
    """
    
    def __init__(self, config: AgentConfig):
        """
        Инициализация агента
        
        Args:
            config: Pydantic конфигурация агента
        """
        self.config = config
        self._request_count = 0
        self._success_count = 0
        self._error_count = 0
        self._total_response_time = 0.0
        
        logger.info(
            f"🤖 Initialized {self.config.agent_type} agent "
            f"(model: {self.config.model}, timeout: {self.config.timeout}s)"
        )
    
    @property
    def agent_type(self) -> AgentType:
        """Тип агента"""
        return self.config.agent_type

    def _agent_type_value(self) -> str:
        """Возвращает строковое значение типа агента независимо от Enum/str представления."""
        at = self.agent_type
        try:
            # Если Enum
            if isinstance(at, AgentType):
                return at.value
        except Exception:
            pass
        # Уже строка или другой тип
        return str(at)
    
    @property
    def capabilities(self) -> list[AgentCapability]:
        """Возможности агента"""
        return self.config.capabilities
    
    @property
    def success_rate(self) -> float:
        """Процент успешных запросов"""
        if self._request_count == 0:
            return 0.0
        return self._success_count / self._request_count
    
    @property
    def average_response_time(self) -> float:
        """Среднее время отклика (секунды)"""
        if self._success_count == 0:
            return 0.0
        return self._total_response_time / self._success_count
    
    def has_capability(self, capability: AgentCapability) -> bool:
        """
        Проверить наличие возможности у агента
        
        Args:
            capability: Проверяемая возможность
            
        Returns:
            True если агент поддерживает эту возможность
        """
        return capability in self.capabilities
    
    @abstractmethod
    async def send_request(self, prompt: str, context: Optional[dict[str, Any]] = None) -> str:
        """
        Отправить запрос агенту
        
        Args:
            prompt: Текст запроса
            context: Дополнительный контекст (опционально)
            
        Returns:
            Ответ агента
            
        Raises:
            ValueError: Невалидный запрос
            TimeoutError: Превышен timeout
            Exception: Другие ошибки
        """
        pass
    
    @abstractmethod
    def validate_response(self, response: str) -> bool:
        """
        Валидация ответа агента
        
        Args:
            response: Ответ для валидации
            
        Returns:
            True если ответ валидный
        """
        pass
    
    async def execute(
        self,
        prompt: str,
        context: Optional[dict[str, Any]] = None,
        retry_on_failure: bool = True
    ) -> dict[str, Any]:
        """
        Выполнить запрос с retry логикой и метриками
        
        Args:
            prompt: Текст запроса
            context: Дополнительный контекст
            retry_on_failure: Повторять при ошибке
            
        Returns:
            dict с ключами:
                - success: bool
                - response: str (если success=True)
                - error: str (если success=False)
                - response_time: float (секунды)
                - attempts: int
        """
        self._request_count += 1
        start_time = utc_now()
        attempts = 0
        last_error = None
        
        max_attempts = self.config.max_retries if retry_on_failure else 1
        
        for attempt in range(1, max_attempts + 1):
            attempts = attempt
            
            try:
                logger.debug(
                    f"📤 {self.agent_type} request (attempt {attempt}/{max_attempts}): "
                    f"{prompt[:100]}..."
                )
                
                # Отправить запрос
                response = await self.send_request(prompt, context)
                
                # Валидация ответа
                if not self.validate_response(response):
                    raise ValueError("Response validation failed")
                
                # Success!
                response_time = (utc_now() - start_time).total_seconds()
                self._success_count += 1
                self._total_response_time += response_time
                
                logger.debug(
                    f"✅ {self.agent_type} response received "
                    f"({response_time:.2f}s, {len(response)} chars)"
                )
                
                return {
                    "success": True,
                    "response": response,
                    "response_time": response_time,
                    "attempts": attempts,
                    "agent_type": self._agent_type_value()
                }
            
            except Exception as e:
                last_error = f"{e.__class__.__name__}: {e}"
                logger.warning(
                    f"⚠️ {self.agent_type} request failed "
                    f"(attempt {attempt}/{max_attempts}): {e}"
                )
                
                # Retry delay
                if attempt < max_attempts:
                    import asyncio
                    await asyncio.sleep(self.config.retry_delay * attempt)
        
        # Все попытки провалились
        response_time = (utc_now() - start_time).total_seconds()
        self._error_count += 1
        
        logger.error(
            f"❌ {self.agent_type} request failed after {attempts} attempts: "
            f"{last_error}"
        )
        
        return {
            "success": False,
            "error": last_error,
            "response_time": response_time,
            "attempts": attempts,
            "agent_type": self._agent_type_value()
        }
    
    def get_stats(self) -> dict[str, Any]:
        """
        Получить статистику агента
        
        Returns:
            dict с метриками производительности
        """
        return {
            "agent_type": self._agent_type_value(),
            "model": self.config.model,
            "total_requests": self._request_count,
            "successful_requests": self._success_count,
            "failed_requests": self._error_count,
            "success_rate": self.success_rate,
            "average_response_time": self.average_response_time,
            "capabilities": [
                (c.value if isinstance(c, AgentCapability) else str(c))
                for c in self.capabilities
            ],
            "config": {
                "timeout": self.config.timeout,
                "max_retries": self.config.max_retries,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature
            }
        }
    
    def reset_stats(self):
        """Сбросить статистику"""
        self._request_count = 0
        self._success_count = 0
        self._error_count = 0
        self._total_response_time = 0.0
        logger.info(f"📊 {self.agent_type} stats reset")
    
    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} "
            f"type={self._agent_type_value()} "
            f"model={self.config.model} "
            f"success_rate={self.success_rate:.2%}>"
        )


class AgentError(Exception):
    """Базовая ошибка агента"""
    
    def __init__(
        self,
        agent_type: Optional[AgentType | str] = None,
        message: Optional[str] = None,
        details: Optional[dict] = None,
    ):
        self.agent_type = agent_type if agent_type is not None else "unknown"
        self.message = message or ""
        self.details = details or {}
        # В сообщении используем UPPERCASE имя агента, чтобы соответствовать ожиданиям тестов
        try:
            label = (
                self.agent_type.name
                if isinstance(self.agent_type, AgentType)
                else str(self.agent_type).upper()
            )
        except Exception:
            label = str(self.agent_type).upper()
        super().__init__(f"[{label}] {self.message}")


class AgentTimeoutError(AgentError):
    """Timeout ошибка"""
    pass


class AgentValidationError(AgentError):
    """Ошибка валидации"""
    pass


class AgentAPIError(AgentError):
    """Ошибка API"""
    pass


__all__ = [
    "BaseAgent",
    "AgentError",
    "AgentTimeoutError",
    "AgentValidationError",
    "AgentAPIError",
]
