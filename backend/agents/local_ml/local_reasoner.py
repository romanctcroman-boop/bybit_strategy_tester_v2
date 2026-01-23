"""
Local Reasoning Engine

Provides local LLM inference for autonomous operation without API dependencies.
Supports:
- llama.cpp integration for efficient CPU/GPU inference
- Hugging Face transformers with quantization
- Chain-of-thought reasoning
- Multiple model sizes (1B to 70B parameters)

Recommended models:
- DeepSeek-R1-Distill-Qwen-7B (best for reasoning)
- Mistral-7B-Instruct (general purpose)
- Phi-3-mini (fast, small)
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from loguru import logger


class ModelSize(Enum):
    """Available model sizes"""

    TINY = "tiny"  # 1-3B parameters
    SMALL = "small"  # 7B parameters
    MEDIUM = "medium"  # 13B parameters
    LARGE = "large"  # 70B parameters


class InferenceBackend(Enum):
    """Supported inference backends"""

    LLAMA_CPP = "llama_cpp"
    TRANSFORMERS = "transformers"
    VLLM = "vllm"
    OLLAMA = "ollama"


@dataclass
class ReasoningResult:
    """Result from local reasoning"""

    content: str
    thinking: Optional[str] = None  # Chain-of-thought trace
    confidence: float = 0.0
    tokens_used: int = 0
    latency_ms: float = 0.0
    model_name: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "thinking": self.thinking,
            "confidence": self.confidence,
            "tokens_used": self.tokens_used,
            "latency_ms": self.latency_ms,
            "model_name": self.model_name,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ModelConfig:
    """Configuration for local model"""

    model_path: str
    model_size: ModelSize = ModelSize.SMALL
    backend: InferenceBackend = InferenceBackend.LLAMA_CPP
    context_length: int = 4096
    max_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 0.95
    threads: int = 4
    gpu_layers: int = 0  # Number of layers to offload to GPU
    quantization: Optional[str] = "Q4_K_M"  # For GGUF models


class LocalReasonerEngine:
    """
    Local reasoning engine for autonomous operation

    Provides CPU/GPU inference using local LLM models.
    Optimized for reasoning tasks with chain-of-thought support.

    Example:
        engine = LocalReasonerEngine(
            model_path="./models/deepseek-r1-distill-qwen-7b-Q4_K_M.gguf"
        )
        await engine.initialize()

        result = await engine.reason(
            "Analyze this trading strategy and suggest improvements",
            context={"strategy": strategy_config}
        )

        print(f"Response: {result.content}")
        print(f"Thinking: {result.thinking}")
    """

    # Default system prompts for different tasks
    SYSTEM_PROMPTS = {
        "reasoning": """You are an expert AI assistant specialized in logical reasoning and analysis.
When solving problems:
1. Break down the problem into steps
2. Consider multiple perspectives
3. Show your reasoning process
4. Provide a clear conclusion

Think step by step before answering.""",
        "coding": """You are an expert programmer and code analyst.
When writing or analyzing code:
1. Consider edge cases
2. Follow best practices
3. Explain your approach
4. Provide working code

Format code blocks properly with language specification.""",
        "trading": """You are an expert trading strategy analyst.
When analyzing trading:
1. Consider risk management
2. Evaluate market conditions
3. Check backtesting results
4. Provide actionable recommendations

