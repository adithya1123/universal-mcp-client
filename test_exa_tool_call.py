"""Test script to verify Exa MCP tool calls work correctly."""

import asyncio
from src.mcp.client import MCPClient


async def test_exa_tool_call():
    """Test calling Exa search tool."""
    print("=" * 60)
    print("Testing Exa MCP Tool Call")
    print("=" * 60)

    client = MCPClient("config/mcp_servers.json")

    try:
        # Connect to servers
        print("\n📡 Connecting to MCP servers...")
        await client.load_servers()
        print("✓ Connected successfully\n")

        # Test Exa web search
        print("🔍 Testing exa_web_search_exa tool...")
        print("-" * 60)

        search_query = "latest developments in MCP protocol 2025"
        print(f"Query: {search_query}\n")

        result = await client.call_tool(
            "exa_web_search_exa",
            {"query": search_query, "numResults": 3}
        )

        print("Response:")
        print(result)
        print("\n" + "=" * 60)
        print("✅ Tool call successful!")

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
    asyncio.run(test_exa_tool_call())
