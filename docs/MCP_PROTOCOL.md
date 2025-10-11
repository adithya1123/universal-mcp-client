# Model Context Protocol (MCP) - Complete Reference

**Last Updated:** January 2025
**Current Specification:** 2025-06-18
**Source:** https://modelcontextprotocol.io/

---

## Overview

**Model Context Protocol (MCP)** is an open protocol that enables seamless integration between LLM applications and external data sources and tools.

### Purpose
- Standardized way to connect LLMs with context
- Works with AI-powered IDEs, chat interfaces, custom AI workflows
- Enables dynamic tool and resource discovery

---

## Architecture

### Participants

```
┌──────────────┐
│   MCP Host   │  (AI Application coordinating clients)
└──────┬───────┘
       │
       ├─────┐
       │     │
       ▼     ▼
┌──────────┐ ┌──────────┐
│  Client  │ │  Client  │  (Maintains 1:1 connection to server)
└────┬─────┘ └────┬─────┘
     │            │
     ▼            ▼
┌──────────┐ ┌──────────┐
│  Server  │ │  Server  │  (Provides context to clients)
└──────────┘ └──────────┘
```

### Key Components

1. **MCP Host**
   - AI application (e.g., IDE, chat app)
   - Coordinates multiple MCP clients
   - Manages client lifecycle

2. **MCP Client**
   - Maintains 1:1 connection to MCP server
   - Discovers and invokes tools/resources
   - Handles protocol messages

3. **MCP Server**
   - Exposes tools, resources, prompts
   - Processes client requests
   - Provides context to LLMs

---

## Protocol Layers

### 1. Data Layer (JSON-RPC 2.0)

**Purpose:** Define message format and protocol primitives

**Features:**
- Lifecycle management
- Capability negotiation
- Server/client feature discovery
- Real-time notifications

**Core Primitives:**

#### Server Primitives
- **Tools:** Executable functions that LLM can call
- **Resources:** Contextual data sources (files, API data, etc.)
- **Prompts:** Interaction templates for LLM

#### Client Primitives
- **Sampling:** Request LLM completions
- **Elicitation:** Request user information
- **Logging:** Send debug/log messages

### 2. Transport Layer

**Purpose:** Enable communication between client and server

**Supported Transports:**

#### a. Stdio Transport
- **Use Case:** Local process communication
- **How it works:**
  - Server runs as child process
  - Communication via stdin/stdout
  - No authentication needed (local only)

**Example:**
```json
{
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"],
  "transport": "stdio"
}
```

#### b. Streamable HTTP Transport (SSE)
- **Use Case:** Remote server communication
- **How it works:**
  - HTTP-based with Server-Sent Events
  - Supports authentication
  - Cross-network communication

**Example:**
```json
{
  "url": "https://api.example.com/mcp",
  "transport": "sse",
  "headers": {
    "Authorization": "Bearer token"
  }
}
```

---

## Initialization Process

```
Client                          Server
  │                               │
  │──── initialize() ────────────>│
  │                               │
  │<─── capabilities ─────────────│
  │                               │
  │──── initialized ─────────────>│
  │                               │
  │<─── tools/list() ─────────────│
  │                               │
  │<─── resources/list() ─────────│
  │                               │
  │        Ready for use          │
```

### Steps

1. **Initialize:** Client sends protocol version and capabilities
2. **Negotiate:** Server responds with its capabilities
3. **Confirm:** Client confirms initialization
4. **Discover:** Exchange available tools/resources
5. **Ready:** Connection established, ready for requests

---

## Tools

### Purpose
Executable functions that LLM can invoke

### Tool Definition
```json
{
  "name": "read_file",
  "description": "Read contents of a file",
  "inputSchema": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "File path to read"
      }
    },
    "required": ["path"]
  }
}
```

### Tool Invocation
```json
// Request
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "read_file",
    "arguments": {
      "path": "/path/to/file.txt"
    }
  }
}

// Response
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "File contents here..."
      }
    ]
  }
}
```

