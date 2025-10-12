## Project Overview
- I want to build a web based AI chat assistant that is a universal mcp client. I want to use azure openai as llm. I want to use langgraph for orchestrating the agentic workflows, and chat history must be stored in postgres tables for context management.
- Use hybrid langgraph approach: LangGraph functional api for majority of the orchestration and When needed use traditional langgraph Graph API.
- Use UV for package management.

## Critical: Documentation and Accuracy

### Local Documentation (ALWAYS CHECK FIRST)
Before implementing or modifying any code, **ALWAYS** reference these local documentation files:

1. **docs/LANGGRAPH_FUNCTIONAL_API.md**
   - Complete LangGraph Functional API reference
   - Correct @entrypoint and @task decorator usage
   - Checkpointing patterns with `previous` parameter
   - `entrypoint.final()` usage
   - Invocation patterns (`.ainvoke()`, `.astream()`, etc.)
   - ⚠️ **READ THIS BEFORE ANY LANGGRAPH CODE**

2. **docs/MCP_PROTOCOL.md**
   - Model Context Protocol specification
   - Client-server architecture
   - Transport layers (stdio, SSE)
   - Tool calling patterns
   - Multi-server management
   - ⚠️ **READ THIS BEFORE ANY MCP CODE**

3. **docs/IMPLEMENTATION_REFERENCE.md**
   - Project-specific implementation details
   - Current architecture and patterns
   - Database schema
   - API endpoints
   - Testing and troubleshooting
   - ⚠️ **READ THIS BEFORE MODIFYING EXISTING CODE**

### When Local Docs Are Insufficient

If local documentation doesn't cover your specific use case:

1. **FIRST: Use Ref MCP Server** (if available)
   - Use `mcp__Ref__ref_search_documentation` to search for latest official documentation
   - Use `mcp__Ref__ref_read_url` to read the exact documentation pages
   - This is the PREFERRED method for getting up-to-date, accurate documentation
   - Prevents hallucination and outdated code patterns
   - Example: Search "LangGraph functional API entrypoint decorator" or "FastAPI async dependency injection"

2. **SECOND: Use Exa MCP Server** for real-time code examples and technical discussions
   - **Tool**: `mcp__exa__get_code_context_exa`
     - Best for: Finding up-to-date code snippets and implementation patterns
     - Returns: Actual code examples from GitHub, official docs, and technical blogs
     - Use when: You need current API usage patterns or solving complex implementation problems
     - Example: "LangGraph functional API state management examples"
   - **Tool**: `mcp__exa__web_search_exa`
     - Best for: Finding recent tutorials, blog posts, and technical discussions
     - Use when: Researching new technologies or rapidly evolving frameworks
     - Returns: Full article content with metadata
   - **Key advantage**: Provides the most current technical information, crucial for avoiding outdated code

3. **FALLBACK: Use WebSearch/WebFetch tools** if Ref/Exa MCP are unavailable
   - Use WebSearch tool to find official documentation
   - Use WebFetch tool to read official docs pages

4. **Verify against official sources**:
   - LangGraph: https://langchain-ai.github.io/langgraph/
   - MCP: https://modelcontextprotocol.io/
   - FastAPI: https://fastapi.tiangolo.com/
   - SQLAlchemy: https://docs.sqlalchemy.org/

5. **DO NOT guess or assume** - Always verify with official docs via Ref/Exa MCP or WebFetch
6. **Update local docs** after learning new patterns

### Code Accuracy Rules

❌ **NEVER:**
- Assume API signatures without checking
- Use outdated patterns from memory
- Guess decorator parameters
- Make up configuration options
- Skip documentation verification
- **Write code from memory - ALWAYS verify with Ref MCP or official docs first**
- **Hallucinate API methods or parameters - use Ref MCP to check**

