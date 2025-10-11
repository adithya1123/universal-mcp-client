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

1. **Use WebSearch tool** to find official documentation
2. **Use WebFetch tool** to read official docs pages
3. **Verify against official sources**:
   - LangGraph: https://langchain-ai.github.io/langgraph/
   - MCP: https://modelcontextprotocol.io/
   - FastAPI: https://fastapi.tiangolo.com/
   - SQLAlchemy: https://docs.sqlalchemy.org/

4. **DO NOT guess or assume** - Always verify with official docs
5. **Update local docs** after learning new patterns

### Code Accuracy Rules

❌ **NEVER:**
- Assume API signatures without checking
- Use outdated patterns from memory
- Guess decorator parameters
- Make up configuration options
- Skip documentation verification

✅ **ALWAYS:**
- Check local docs first
- Search official docs when unsure
- Verify patterns with WebFetch
- Test with small examples
- Update documentation after learning

### Example Workflow

**Before writing LangGraph code:**
1. Open `docs/LANGGRAPH_FUNCTIONAL_API.md`
2. Find relevant example
3. Copy the pattern exactly
4. If pattern not found, use WebSearch/WebFetch
5. Implement based on verified pattern

**Before writing MCP code:**
1. Open `docs/MCP_PROTOCOL.md`
2. Review architecture and patterns
3. Check implementation examples
4. Follow established conventions

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
 