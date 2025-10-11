# Quick Start Guide

## 🚀 Get Running in 3 Steps

### Step 1: Start the Backend

```bash
./run_backend.sh
```

You should see:
```
🚀 Starting Universal MCP Client...
✓ Connected to MCP server: filesystem
  - Discovered tool: read_file
  - Discovered tool: write_file
  ... (14 tools total)
✅ All systems ready!
INFO: Uvicorn running on http://0.0.0.0:8000
```

### Step 2: Start the Frontend (New Terminal)

```bash
cd frontend
npm run dev
```

You should see:
```
  VITE v6.x.x  ready in xxx ms

  ➜  Local:   http://localhost:3000/
```

### Step 3: Open Browser

Navigate to: **http://localhost:3000**

You'll see:
- Chat interface
- "Connected! 14 tools available from MCP servers" message
- Green connection indicator

## 🧪 Test the System

### Test 1: Simple Chat
**You:** "Hello, what can you do?"
**Assistant:** Should list available capabilities and tools

### Test 2: File Operations
**You:** "List all files in the /tmp directory"
**Assistant:** Will use the `filesystem:list_directory` tool to show files

### Test 3: File Reading
**You:** "Create a test file at /tmp/hello.txt with content 'Hello from MCP!'"
**Assistant:** Will use `filesystem:write_file` tool

**You:** "Now read that file"
**Assistant:** Will use `filesystem:read_text_file` tool

## 📊 Verify Backend Status

Check health:
```bash
curl http://localhost:8000/health | jq .
```

List available tools:
```bash
curl http://localhost:8000/tools | jq '.tools[] | {name: .name, description: .description}'
```

## 🔍 Available MCP Tools

The filesystem server provides 14 tools:
1. `read_text_file` - Read file contents
2. `write_file` - Create/overwrite files
3. `edit_file` - Line-based file editing
4. `create_directory` - Create directories
5. `list_directory` - List directory contents
6. `list_directory_with_sizes` - List with file sizes
7. `directory_tree` - Recursive tree view
8. `move_file` - Move/rename files
9. `search_files` - Search for files
10. `get_file_info` - Get file metadata
11. `read_media_file` - Read images/audio
12. `read_multiple_files` - Batch file reading
13. `list_allowed_directories` - Show accessible paths
14. `read_file` (deprecated)

## 🛠️ Troubleshooting

**Backend won't start?**
- Ensure you have UV installed: `uv --version`
- Check Python version: `python --version` (need 3.13+)
- Verify .env file exists with Azure OpenAI credentials

**Frontend won't start?**
- Install dependencies: `npm install` in frontend/ directory
- Check Node version: `node --version` (need 18+)

**Can't connect to WebSocket?**
- Ensure backend is running on port 8000
- Check browser console for errors
- Verify CORS settings in src/api/server.py

**No tools showing?**
- Check if npx is installed: `npx --version`
- Verify config/mcp_servers.json has correct MCP server config
- Look at backend logs for connection errors

## 📝 Next Steps

1. Try different file operations through chat
2. Add more MCP servers to config/mcp_servers.json
3. Explore the codebase:
   - `src/orchestration/agent.py` - LangGraph workflows
   - `src/mcp/client.py` - MCP client logic
   - `frontend/src/components/Chat.tsx` - Chat UI

4. Move to Phase 2:
   - Add Postgres for persistence
   - Support multiple MCP servers
   - Build server configuration UI

## 🎉 Success Indicators

✅ Backend shows "All systems ready!"
✅ 14 tools discovered from filesystem server
✅ Frontend shows green "Connected" status
✅ Chat interface is responsive
✅ Tools execute successfully when requested by LLM

Happy chatting! 🤖