### Tool Discovery
```json
// Request
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list"
}

// Response
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "read_file",
        "description": "Read a file",
        "inputSchema": { ... }
      },
      {
        "name": "write_file",
        "description": "Write to a file",
        "inputSchema": { ... }
      }
    ]
  }
}
```

---

## Resources

### Purpose
Provide contextual data to LLMs (files, API data, database records, etc.)

### Resource Definition
```json
{
  "uri": "file:///path/to/file.txt",
  "name": "Configuration File",
  "description": "Application configuration",
  "mimeType": "text/plain"
}
```

### Resource Reading
```json
// Request
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "resources/read",
  "params": {
    "uri": "file:///path/to/file.txt"
  }
}

// Response
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "contents": [
      {
        "uri": "file:///path/to/file.txt",
        "mimeType": "text/plain",
        "text": "Resource contents..."
      }
    ]
  }
}
```

---

## Notifications

### Purpose
Real-time updates from server to client

### Examples

#### Tools Changed
```json
{
  "jsonrpc": "2.0",
  "method": "notifications/tools/list_changed"
}
```

#### Resource Updated
```json
{
  "jsonrpc": "2.0",
  "method": "notifications/resources/updated",
  "params": {
    "uri": "file:///path/to/file.txt"
  }
}
```

---

## Client Implementation (Python)

### Basic Client Setup

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Server parameters
server_params = StdioServerParameters(
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"]
)

# Create client session
async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        # Initialize connection
        await session.initialize()

        # List available tools
        tools = await session.list_tools()
        print(f"Available tools: {[t.name for t in tools]}")

        # Call a tool
        result = await session.call_tool(
            "read_file",
            arguments={"path": "config.json"}
        )
        print(f"Result: {result.content}")
```

### Tool Discovery and Calling

```python
async def discover_and_call_tools(session: ClientSession):
    # Discover tools
    tools_result = await session.list_tools()

    # Convert to LLM-friendly format
    tools_for_llm = [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema
            }
        }
        for tool in tools_result.tools
    ]

    # LLM decides to call a tool
    tool_name = "read_file"
    tool_args = {"path": "/path/to/file.txt"}

    # Execute tool
    result = await session.call_tool(tool_name, arguments=tool_args)

    return result
```

### Multiple Server Management

```python
class MCPClientManager:
    def __init__(self):
        self.servers = {}  # server_name -> session
        self.tools = {}    # tool_key -> server_name

    async def connect_server(self, name: str, params: StdioServerParameters):
        # Create connection
        read, write = await stdio_client(params).__aenter__()
        session = await ClientSession(read, write).__aenter__()
        await session.initialize()

        # Store session
        self.servers[name] = session

        # Discover tools
        tools = await session.list_tools()
        for tool in tools:
            key = f"{name}_{tool.name}"
            self.tools[key] = name

    async def call_tool(self, tool_key: str, arguments: dict):
        server_name = self.tools.get(tool_key)
        if not server_name:
            raise ValueError(f"Tool {tool_key} not found")

        session = self.servers[server_name]
        result = await session.call_tool(tool_key.split("_", 1)[1], arguments)
        return result

    async def close_all(self):
        for session in self.servers.values():
            await session.__aexit__(None, None, None)
```

---

## Server Configuration

### JSON Configuration File

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"],
      "transport": "stdio"
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "ghp_..."
      },
      "transport": "stdio"
    },
    "remote-api": {
      "url": "https://api.example.com/mcp",
      "transport": "sse",
      "headers": {
        "Authorization": "Bearer token"
      }
    }
  }
}
```

### Dynamic Server Configuration