✅ **ALWAYS:**
- Check local docs first
- **Use Ref MCP server (`mcp__Ref__ref_search_documentation`) for latest documentation**
- **Read documentation with Ref MCP (`mcp__Ref__ref_read_url`) before implementing**
- **Use Exa MCP (`mcp__exa__get_code_context_exa`) for current code examples and implementation patterns**
- **Use Exa MCP (`mcp__exa__web_search_exa`) for recent tutorials and technical discussions**
- Search official docs when Ref/Exa MCP are unavailable
- Verify patterns with WebFetch as fallback
- Test with small examples
- Update documentation after learning
- **When in doubt, look it up - never guess**

### Example Workflow

**Before writing LangGraph code:**
1. Open `docs/LANGGRAPH_FUNCTIONAL_API.md`
2. Find relevant example
3. Copy the pattern exactly
4. If pattern not found:
   - **FIRST**: Use `mcp__Ref__ref_search_documentation` with query like "LangGraph functional API [specific feature]"
   - **THEN**: Use `mcp__Ref__ref_read_url` to read the official documentation
   - **ALSO**: Use `mcp__exa__get_code_context_exa` for current code examples if needed
   - **FALLBACK**: Use WebSearch/WebFetch if Ref/Exa MCP unavailable
5. Implement based on verified pattern

**Before writing MCP code:**
1. Open `docs/MCP_PROTOCOL.md`
2. Review architecture and patterns
3. Check implementation examples
4. If unclear:
   - Use Ref MCP to search "MCP protocol [specific topic]"
   - Use Exa MCP for recent implementation examples
5. Follow established conventions

**Before writing FastAPI/SQLAlchemy/other library code:**
1. Check if pattern exists in existing codebase
2. If not:
   - Use `mcp__Ref__ref_search_documentation` to find latest official docs
   - Read the documentation with `mcp__Ref__ref_read_url`
   - Use `mcp__exa__get_code_context_exa` for current usage patterns
3. Implement using verified, up-to-date patterns

**Before modifying existing code:**
1. Open `docs/IMPLEMENTATION_REFERENCE.md`
2. Understand current architecture
3. Check database schema
4. Review API patterns
5. Make changes consistent with existing code

## Implementation Standards

### LangGraph Patterns (FROM docs/LANGGRAPH_FUNCTIONAL_API.md)

✅ **Correct @entrypoint usage:**
```python
@entrypoint(checkpointer=_get_checkpointer)
async def workflow(inputs: dict, *, previous: dict = None) -> dict:
    # Use previous parameter for saved state
    state = previous.get("key", default) if previous else default

    # Process...

    # Use entrypoint.final to separate return vs save
    return entrypoint.final(
        value={"response": "..."},
        save={"state_to_save": "..."}
    )

# Invoke with config
config = {"configurable": {"thread_id": session_id}}
result = await workflow.ainvoke(inputs, config=config)
```

❌ **Wrong patterns:**
```python
# DON'T use lambda for checkpointer
@entrypoint(checkpointer=lambda: checkpointer)  # ❌

# DON'T forget previous parameter
@entrypoint()
async def workflow(inputs: dict) -> dict:  # ❌ Missing previous

# DON'T call directly without .ainvoke
result = await workflow(inputs)  # ❌ Wrong invocation
```

### MCP Patterns (FROM docs/MCP_PROTOCOL.md)

✅ **Correct MCP client usage:**
```python
# Tool naming with server prefix
tool_key = f"{server_name}_{tool.name}"

# Proper cleanup
async with stdio_client(params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        # Use session...
```

### Database Patterns (FROM docs/IMPLEMENTATION_REFERENCE.md)

✅ **Correct async database operations:**
```python
# Use database manager
history = await db_manager.get_conversation_history(session_id)
await db_manager.save_message(session_id, role, content)
```

## Verification Checklist

Before committing any code:
- [ ] Checked relevant local documentation
- [ ] Verified with official docs if needed
- [ ] Followed established patterns
- [ ] Tested implementation
- [ ] Updated documentation if learned new patterns

## Documentation Maintenance

When you learn new patterns or fix issues:
1. Document the correct pattern in appropriate local doc
2. Add examples
3. Note common mistakes to avoid
4. Keep docs synchronized with code

**Remember: Accurate code comes from accurate documentation. Always verify, never assume.**
 