"""
State definitions for LangGraph workflows.
"""

from typing import TypedDict, List, Dict, Any, Optional


class ChatState(TypedDict, total=False):
    """
    State for chat agent workflow.

    Attributes:
        session_id: Unique identifier for the conversation session
        user_message: Current user message
        conversation_history: Full conversation history in OpenAI format
        available_tools: List of tools available from MCP servers
        current_response: Current assistant response
        tool_calls_made: List of tool calls made in this turn
        iteration: Current iteration in agent loop
        max_iterations: Maximum iterations allowed
        error: Error message if any
    """
    session_id: str
    user_message: str
    conversation_history: List[Dict[str, Any]]
    available_tools: List[Dict[str, Any]]
    current_response: Optional[str]
    tool_calls_made: List[Dict[str, Any]]
    iteration: int
    max_iterations: int
    error: Optional[str]


class AgentInput(TypedDict):
    """
    Input to the chat agent entrypoint.

    Attributes:
        session_id: Session identifier
        user_message: User's message
        conversation_history: Optional previous conversation history
    """
    session_id: str
    user_message: str
    conversation_history: Optional[List[Dict[str, Any]]]


class AgentOutput(TypedDict):
    """
    Output from the chat agent.

    Attributes:
        response: Assistant's final response
        conversation_history: Updated conversation history
        tool_calls_made: List of tool calls made
        session_id: Session identifier
    """
    response: str
    conversation_history: List[Dict[str, Any]]
    tool_calls_made: List[Dict[str, Any]]
    session_id: str
