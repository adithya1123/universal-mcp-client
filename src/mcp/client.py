"""MCP Client implementation for connecting to MCP servers."""

import json
import re
from typing import Any, Dict, List
from pathlib import Path

from mcp import ClientSession

from .transports import TransportFactory, MCPTransport


class MCPClient:
    """Universal MCP client that can connect to multiple MCP servers.

    Supports multiple transport types (STDIO, HTTP) through a unified
    transport abstraction layer.
    """

    @staticmethod
    def _sanitize_tool_name(name: str) -> str:
        """Sanitize tool names for Azure OpenAI compatibility.

        Azure OpenAI requires tool names to match: ^[a-zA-Z0-9_\.-]+
        This function replaces invalid characters with underscores.

        Args:
            name: Original tool name

        Returns:
            Sanitized tool name with only valid characters
        """
        # Replace spaces and other invalid characters with underscores
        # Keep only alphanumeric, underscore, dot, and hyphen
        sanitized = re.sub(r'[^a-zA-Z0-9_.\-]', '_', name)
        # Collapse multiple consecutive underscores to single underscore
        sanitized = re.sub(r'_+', '_', sanitized)
        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')
        return sanitized

    def __init__(self, config_path: str = "config/mcp_servers.json"):
        self.config_path = Path(config_path)
        self.servers: Dict[str, ClientSession] = {}
        self.tools: Dict[str, Dict[str, Any]] = {}
        # Store transport instances for proper lifecycle management
        self._transports: Dict[str, MCPTransport] = {}

    async def load_servers(self) -> None:
        """Load and connect to MCP servers from configuration."""
        with open(self.config_path) as f:
            config = json.load(f)

        for server_config in config["servers"]:
            if server_config.get("enabled", True):
                await self.connect_server(server_config)

    async def connect_server(self, server_config: Dict[str, Any]) -> None:
        """Connect to a single MCP server using appropriate transport.

        Args:
            server_config: Server configuration with transport type and parameters
        """
        name = server_config["name"]
        transport_type = server_config.get("transport", "stdio")

        try:
            # Create appropriate transport using factory
            transport = TransportFactory.create(name, server_config)
            self._transports[name] = transport

            # Connect and get initialized session
            session = await transport.connect()

            # Store the active session
            self.servers[name] = session

            # Discover and store tools
            await self.discover_tools(name, session)

            print(f"✓ Connected to MCP server: {name} ({transport_type})")

        except Exception as e:
            print(f"✗ Failed to connect to {name} ({transport_type}): {e}")
            # Clean up partial connection if any
            if name in self._transports:
                try:
                    await self._transports[name].disconnect()
                except Exception:
                    pass
                del self._transports[name]
            raise

    async def discover_tools(self, server_name: str, session: ClientSession) -> None:
        """Discover available tools from an MCP server."""
        try:
            tools_result = await session.list_tools()

            for tool in tools_result.tools:
                # Sanitize server name and tool name for Azure OpenAI compatibility
                sanitized_server = self._sanitize_tool_name(server_name)
                sanitized_tool = self._sanitize_tool_name(tool.name)
                tool_key = f"{sanitized_server}_{sanitized_tool}"

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
        """Close all MCP server connections and cleanup resources."""
        print("🛑 Closing MCP connections...")

        for name in list(self.servers.keys()):
            # Disconnect transport
            if name in self._transports:
                try:
                    await self._transports[name].disconnect()
                except Exception as e:
                    print(f"  Warning: Error disconnecting {name}: {e}")
                finally:
                    del self._transports[name]

            # Remove from servers
            self.servers.pop(name, None)

        print("✓ MCP client cleanup completed")

    async def health_check_all(self) -> Dict[str, bool]:
        """Check health status of all connected servers.

        Returns:
            Dict[str, bool]: Map of server name to health status
        """
        results = {}
        for name, transport in self._transports.items():
            try:
                results[name] = await transport.health_check()
            except Exception:
                results[name] = False
        return results

    def get_server_info(self) -> List[Dict[str, Any]]:
        """Get information about all connected servers.

        Returns:
            List[Dict]: List of server information dictionaries
        """
        servers_info = []
        for name, transport in self._transports.items():
            server_tools = [
                tool_key for tool_key in self.tools.keys()
                if self.tools[tool_key]["server"] == name
            ]
            servers_info.append({
                "name": name,
                "transport": transport.config.get("transport", "stdio"),
                "connected": transport.is_connected,
                "tool_count": len(server_tools),
                "tools": server_tools
            })
        return servers_info
