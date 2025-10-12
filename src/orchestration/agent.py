"""LangGraph functional API agent orchestration with State management."""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from langgraph.func import entrypoint, task
from langgraph.checkpoint.base import BaseCheckpointSaver

from src.llm.azure_openai import AzureOpenAIClient
from src.mcp.client import MCPClient
from src.storage.database import DatabaseManager
from .state import ChatState

logger = logging.getLogger(__name__)


def validate_and_clean_conversation_history(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Validate and clean conversation history to ensure proper OpenAI API format.

    Rules enforced:
    1. Tool messages must follow assistant messages with tool_calls
    2. Remove orphaned tool messages (no preceding assistant with tool_calls)
    3. Remove incomplete assistant messages with tool_calls but no tool responses

    Args:
        history: Conversation history to validate and clean

    Returns:
        Cleaned conversation history
    """
    if not history:
        return history

    cleaned = []
    i = 0

    while i < len(history):
        msg = history[i]
        role = msg.get("role")

        if role == "system" or role == "user":
            # System and user messages are always valid
            cleaned.append(msg)
            i += 1

        elif role == "assistant":
            # Check if this assistant message has tool_calls
            if msg.get("tool_calls"):
                # Look ahead to see if there are corresponding tool responses
                tool_call_ids = {tc["id"] for tc in msg["tool_calls"]}
                j = i + 1
                tool_responses = []

                # Collect all immediately following tool messages
                while j < len(history) and history[j].get("role") == "tool":
                    tool_msg = history[j]
                    if tool_msg.get("tool_call_id") in tool_call_ids:
                        tool_responses.append(tool_msg)
                        tool_call_ids.discard(tool_msg["tool_call_id"])
                    j += 1

                # Only include if we have ALL tool responses
                if not tool_call_ids:  # All tool calls have responses
                    cleaned.append(msg)
                    cleaned.extend(tool_responses)
                    i = j
                else:
                    # Incomplete tool interaction - skip
                    logger.warning(f"Removing incomplete tool interaction: missing responses for {tool_call_ids}")
                    i = j
            else:
                # Regular assistant message without tool calls
                cleaned.append(msg)
                i += 1

        elif role == "tool":
            # Orphaned tool message (should have been handled in assistant block)
            logger.warning(f"Removing orphaned tool message: {msg.get('tool_call_id')}")
            i += 1

        else:
            # Unknown role - skip
            logger.warning(f"Removing message with unknown role: {role}")
            i += 1

    if len(cleaned) != len(history):
        logger.info(f"Cleaned conversation history: {len(history)} -> {len(cleaned)} messages")

    return cleaned


def truncate_conversation_history(history: List[Dict[str, Any]], max_messages: int = 20) -> List[Dict[str, Any]]:
    """
    Truncate conversation history to reduce token usage.
    Keeps the system message and the most recent messages.

    Args:
        history: Full conversation history
        max_messages: Maximum number of messages to keep

    Returns:
        Truncated conversation history
    """
    if not history or len(history) <= max_messages:
        return history

    # Always keep system message if present
    system_messages = [msg for msg in history if msg.get("role") == "system"]
    other_messages = [msg for msg in history if msg.get("role") != "system"]

    # Keep most recent messages
    recent_messages = other_messages[-(max_messages - len(system_messages)):]

    truncated = system_messages + recent_messages

    if len(history) > len(truncated):
        logger.info(f"Truncated conversation history from {len(history)} to {len(truncated)} messages")

    return truncated


# Global clients (initialized at startup)
mcp_client: Optional[MCPClient] = None
llm_client: Optional[AzureOpenAIClient] = None
db_manager: Optional[DatabaseManager] = None
chat_agent: Optional[Any] = None  # Will be created after initialization

# Throttling: Limit concurrent API calls to prevent burst patterns
import asyncio
_api_call_semaphore: Optional[asyncio.Semaphore] = None


async def initialize_clients(
    mcp: MCPClient,
    llm: AzureOpenAIClient,
    db: Optional[DatabaseManager] = None,
    checkpointer: Optional[BaseCheckpointSaver] = None
):
    """
    Initialize global clients for the agent.

    Args:
        mcp: MCP client instance
        llm: Azure OpenAI client instance
        db: Optional database manager instance
        checkpointer: Optional checkpointer instance (managed by FastAPI lifespan)

    Note:
        The checkpointer should be managed by the FastAPI lifespan context manager
        to ensure proper resource cleanup. Do not create checkpointer here.
    """
    global mcp_client, llm_client, db_manager, chat_agent, _api_call_semaphore
    mcp_client = mcp
    llm_client = llm
    db_manager = db

    # Initialize API call semaphore to limit concurrent requests
    # Limit to 2 concurrent API calls to prevent burst patterns
    _api_call_semaphore = asyncio.Semaphore(2)
    logger.info("API call throttling initialized (max 2 concurrent requests)")

    # Use provided checkpointer (managed by FastAPI lifespan)
    if checkpointer:
        logger.info("Using provided PostgreSQL checkpointer (managed by FastAPI lifespan)")
    else:
        logger.warning("No checkpointer provided - LangGraph persistence disabled")

    # Create the @entrypoint dynamically with the checkpointer
    chat_agent = entrypoint(checkpointer=checkpointer)(_chat_agent_impl)
    logger.info(f"Chat agent entrypoint created (checkpointing: {'enabled' if checkpointer else 'disabled'})")


@task
async def call_llm_task(state: ChatState) -> ChatState:
    """
    Task: Call Azure OpenAI with messages and available tools.

    Args:
        state: Current chat state

    Returns:
        Updated state with LLM response
    """
    if llm_client is None:
        state["error"] = "LLM client not initialized"
        return state

    try:
        # Validate and clean conversation history first
        validated_history = validate_and_clean_conversation_history(state["conversation_history"])

        # Truncate conversation history to reduce token usage
        max_history_messages = int(os.getenv("MAX_CONVERSATION_HISTORY_MESSAGES", "20"))
        truncated_history = truncate_conversation_history(
            validated_history,
            max_messages=max_history_messages
        )

        # Use semaphore to throttle concurrent API calls
        if _api_call_semaphore:
            async with _api_call_semaphore:
                response = await llm_client.chat_completion(
                    messages=truncated_history,
                    tools=state["available_tools"] if state["available_tools"] else None,
                    temperature=0.7
                )
        else:
            # Fallback if semaphore not initialized
            response = await llm_client.chat_completion(
                messages=truncated_history,
                tools=state["available_tools"] if state["available_tools"] else None,
                temperature=0.7
            )

        # Validate response structure
        if not response or not hasattr(response, 'choices') or not response.choices:
            logger.error(f"Invalid LLM response structure: {response}")
            state["error"] = "Invalid response from LLM"
            return state

        content = response.choices[0].message.content or ""  # Handle None content
        tool_calls = llm_client.extract_tool_calls(response)

        # Build assistant message
        assistant_message = {
            "role": "assistant",
            "content": content if content else None  # Keep None if no content for OpenAI format
        }

        # Add tool calls if present
        if tool_calls:
            assistant_message["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["arguments"]
                    }
                }
                for tc in tool_calls
            ]

        # Update state
        state["conversation_history"].append(assistant_message)
        state["current_response"] = content

        # Store tool calls for execution
        if tool_calls:
            state["tool_calls_made"] = tool_calls

        # Log response (handle empty content)
        if content:
            logger.info(f"LLM response: {content[:100]}... (tool_calls: {len(tool_calls)})")
        else:
            logger.info(f"LLM made tool calls only (no text content, {len(tool_calls)} tool calls)")

    except Exception as e:
        logger.error(f"LLM call failed: {e}", exc_info=True)
        state["error"] = str(e)

    return state


@task
async def execute_tools_task(state: ChatState) -> ChatState:
    """
    Task: Execute MCP tools based on LLM's tool calls.

    Args:
        state: Current chat state

    Returns:
        Updated state with tool results
    """
    if mcp_client is None:
        state["error"] = "MCP client not initialized"
        return state

    tool_calls = state.get("tool_calls_made", [])
    if not tool_calls:
        return state

    try:
        for tool_call in tool_calls:
            # Parse arguments
            args_dict = json.loads(tool_call["arguments"])

            # Call the tool
            result = await mcp_client.call_tool(tool_call["name"], args_dict)

            # Convert result to JSON string
            if hasattr(result, "model_dump"):
                result_str = json.dumps(result.model_dump())
            elif hasattr(result, "dict"):
                result_str = json.dumps(result.dict())
            else:
                result_str = str(result)

            # Add tool result to conversation
            state["conversation_history"].append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": result_str
            })

            logger.info(f"Executed tool: {tool_call['name']}")

        # Clear tool calls after execution
        state["tool_calls_made"] = []

    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        state["error"] = str(e)

    return state


async def _chat_agent_impl(
    inputs: Dict[str, Any],
    *,
    previous: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Main agent entrypoint for processing chat messages with LangGraph.

    This uses LangGraph's @entrypoint decorator with PostgreSQL checkpointing
    for stateful, resumable workflows.

    Args:
        inputs: Dict containing user_message and optionally conversation_history
        previous: Previous saved state from checkpointer (managed by LangGraph)

    Returns:
        Dict with response, conversation_history, tool_calls_made

    Usage:
        config = {"configurable": {"thread_id": session_id}}
        result = await chat_agent.ainvoke({"user_message": "Hello"}, config)
    """
    if mcp_client is None or llm_client is None:
        raise RuntimeError("Clients not initialized. Call initialize_clients() first.")

    # Get user message from inputs
    user_message = inputs.get("user_message", "")

    # Use previous conversation history if available, otherwise from inputs
    conversation_history = previous.get("conversation_history", []) if previous else inputs.get("conversation_history", [])

    # Validate and clean conversation history to prevent API errors
    # This removes orphaned tool messages and incomplete tool interactions
    conversation_history = validate_and_clean_conversation_history(conversation_history)

    # Initialize state
    state: ChatState = {
        "session_id": inputs.get("session_id", "default"),
        "user_message": user_message,
        "conversation_history": conversation_history,
        "available_tools": [],
        "current_response": None,
        "tool_calls_made": [],
        "iteration": 0,
        "max_iterations": 10,
        "error": None,
    }

    # Add system message if this is the start of conversation
    if not state["conversation_history"]:
        state["conversation_history"].append({
            "role": "system",
            "content": "You are a helpful AI assistant with access to various tools via MCP servers. Use the available tools when needed to help the user."
        })

    # Add user message
    state["conversation_history"].append({
        "role": "user",
        "content": state["user_message"]
    })

    # Get available tools from MCP client
    state["available_tools"] = mcp_client.get_tools_for_llm()

    # Agent loop - max iterations to prevent infinite loops
    while state["iteration"] < state["max_iterations"]:
        state["iteration"] += 1

        # Call LLM
        state = await call_llm_task(state)

        # Check for errors
        if state.get("error"):
            result = {
                "response": f"I encountered an error: {state['error']}",
                "conversation_history": state["conversation_history"],
                "tool_calls_made": [],
            }
            return entrypoint.final(value=result, save={"conversation_history": state["conversation_history"]})

        # If no tool calls, we're done
        if not state.get("tool_calls_made"):
            result = {
                "response": state["current_response"] or "I apologize, I couldn't generate a response.",
                "conversation_history": state["conversation_history"],
                "tool_calls_made": [],
            }
            # Save conversation history for next invocation
            return entrypoint.final(value=result, save={"conversation_history": state["conversation_history"]})

        # Execute tools
        state = await execute_tools_task(state)

        # Check for errors
        if state.get("error"):
            result = {
                "response": f"I encountered an error while executing tools: {state['error']}",
                "conversation_history": state["conversation_history"],
                "tool_calls_made": [],
            }
            return entrypoint.final(value=result, save={"conversation_history": state["conversation_history"]})

        # Continue loop to get final response after tool execution

    # If we hit max iterations
    logger.warning(f"Agent reached max iterations")
    final_result = {
        "response": "I apologize, but I've reached the maximum number of processing steps. Please try rephrasing your request.",
        "conversation_history": state["conversation_history"],
        "tool_calls_made": [],
    }

    # Save conversation history to checkpoint for next invocation
    return entrypoint.final(
        value=final_result,
        save={"conversation_history": state["conversation_history"]}
    )


# Legacy function for backwards compatibility (will be deprecated)
async def chat_agent_legacy(user_message: str, conversation_history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Legacy chat agent function for backwards compatibility.
    Use chat_agent.ainvoke() with config instead.

    Args:
        user_message: The user's input message
        conversation_history: Previous conversation messages

    Returns:
        Dict containing the assistant's response and updated conversation
    """
    import uuid

    # Call new function with LangGraph pattern
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    result = await chat_agent.ainvoke(
        {"user_message": user_message, "conversation_history": conversation_history},
        config=config
    )

    return result
