"""Azure OpenAI integration for the MCP client."""

import asyncio
import logging
import os
from typing import Any, AsyncIterator, Dict, List, Optional

from openai import AsyncAzureOpenAI, RateLimitError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class AzureOpenAIClient:
    """Azure OpenAI client for chat completions with tool calling."""

    def __init__(self):
        self.client = AsyncAzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
        self.deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")

        # Rate limiting configuration
        self.max_retries = int(os.getenv("AZURE_OPENAI_MAX_RETRIES", "5"))
        self.retry_min_wait = int(os.getenv("AZURE_OPENAI_RETRY_MIN_WAIT", "1"))
        self.retry_max_wait = int(os.getenv("AZURE_OPENAI_RETRY_MAX_WAIT", "60"))
        self.api_call_delay = int(os.getenv("API_CALL_DELAY_MS", "150")) / 1000  # Convert to seconds
        self.max_tokens_default = int(os.getenv("MAX_TOKENS_PER_REQUEST", "2000"))

    async def _make_api_call_with_retry(self, **kwargs) -> Any:
        """
        Make API call with exponential backoff retry logic.
        Handles 429 rate limit errors automatically.
        """
        @retry(
            retry=retry_if_exception_type(RateLimitError),
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(
                multiplier=1,
                min=self.retry_min_wait,
                max=self.retry_max_wait
            ),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        async def _call():
            # Add jitter delay before each API call to smooth out request bursts
            await asyncio.sleep(self.api_call_delay)
            return await self.client.chat.completions.create(**kwargs)

        try:
            return await _call()
        except RateLimitError as e:
            logger.error(f"Rate limit exceeded after {self.max_retries} retries: {e}")
            raise
        except Exception as e:
            logger.error(f"API call failed: {e}")
            raise

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create a chat completion with optional tool calling and automatic retry on rate limits."""
        kwargs = {
            "model": self.deployment_name,
            "messages": messages,
            "temperature": temperature,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        # Use configured default if max_tokens not specified
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = self.max_tokens_default

        response = await self._make_api_call_with_retry(**kwargs)
        return response

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncIterator[str]:
        """Stream chat completion responses with automatic retry on rate limits."""
        kwargs = {
            "model": self.deployment_name,
            "messages": messages,
            "temperature": temperature,
            "stream": True
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        # Use configured default if max_tokens not specified
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = self.max_tokens_default

        stream = await self._make_api_call_with_retry(**kwargs)

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def extract_tool_calls(self, response: Any) -> List[Dict[str, Any]]:
        """Extract tool calls from response."""
        tool_calls = []

        if response.choices[0].message.tool_calls:
            for tool_call in response.choices[0].message.tool_calls:
                tool_calls.append({
                    "id": tool_call.id,
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments
                })

        return tool_calls