Be specific about entry/exit conditions.""",
    }

    def __init__(
        self,
        model_path: Optional[str] = None,
        config: Optional[ModelConfig] = None,
    ):
        """
        Initialize local reasoner

        Args:
            model_path: Path to model file (GGUF for llama.cpp)
            config: Optional ModelConfig
        """
        self.config = config or ModelConfig(
            model_path=model_path or "",
            model_size=ModelSize.SMALL,
        )

        self._model = None
        self._tokenizer = None
        self._initialized = False

        # Statistics
        self.stats = {
            "total_inferences": 0,
            "total_tokens": 0,
            "avg_latency_ms": 0.0,
            "errors": 0,
        }

        logger.info(
            f"🧠 LocalReasonerEngine created (backend={self.config.backend.value})"
        )

    async def initialize(self) -> bool:
        """
        Initialize the model

        Returns:
            True if successful, False otherwise
        """
        if self._initialized:
            return True

        try:
            if self.config.backend == InferenceBackend.LLAMA_CPP:
                await self._init_llama_cpp()
            elif self.config.backend == InferenceBackend.TRANSFORMERS:
                await self._init_transformers()
            elif self.config.backend == InferenceBackend.OLLAMA:
                await self._init_ollama()
            else:
                logger.warning(f"Backend {self.config.backend} not fully implemented")
                return False

            self._initialized = True
            logger.info(f"✅ Local model initialized: {self.config.model_path}")
            return True

        except ImportError as e:
            logger.warning(f"Missing dependency for local inference: {e}")
            logger.info(
                "Install with: pip install llama-cpp-python or pip install transformers"
            )
            return False
        except Exception as e:
            logger.error(f"Failed to initialize local model: {e}")
            self.stats["errors"] += 1
            return False

    async def _init_llama_cpp(self) -> None:
        """Initialize llama.cpp backend"""
        try:
            from llama_cpp import Llama

            def load_model():
                return Llama(
                    model_path=self.config.model_path,
                    n_ctx=self.config.context_length,
                    n_threads=self.config.threads,
                    n_gpu_layers=self.config.gpu_layers,
                    verbose=False,
                )

            self._model = await asyncio.to_thread(load_model)

        except ImportError:
            raise ImportError(
                "llama-cpp-python not installed. Run: pip install llama-cpp-python"
            )

    async def _init_transformers(self) -> None:
        """Initialize Hugging Face transformers backend"""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch

            def load_model():
                tokenizer = AutoTokenizer.from_pretrained(
                    self.config.model_path,
                    trust_remote_code=True,
                )

                # Determine device
                device = "cuda" if torch.cuda.is_available() else "cpu"

                # Load with quantization if available
                model = AutoModelForCausalLM.from_pretrained(
                    self.config.model_path,
                    torch_dtype=torch.float16 if device == "cuda" else torch.float32,
                    device_map="auto" if device == "cuda" else None,
                    trust_remote_code=True,
                )

                return model, tokenizer

            self._model, self._tokenizer = await asyncio.to_thread(load_model)

        except ImportError:
            raise ImportError(
                "transformers not installed. Run: pip install transformers torch"
            )

    async def _init_ollama(self) -> None:
        """Initialize Ollama backend (uses HTTP API)"""
        # Ollama runs as a service, just verify it's available
        import httpx

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:11434/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    logger.info(f"Ollama available with {len(models)} models")
                else:
                    raise ConnectionError("Ollama not responding")
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            raise

    async def reason(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        task_type: str = "reasoning",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> ReasoningResult:
        """
        Perform reasoning with local model

        Args:
            prompt: The prompt/question
            context: Optional context dict
            task_type: Type of task (reasoning, coding, trading)
            max_tokens: Override max tokens
            temperature: Override temperature

        Returns:
            ReasoningResult with content and thinking trace
        """
        if not self._initialized:
            success = await self.initialize()
            if not success:
                return ReasoningResult(
                    content="Error: Model not initialized",
                    confidence=0.0,
                    model_name="none",
                )

        start_time = time.time()

        # Build full prompt with system message
        system_prompt = self.SYSTEM_PROMPTS.get(
            task_type, self.SYSTEM_PROMPTS["reasoning"]
        )

        if context:
            context_str = json.dumps(context, indent=2)
            full_prompt = (
                f"{system_prompt}\n\nContext:\n{context_str}\n\nQuestion: {prompt}"
            )
        else:
            full_prompt = f"{system_prompt}\n\nQuestion: {prompt}"

        # Generate response based on backend
        try:
            if self.config.backend == InferenceBackend.LLAMA_CPP:
                content, thinking, tokens = await self._generate_llama_cpp(
                    full_prompt,
                    max_tokens or self.config.max_tokens,
                    temperature or self.config.temperature,
                )
            elif self.config.backend == InferenceBackend.TRANSFORMERS:
                content, thinking, tokens = await self._generate_transformers(
                    full_prompt,
                    max_tokens or self.config.max_tokens,
                    temperature or self.config.temperature,
                )
            elif self.config.backend == InferenceBackend.OLLAMA:
                content, thinking, tokens = await self._generate_ollama(
                    full_prompt,
                    max_tokens or self.config.max_tokens,
                    temperature or self.config.temperature,
                )
            else:
                content = "Backend not implemented"
                thinking = None
                tokens = 0

        except Exception as e:
            logger.error(f"Generation failed: {e}")
            self.stats["errors"] += 1
            return ReasoningResult(
                content=f"Error: {e}",
                confidence=0.0,
                model_name=self.config.model_path,
            )

        latency = (time.time() - start_time) * 1000

        # Calculate confidence based on response quality
        confidence = self._estimate_confidence(content, thinking)

        # Update stats
        self.stats["total_inferences"] += 1
        self.stats["total_tokens"] += tokens
        prev_avg = self.stats["avg_latency_ms"]
        self.stats["avg_latency_ms"] = (
            prev_avg * (self.stats["total_inferences"] - 1) + latency
        ) / self.stats["total_inferences"]

        result = ReasoningResult(
            content=content,
            thinking=thinking,
            confidence=confidence,
            tokens_used=tokens,
            latency_ms=latency,
            model_name=Path(self.config.model_path).name
            if self.config.model_path
            else "unknown",
        )

        logger.debug(
            f"🧠 Local reasoning: {tokens} tokens, {latency:.0f}ms, "
            f"confidence={confidence:.2f}"
        )

        return result

    async def _generate_llama_cpp(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> Tuple[str, Optional[str], int]:
        """Generate with llama.cpp"""

        def generate():
            response = self._model(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=self.config.top_p,
                echo=False,
            )
            return response

        response = await asyncio.to_thread(generate)

        content = response["choices"][0]["text"].strip()
        tokens = response.get("usage", {}).get("total_tokens", 0)

        # Extract thinking if present (for models that support it)
        thinking = None
        if "<think>" in content and "</think>" in content:
            think_start = content.find("<think>") + 7
            think_end = content.find("</think>")
            thinking = content[think_start:think_end].strip()
            content = content[think_end + 8 :].strip()

        return content, thinking, tokens

    async def _generate_transformers(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> Tuple[str, Optional[str], int]:
        """Generate with transformers"""
        import torch

        def generate():
            inputs = self._tokenizer(prompt, return_tensors="pt")

            if torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self._model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    temperature=temperature,
                    top_p=self.config.top_p,
                    do_sample=True,
                )

            response = self._tokenizer.decode(outputs[0], skip_special_tokens=True)
            return response, len(outputs[0])

        content, tokens = await asyncio.to_thread(generate)

        # Remove the prompt from the response
        if content.startswith(prompt):
            content = content[len(prompt) :].strip()

        return content, None, tokens

    async def _generate_ollama(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> Tuple[str, Optional[str], int]:
        """Generate with Ollama API"""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": Path(self.config.model_path).stem,
                    "prompt": prompt,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": temperature,
                    },
                    "stream": False,
                },
                timeout=120.0,
            )

            if response.status_code == 200:
                data = response.json()
                content = data.get("response", "")
                tokens = data.get("eval_count", 0)
                return content, None, tokens
            else:
                raise Exception(f"Ollama error: {response.status_code}")

    def _estimate_confidence(self, content: str, thinking: Optional[str]) -> float:
        """Estimate confidence in the response"""
        confidence = 0.5  # Base confidence

        if not content or len(content) < 20:
            return 0.1

        # Boost if thinking trace present
        if thinking:
            confidence += 0.2

        # Check for uncertainty markers
        uncertainty_words = [
            "maybe",
            "possibly",
            "might",
            "could",
            "uncertain",
            "not sure",
        ]
        for word in uncertainty_words:
            if word in content.lower():
                confidence -= 0.05

        # Check for confidence markers
        confidence_words = [
            "definitely",
            "clearly",
            "certainly",
            "confident",
            "obvious",
        ]
        for word in confidence_words:
            if word in content.lower():
                confidence += 0.05

        # Boost for structured response
        if any(marker in content for marker in ["1.", "2.", "•", "-"]):
            confidence += 0.1

        return max(0.0, min(1.0, confidence))

    async def chain_of_thought(
        self,
        problem: str,
        steps: int = 5,
    ) -> ReasoningResult:
        """
        Execute step-by-step chain-of-thought reasoning

        Args:
            problem: The problem to solve
            steps: Maximum reasoning steps
        """
        cot_prompt = f"""
Solve this problem step by step. Show your thinking at each step.

Problem: {problem}

Think through this carefully:
Step 1:"""

        result = await self.reason(
            cot_prompt,
            task_type="reasoning",
            max_tokens=self.config.max_tokens * 2,  # Allow more tokens for CoT
        )

        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics"""
        return {
            **self.stats,
            "initialized": self._initialized,
            "model": self.config.model_path,
            "backend": self.config.backend.value,
        }


__all__ = [
    "LocalReasonerEngine",
    "ReasoningResult",
    "ModelConfig",
    "ModelSize",
    "InferenceBackend",
]