```python
class ServerConfig:
    def __init__(self):
        self.servers = []

    def add_stdio_server(self, name: str, command: str, args: list, env: dict = None):
        self.servers.append({
            "name": name,
            "command": command,
            "args": args,
            "env": env or {},
            "transport": "stdio"
        })

    def add_http_server(self, name: str, url: str, headers: dict = None):
        self.servers.append({
            "name": name,
            "url": url,
            "headers": headers or {},
            "transport": "sse"
        })

    async def connect_all(self) -> MCPClientManager:
        manager = MCPClientManager()
        for config in self.servers:
            if config["transport"] == "stdio":
                params = StdioServerParameters(
                    command=config["command"],
                    args=config["args"],
                    env=config.get("env")
                )
                await manager.connect_server(config["name"], params)
        return manager
```

---

## Best Practices

### 1. Error Handling
```python
async def safe_tool_call(session: ClientSession, tool_name: str, args: dict):
    try:
        result = await session.call_tool(tool_name, arguments=args)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

### 2. Tool Naming Convention
Use server prefix to avoid conflicts:
```python
# Good: server_toolname
filesystem_read_file
github_list_repos

# Bad: generic names
read_file  # Which server?
list       # Too generic
```

### 3. Connection Management
```python
async def with_mcp_session(server_params, callback):
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await callback(session)
```

### 4. Health Checks
```python
async def check_server_health(session: ClientSession) -> bool:
    try:
        # Try listing tools as health check
        await session.list_tools()
        return True
    except:
        return False
```

---

## Common Patterns

### Pattern 1: Single Server Connection
```python
async def simple_mcp_client():
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            # Use tools...
```

### Pattern 2: Multi-Server Architecture
```python
async def multi_server_client():
    manager = MCPClientManager()

    # Connect to filesystem server
    await manager.connect_server("filesystem", StdioServerParameters(...))

    # Connect to GitHub server
    await manager.connect_server("github", StdioServerParameters(...))

    # Use unified interface
    result = await manager.call_tool("filesystem_read_file", {"path": "/"})
```

### Pattern 3: Tool Discovery for LLM
```python
async def get_tools_for_llm(session: ClientSession) -> list[dict]:
    """Convert MCP tools to OpenAI function calling format."""
    tools_result = await session.list_tools()

    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema
            }
        }
        for tool in tools_result.tools
    ]
```

---

## Available MCP Servers

### Official Servers

- **@modelcontextprotocol/server-filesystem** - File system operations
- **@modelcontextprotocol/server-github** - GitHub API integration
- **@modelcontextprotocol/server-slack** - Slack integration
- **@modelcontextprotocol/server-postgres** - PostgreSQL database
- **@modelcontextprotocol/server-brave-search** - Web search
- **@modelcontextprotocol/server-google-drive** - Google Drive access

### Discovery

MCP Registry: https://registry.modelcontextprotocol.io

---

## Troubleshooting

### Issue: Connection Failed
```python
# Check if server process started
try:
    async with stdio_client(params) as (read, write):
        print("Connected successfully")
except Exception as e:
    print(f"Connection failed: {e}")
```

### Issue: Tool Not Found
```python
# List available tools
tools = await session.list_tools()
available = [t.name for t in tools]
print(f"Available tools: {available}")
```

### Issue: Invalid Arguments
```python
# Check tool schema
tools = await session.list_tools()
for tool in tools:
    if tool.name == "my_tool":
        print(f"Schema: {tool.inputSchema}")
```

---

## Security Considerations

1. **Stdio Transport:** Trusted local processes only
2. **HTTP Transport:** Use HTTPS and authentication
3. **Tool Execution:** Validate and sanitize all inputs
4. **Resource Access:** Implement proper access controls
5. **Rate Limiting:** Protect against abuse

---

## References

- **Specification:** https://modelcontextprotocol.io/specification/2025-06-18
- **Architecture:** https://modelcontextprotocol.io/docs/learn/architecture
- **Registry:** https://registry.modelcontextprotocol.io
- **GitHub:** https://github.com/modelcontextprotocol
