"""
Multi-cloud LLM router with automatic fallback.

Supports OpenAI and Anthropic providers with graceful degradation.
Routes requests based on task type and handles failures transparently.
"""

import os
import json
from enum import Enum
from typing import Optional, Dict, Any, Union
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class LLMTask(str, Enum):
    """Types of LLM tasks for routing decisions."""

    INTENT_PARSE = "intent_parse"
    PLAN_GENERATION = "plan_generation"
    INSIGHT_NARRATION = "insight_narration"
    REPORT_SYNTHESIS = "report_synthesis"


class LLMResponse(BaseModel):
    """Standardized LLM response."""

    content: str
    provider: LLMProvider
    model: str
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None


class LLMRouter:
    """
    Multi-cloud LLM router with automatic fallback.

    Features:
    - Routes to primary provider
    - Falls back to secondary on failure
    - Supports structured JSON outputs
    - Tracks usage and errors
    """

    def __init__(
        self,
        primary_provider: LLMProvider = LLMProvider.OPENAI,
        secondary_provider: LLMProvider = LLMProvider.ANTHROPIC,
    ):
        """
        Initialize LLM router.

        Args:
            primary_provider: Primary LLM provider
            secondary_provider: Fallback LLM provider
        """
        self.primary_provider = primary_provider
        self.secondary_provider = secondary_provider
        self._init_clients()

    def _init_clients(self):
        """Initialize LLM client libraries."""
        # OpenAI client
        try:
            from openai import OpenAI

            self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.openai_available = True
        except Exception as e:
            logger.warning(f"OpenAI client initialization failed: {e}")
            self.openai_client = None
            self.openai_available = False

        # Anthropic client
        try:
            from anthropic import Anthropic

            self.anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            self.anthropic_available = True
        except Exception as e:
            logger.warning(f"Anthropic client initialization failed: {e}")
            self.anthropic_client = None
            self.anthropic_available = False

    def complete(
        self,
        task_name: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        timeout_s: int = 30,
    ) -> Union[str, Dict[str, Any]]:
        """
        Generate completion with automatic fallback.

        Args:
            task_name: Task identifier for routing
            prompt: User prompt
            system_prompt: Optional system prompt
            schema: Optional JSON schema for structured output
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            timeout_s: Request timeout in seconds

        Returns:
            String response or parsed JSON dict (if schema provided)

        Raises:
            RuntimeError: If all providers fail
        """
        # Try primary provider
        try:
            response = self._call_provider(
                self.primary_provider,
                prompt,
                system_prompt,
                schema,
                temperature,
                max_tokens,
                timeout_s,
            )
            logger.info(
                f"Task '{task_name}' completed with {self.primary_provider.value}"
            )
            return response.content if not schema else json.loads(response.content)

        except Exception as e:
            logger.warning(
                f"Primary provider {self.primary_provider.value} failed: {e}"
            )

            # Try secondary provider
            try:
                response = self._call_provider(
                    self.secondary_provider,
                    prompt,
                    system_prompt,
                    schema,
                    temperature,
                    max_tokens,
                    timeout_s,
                )
                logger.info(
                    f"Task '{task_name}' completed with fallback {self.secondary_provider.value}"
                )
                return response.content if not schema else json.loads(response.content)

            except Exception as e2:
                logger.error(
                    f"Secondary provider {self.secondary_provider.value} also failed: {e2}"
                )
                raise RuntimeError(
                    f"All LLM providers failed. Primary: {e}, Secondary: {e2}"
                )

    def _call_provider(
        self,
        provider: LLMProvider,
        prompt: str,
        system_prompt: Optional[str],
        schema: Optional[Dict[str, Any]],
        temperature: float,
        max_tokens: int,
        timeout_s: int,
    ) -> LLMResponse:
        """
        Call specific LLM provider.

        Args:
            provider: LLM provider to use
            prompt: User prompt
            system_prompt: System prompt
            schema: JSON schema for structured output
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            timeout_s: Timeout in seconds

        Returns:
            LLMResponse with completion

        Raises:
            ValueError: If provider is not available
            RuntimeError: If provider call fails
        """
        if provider == LLMProvider.OPENAI:
            return self._call_openai(
                prompt, system_prompt, schema, temperature, max_tokens, timeout_s
            )
        elif provider == LLMProvider.ANTHROPIC:
            return self._call_anthropic(
                prompt, system_prompt, schema, temperature, max_tokens, timeout_s
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def _call_openai(
        self,
        prompt: str,
        system_prompt: Optional[str],
        schema: Optional[Dict[str, Any]],
        temperature: float,
        max_tokens: int,
        timeout_s: int,
    ) -> LLMResponse:
        """Call OpenAI API."""
        if not self.openai_available or not self.openai_client:
            raise RuntimeError("OpenAI client not available")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Use structured outputs if schema provided
        kwargs = {
            "model": "gpt-4-turbo-preview",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": timeout_s,
        }

        if schema:
            kwargs["response_format"] = {"type": "json_object"}
            # Add JSON instruction to prompt
            messages[-1][
                "content"
            ] += f"\n\nRespond with valid JSON matching this schema: {json.dumps(schema)}"

        response = self.openai_client.chat.completions.create(**kwargs)

        return LLMResponse(
            content=response.choices[0].message.content,
            provider=LLMProvider.OPENAI,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            finish_reason=response.choices[0].finish_reason,
        )

    def _call_anthropic(
        self,
        prompt: str,
        system_prompt: Optional[str],
        schema: Optional[Dict[str, Any]],
        temperature: float,
        max_tokens: int,
        timeout_s: int,
    ) -> LLMResponse:
        """Call Anthropic API."""
        if not self.anthropic_available or not self.anthropic_client:
            raise RuntimeError("Anthropic client not available")

        # Add JSON instruction if schema provided
        if schema:
            prompt += f"\n\nRespond with valid JSON matching this schema: {json.dumps(schema)}"

        kwargs = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        response = self.anthropic_client.messages.create(**kwargs)

        return LLMResponse(
            content=response.content[0].text,
            provider=LLMProvider.ANTHROPIC,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            },
            finish_reason=response.stop_reason,
        )

    def complete_with_template_fallback(
        self,
        task_name: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        template_response: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Complete with template fallback if all LLMs fail.

        Args:
            task_name: Task identifier
            prompt: User prompt
            system_prompt: System prompt
            template_response: Template to use if all LLMs fail
            **kwargs: Additional arguments for complete()

        Returns:
            LLM response or template
        """
        try:
            return self.complete(task_name, prompt, system_prompt, **kwargs)
        except RuntimeError as e:
            logger.error(f"All LLM providers failed for task '{task_name}': {e}")
            if template_response:
                logger.info(f"Using template fallback for task '{task_name}'")
                return template_response
            else:
                raise

    def health_check(self) -> Dict[str, bool]:
        """
        Check health of all providers.

        Returns:
            Dictionary of provider availability
        """
        return {
            "openai": self.openai_available,
            "anthropic": self.anthropic_available,
        }
