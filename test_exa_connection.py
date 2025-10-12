"""Test script to verify Exa MCP server connection over HTTP."""

import asyncio
from src.mcp.client import MCPClient


async def test_exa_connection():
    """Test connection to Exa search MCP server."""
    print("=" * 60)
    print("Testing Exa MCP Server Connection (HTTP Transport)")
    print("=" * 60)

    # Create client with test config
    client = MCPClient("config/mcp_servers.json")

    try:
        # Load servers (will connect to enabled servers including Exa)
        print("\n📡 Connecting to MCP servers...")
        await client.load_servers()

        print("\n📊 Server Information:")
        print("-" * 60)
        for server_info in client.get_server_info():
            print(f"\nServer: {server_info['name']}")
            print(f"  Transport: {server_info['transport']}")
            print(f"  Connected: {server_info['connected']}")
            print(f"  Tools: {server_info['tool_count']}")
            if server_info['tools']:
                print(f"  Tool list:")
                for tool in server_info['tools'][:5]:  # Show first 5 tools
                    print(f"    - {tool}")
                if len(server_info['tools']) > 5:
                    print(f"    ... and {len(server_info['tools']) - 5} more")

        print("\n🔍 Health Check:")
        print("-" * 60)
        health_status = await client.health_check_all()
        for server_name, is_healthy in health_status.items():
            status = "✅ Healthy" if is_healthy else "❌ Unhealthy"
            print(f"{server_name}: {status}")

        print("\n✅ Test completed successfully!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Clean up
        print("\n🧹 Cleaning up...")
        await client.close()
        print("Done!\n")


if __name__ == "__main__":
    asyncio.run(test_exa_connection())
