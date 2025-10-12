"""Base transport abstraction for MCP clients."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Any

from mcp import ClientSession


class TransportType(str, Enum):
    """Supported MCP transport types."""
    STDIO = "stdio"
    HTTP = "http"


class MCPTransport(ABC):
    """Abstract base class for MCP transports.

    All transport implementations must extend this class and implement
    the required methods for connection lifecycle management.
    """

    def __init__(self, name: str, config: dict[str, Any]):
        """Initialize transport with server name and configuration.

        Args:
            name: Unique server name
            config: Transport-specific configuration
        """
        self.name = name
        self.config = config
        self._session: Optional[ClientSession] = None
        self._connected: bool = False

    @abstractmethod
    async def connect(self) -> ClientSession:
        """Establish connection and return initialized ClientSession.

        Returns:
            ClientSession: Initialized MCP client session

        Raises:
            Exception: If connection fails
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection and cleanup resources."""
        pass

    async def health_check(self) -> bool:
        """Check if transport connection is healthy.

        Returns:
            bool: True if healthy, False otherwise
        """
        if not self.is_connected or not self._session:
            return False

        try:
            # Use list_tools as a health check probe
            await self._session.list_tools()
            return True
        except Exception:
            return False

    @property
    def is_connected(self) -> bool:
        """Check if transport is currently connected."""
        return self._connected

    @property
    def session(self) -> Optional[ClientSession]:
        """Get the active ClientSession if connected."""
        return self._session
