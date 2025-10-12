"""Transport factory for creating appropriate transport instances."""

from typing import Any

from .base import MCPTransport, TransportType
from .stdio import StdioTransport
from .streamable_http import StreamableHttpTransport


class TransportFactory:
    """Factory for creating MCP transport instances based on configuration."""

    @staticmethod
    def create(name: str, config: dict[str, Any]) -> MCPTransport:
        """Create appropriate transport based on configuration.

        Args:
            name: Server name
            config: Server configuration containing transport type and parameters

        Returns:
            MCPTransport: Appropriate transport instance

        Raises:
            ValueError: If transport type is unsupported or missing
        """
        transport_type = config.get("transport", "stdio").lower()

        if transport_type == TransportType.STDIO:
            return StdioTransport(name, config)
        elif transport_type == TransportType.HTTP:
            return StreamableHttpTransport(name, config)
        else:
            raise ValueError(
                f"Unsupported transport type '{transport_type}' for server '{name}'. "
                f"Supported types: {[t.value for t in TransportType]}"
            )

    @staticmethod
    def get_supported_types() -> list[str]:
        """Get list of supported transport types.

        Returns:
            list[str]: List of supported transport type strings
        """
        return [t.value for t in TransportType]
