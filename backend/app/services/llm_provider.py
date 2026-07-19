import logging
import json
from typing import Generator, Dict, Any, Protocol
from app.core.config import settings

logger = logging.getLogger("app.services.llm_provider")

class LLMProvider(Protocol):
    """
    Interface definition for LLM stream generators.
    """
    def generate_stream(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
        num_ctx: int | None = None
    ) -> Generator[Dict[str, Any], None, None]:
        ...

class OpenAIProvider:
    """
    Concrete implementation of LLMProvider targeting OpenAI models.
    """
    def generate_stream(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
        num_ctx: int | None = None
    ) -> Generator[Dict[str, Any], None, None]:
        # Lazily import OpenAI to keep start-up light
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError("openai SDK is not installed in the virtual environment.")

        # Handle missing or mock key for development tests
        if not settings.OPENAI_API_KEY or "mock" in settings.OPENAI_API_KEY.lower():
            logger.warning("OPENAI_API_KEY is not configured or is a mock key. Streaming mock OpenAI response...")
            mock_text = (
                "Based on the uploaded document, I found that the context describes a clean SaaS application layout. "
                "The design features a flexible sidebar drawer, a contextual PDF indicator, and responsive grid layouts. "
                "The system is designed to provide high-quality grounded question answering with inline sources."
            )
            for word in mock_text.split():
                yield {"type": "token", "token": word + " "}
            # Yield cost estimation metrics
            yield {"type": "usage", "input_tokens": 120, "output_tokens": 50, "cost": 0.00003}
            return

        try:
            client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=30.0)
            model = "gpt-4o-mini"
            # gpt-4o-mini costs: input $0.15/1M, output $0.60/1M
            input_rate = 0.15 / 1_000_000
            output_rate = 0.60 / 1_000_000

            logger.info(f"Initiating streaming chat completion with OpenAI model '{model}'...")
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                stream_options={"include_usage": True}
            )

            for chunk in response:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield {"type": "token", "token": delta.content}

                if chunk.usage:
                    prompt_tokens = chunk.usage.prompt_tokens
                    completion_tokens = chunk.usage.completion_tokens
                    cost = (prompt_tokens * input_rate) + (completion_tokens * output_rate)
                    yield {
                        "type": "usage",
                        "input_tokens": prompt_tokens,
                        "output_tokens": completion_tokens,
                        "cost": cost
                    }

        except Exception as e:
            logger.error(f"OpenAI Provider streaming failure: {e}")
            raise e

class ClaudeProvider:
    """
    Concrete implementation of LLMProvider targeting Anthropic Claude models.
    Uses httpx to run stream requests to keep SDK bindings simple.
    """
    def generate_stream(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
        num_ctx: int | None = None
    ) -> Generator[Dict[str, Any], None, None]:
        # Handle missing or mock key for development tests
        if not settings.CLAUDE_API_KEY or "mock" in settings.CLAUDE_API_KEY.lower():
            logger.warning("CLAUDE_API_KEY is not configured or is a mock key. Streaming mock Claude response...")
            mock_text = (
                "Based on the uploaded document, I found that the context describes a clean SaaS application layout. "
                "The design features a flexible sidebar drawer, a contextual PDF indicator, and responsive grid layouts. "
                "The system is designed to provide high-quality grounded question answering with inline sources."
            )
            for word in mock_text.split():
                yield {"type": "token", "token": word + " "}
            # Yield cost estimation metrics
            yield {"type": "usage", "input_tokens": 150, "output_tokens": 60, "cost": 0.0001}
            return

        try:
            # Lazily import httpx
            import httpx

            # Claude 3.5 Haiku costs: input $0.25/1M, output $1.25/1M
            model = "claude-3-5-haiku-20241022"
            input_rate = 0.25 / 1_000_000
            output_rate = 1.25 / 1_000_000

            headers = {
                "x-api-key": settings.CLAUDE_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }

            body = {
                "model": model,
                "system": system_prompt,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True
            }

            logger.info(f"Initiating streaming chat completion with Claude model '{model}'...")
            with httpx.stream(
                "POST",
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=body,
                timeout=30.0
            ) as r:
                r.raise_for_status()

                prompt_tokens = 0
                completion_tokens = 0

                for line in r.iter_lines():
                    if not line:
                        continue

                    line_str = line.strip()
                    if line_str.startswith("data:"):
                        data_content = line_str[5:].strip()
                        if data_content == "[DONE]":
                            continue
                        try:
                            event = json.loads(data_content)
                            event_type = event.get("type")

                            if event_type == "message_start":
                                msg = event.get("message", {})
                                usage = msg.get("usage", {})
                                prompt_tokens = usage.get("input_tokens", 0)

                            elif event_type == "content_block_delta":
                                delta = event.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    yield {"type": "token", "token": delta.get("text", "")}

                            elif event_type == "message_delta":
                                usage = event.get("usage", {})
                                completion_tokens = usage.get("output_tokens", 0)

                        except Exception as parse_err:
                            logger.warning(f"Error parsing Claude streaming line: {parse_err}")

                cost = (prompt_tokens * input_rate) + (completion_tokens * output_rate)
                yield {
                    "type": "usage",
                    "input_tokens": prompt_tokens,
                    "output_tokens": completion_tokens,
                    "cost": cost
                }

        except Exception as e:
            logger.error(f"Claude Provider streaming failure: {e}")
            raise e

# OLD: factory returning only OpenAI or Claude providers — replaced below to add Ollama local support
# def get_llm_provider() -> LLMProvider:
#     """
#     Factory function returning active LLMProvider singleton matching config.
#     """
#     provider_name = settings.LLM_PROVIDER.lower()
#     if provider_name == "claude":
#         return ClaudeProvider()
#     return OpenAIProvider()

def get_llm_provider() -> LLMProvider:
    """
    Factory function returning active LLMProvider singleton matching config (OpenAI, Claude, or local Ollama).
    """
    provider_name = settings.LLM_PROVIDER.lower()
    if provider_name == "claude":
        return ClaudeProvider()
    elif provider_name == "ollama":
        from app.services.llm_providers.ollama_provider import OllamaProvider
        return OllamaProvider()
    return OpenAIProvider()
