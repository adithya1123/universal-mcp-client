"""Streamable HTTP transport implementation for remote MCP servers."""

from typing import Optional, Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from .base import MCPTransport


class StreamableHttpTransport(MCPTransport):
    """Streamable HTTP transport for remote MCP servers.

    This transport connects to remote MCP servers over HTTP using the
    streamable HTTP protocol (MCP 2025-06-18 specification).
    Supports optional authentication headers.
    """

    def __init__(self, name: str, config: dict[str, Any]):
        """Initialize Streamable HTTP transport.

        Args:
            name: Server name
            config: Configuration with 'url' and optional 'headers'

        Example config:
            {
                "url": "https://api.example.com/mcp",
                "headers": {
                    "Authorization": "Bearer token123"
                }
            }
        """
        super().__init__(name, config)
        self._streams_cm: Optional[Any] = None
        self._session_cm: Optional[Any] = None
        self._get_session_id: Optional[Any] = None

    async def connect(self) -> ClientSession:
        """Connect to Streamable HTTP MCP server.

        Returns:
            ClientSession: Initialized client session

        Raises:
            Exception: If connection fails or URL is missing
        """
        url = self.config.get("url")
        if not url:
            raise ValueError(f"URL is required for HTTP transport: {self.name}")

        headers = self.config.get("headers", {})

        # Enter streamablehttp_client context manager
        self._streams_cm = streamablehttp_client(url=url, headers=headers)
        read_stream, write_stream, get_session_id = await self._streams_cm.__aenter__()
        self._get_session_id = get_session_id

        # Enter ClientSession context manager
        self._session_cm = ClientSession(read_stream, write_stream)
        self._session = await self._session_cm.__aenter__()

        # Initialize the connection
        await self._session.initialize()

        self._connected = True

        # Log session ID if available
        if callable(get_session_id):
            try:
                session_id = get_session_id()
                if session_id:
                    print(f"  Session ID: {session_id}")
            except Exception:
                pass

        return self._session

    async def disconnect(self) -> None:
        """Disconnect from HTTP server and cleanup resources."""
        self._connected = False

        # Exit session context first
        if self._session_cm:
            try:
                await self._session_cm.__aexit__(None, None, None)
            except Exception:
                pass
            finally:
                self._session_cm = None
                self._session = None

        # Exit streams context second
        if self._streams_cm:
            try:
                await self._streams_cm.__aexit__(None, None, None)
            except Exception:
                pass
            finally:
                self._streams_cm = None
                self._get_session_id = None

    def get_session_id(self) -> Optional[str]:
        """Get the current session ID if available.

        Returns:
            Optional[str]: Session ID or None
        """
        if callable(self._get_session_id):
            try:
                return self._get_session_id()
            except Exception:
                return None
        return None
