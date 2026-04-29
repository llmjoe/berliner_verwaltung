"""Unified LLM client abstraction for local (Ollama) and cloud (Anthropic, OpenAI) models.

Usage:
    client = get_llm_client("ollama")  # local
    client = get_llm_client("anthropic")  # cloud
    result = await client.complete("Classify this text", system="You are a classifier.")
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from berliner_verwaltung.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    text: str
    model: str
    usage: dict = field(default_factory=dict)

    def as_json(self) -> dict | list | None:
        try:
            cleaned = self.text.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(cleaned)
        except (json.JSONDecodeError, IndexError):
            logger.warning("Failed to parse LLM response as JSON: %s...", self.text[:100])
            return None


class LLMClient(ABC):
    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> LLMResponse: ...

    async def complete_json(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> dict | list | None:
        response = await self.complete(prompt, system, temperature, max_tokens)
        return response.as_json()


class OllamaClient(LLMClient):
    def __init__(self, model: str = "qwen2.5:7b-instruct", base_url: str | None = None) -> None:
        self.model = model
        self.base_url = base_url or settings.ollama_base_url

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        import ollama

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        client = ollama.AsyncClient(host=self.base_url)
        response = await client.chat(
            model=self.model,
            messages=messages,
            options={"temperature": temperature, "num_predict": max_tokens},
        )
        return LLMResponse(
            text=response["message"]["content"],
            model=self.model,
            usage={
                "prompt_tokens": response.get("prompt_eval_count", 0),
                "completion_tokens": response.get("eval_count", 0),
            },
        )


class AnthropicClient(LLMClient):
    def __init__(self, model: str = "claude-sonnet-4-20250514") -> None:
        self.model = model

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        kwargs: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        response = await client.messages.create(**kwargs)
        return LLMResponse(
            text=response.content[0].text,
            model=self.model,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
            },
        )


class OpenAIClient(LLMClient):
    def __init__(self, model: str = "gpt-4o") -> None:
        self.model = model

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        import openai

        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        choice = response.choices[0]
        return LLMResponse(
            text=choice.message.content or "",
            model=self.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            },
        )


def get_llm_client(provider: str = "ollama", model: str | None = None) -> LLMClient:
    if provider == "ollama":
        return OllamaClient(model=model or "qwen2.5:7b-instruct")
    elif provider == "anthropic":
        return AnthropicClient(model=model or "claude-sonnet-4-20250514")
    elif provider == "openai":
        return OpenAIClient(model=model or "gpt-4o")
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
