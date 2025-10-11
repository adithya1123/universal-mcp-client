"""Azure OpenAI integration for the MCP client."""

import os
from typing import Any, AsyncIterator, Dict, List, Optional

from openai import AsyncAzureOpenAI
from dotenv import load_dotenv

load_dotenv()


class AzureOpenAIClient:
    """Azure OpenAI client for chat completions with tool calling."""

    def __init__(self):
        self.client = AsyncAzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
        self.deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create a chat completion with optional tool calling."""
        kwargs = {
            "model": self.deployment_name,
            "messages": messages,
            "temperature": temperature,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        response = await self.client.chat.completions.create(**kwargs)
        return response

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncIterator[str]:
        """Stream chat completion responses."""
        kwargs = {
            "model": self.deployment_name,
            "messages": messages,
            "temperature": temperature,
            "stream": True
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        stream = await self.client.chat.completions.create(**kwargs)

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
