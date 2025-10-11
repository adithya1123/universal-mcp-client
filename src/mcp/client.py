"""MCP Client implementation for connecting to MCP servers."""

import json
from typing import Any, Dict, List
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClient:
    """Universal MCP client that can connect to multiple MCP servers.

    Uses direct context manager entry to keep connections alive for the
    application lifetime. The contexts must be managed properly to avoid
    the 'Attempted to exit cancel scope in a different task' error.
    """

    def __init__(self, config_path: str = "config/mcp_servers.json"):
        self.config_path = Path(config_path)
        self.servers: Dict[str, ClientSession] = {}
        self.tools: Dict[str, Dict[str, Any]] = {}
        # Store context managers for proper cleanup
        self._stdio_cms: Dict[str, Any] = {}
        self._session_cms: Dict[str, Any] = {}

    async def load_servers(self) -> None:
        """Load and connect to MCP servers from configuration."""
        with open(self.config_path) as f:
            config = json.load(f)

        for server_config in config["servers"]:
            if server_config.get("enabled", True):
                await self.connect_server(server_config)

    async def connect_server(self, server_config: Dict[str, Any]) -> None:
        """Connect to a single MCP server.

        Uses manual __aenter__() to keep connections alive. The contexts
        will be cleaned up properly in close() using __aexit__().
        """
        name = server_config["name"]

        if server_config["transport"] == "stdio":
            server_params = StdioServerParameters(
                command=server_config["command"],
                args=server_config.get("args", []),
                env=server_config.get("env")
            )

            # Enter stdio_client context manager
            stdio_cm = stdio_client(server_params)
            read_stream, write_stream = await stdio_cm.__aenter__()
            self._stdio_cms[name] = stdio_cm

            # Enter ClientSession context manager
            session_cm = ClientSession(read_stream, write_stream)
            session = await session_cm.__aenter__()
            self._session_cms[name] = session_cm

            # Initialize the connection
            await session.initialize()

            # Store the active session
            self.servers[name] = session

            # Discover and store tools
            await self.discover_tools(name, session)

            print(f"✓ Connected to MCP server: {name}")

    async def discover_tools(self, server_name: str, session: ClientSession) -> None:
        """Discover available tools from an MCP server."""
        try:
            tools_result = await session.list_tools()

            for tool in tools_result.tools:
                # Use underscore instead of colon for Azure OpenAI compatibility
                tool_key = f"{server_name}_{tool.name}"
                self.tools[tool_key] = {
                    "server": server_name,
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema
                }
                print(f"  - Discovered tool: {tool_key}")
        except Exception as e:
            print(f"Error discovering tools from {server_name}: {e}")

    async def call_tool(self, tool_key: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the appropriate MCP server."""
        if tool_key not in self.tools:
            raise ValueError(f"Tool {tool_key} not found")

        tool_info = self.tools[tool_key]
        server_name = tool_info["server"]
        tool_name = tool_info["name"]

        session = self.servers[server_name]

        result = await session.call_tool(tool_name, arguments)
        return result

    def get_tools_for_llm(self) -> List[Dict[str, Any]]:
        """Get tools formatted for LLM function calling."""
        llm_tools = []

        for tool_key, tool_info in self.tools.items():
            llm_tools.append({
                "type": "function",
                "function": {
                    "name": tool_key,
                    "description": tool_info["description"],
                    "parameters": tool_info["input_schema"]
                }
            })

        return llm_tools

    async def close(self) -> None:
        """Close all MCP server connections.

        NOTE: Due to anyio's cancel scope restrictions, cleanup errors may occur
        if this is called from a different task than initialization. These errors
        are suppressed as the process/container shutdown will clean up resources.
        """
        print("🛑 Closing MCP connections...")

        for name in list(self.servers.keys()):
            # Exit session context first
            if name in self._session_cms:
                try:
                    await self._session_cms[name].__aexit__(None, None, None)
                except Exception:
                    # Suppress anyio cancel scope errors - resources will be cleaned
                    # up by process termination anyway
                    pass
                finally:
                    del self._session_cms[name]

            # Exit stdio context second
            if name in self._stdio_cms:
                try:
                    await self._stdio_cms[name].__aexit__(None, None, None)
                except Exception:
                    # Suppress anyio cancel scope errors
                    pass
                finally:
                    del self._stdio_cms[name]

            # Remove from servers
            self.servers.pop(name, None)

        print("✓ MCP client cleanup completed")
