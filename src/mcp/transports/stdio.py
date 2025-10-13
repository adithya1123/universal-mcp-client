"""STDIO transport implementation for local MCP servers."""

from typing import Optional, Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .base import MCPTransport


class StdioTransport(MCPTransport):
    """STDIO transport for local process-based MCP servers.

    This transport spawns a local process and communicates via stdin/stdout.
    Typically used for servers like filesystem, PostgreSQL, etc.
    """

    def __init__(self, name: str, config: dict[str, Any]):
        """Initialize STDIO transport.

        Args:
            name: Server name
            config: Configuration with 'command', 'args', and optional 'env'
        """
        super().__init__(name, config)
        self._stdio_cm: Optional[Any] = None
        self._session_cm: Optional[Any] = None

    async def connect(self) -> ClientSession:
        """Connect to STDIO MCP server.

        Returns:
            ClientSession: Initialized client session
        """
        server_params = StdioServerParameters(
            command=self.config["command"],
            args=self.config.get("args", []),
            env=self.config.get("env")
        )

        # Enter stdio_client context manager
        self._stdio_cm = stdio_client(server_params)
        read_stream, write_stream = await self._stdio_cm.__aenter__()

        # Enter ClientSession context manager
        self._session_cm = ClientSession(read_stream, write_stream)
        self._session = await self._session_cm.__aenter__()

        # Initialize the connection
        await self._session.initialize()

        self._connected = True
        return self._session

    async def disconnect(self) -> None:
        """Disconnect from STDIO server and cleanup resources."""
        self._connected = False

        # Exit session context first
        if self._session_cm:
            try:
                await self._session_cm.__aexit__(None, None, None)
            except Exception:
                # Suppress anyio cancel scope errors
                pass
            finally:
                self._session_cm = None
                self._session = None

        # Exit stdio context second
        if self._stdio_cm:
            try:
                await self._stdio_cm.__aexit__(None, None, None)
            except Exception:
                # Suppress anyio cancel scope errors
                pass
            finally:
                self._stdio_cm = None
