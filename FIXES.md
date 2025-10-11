# Fixes Applied to Phase 2

## Issue: LangGraph @entrypoint TypeError and Pregel Object

### Errors Encountered
1. `TypeError: unhashable type: 'dict'` - TypedDict not hashable for caching
2. `TypeError: 'Pregel' object is not callable` - @entrypoint returns graph, not function

### Root Cause
LangGraph's @entrypoint decorator:
1. Tries to cache functions by hashing input types (TypedDict fails)
2. Returns a Pregel graph object, not a callable function
3. Requires additional setup for proper invocation

### Solution
**Removed @entrypoint decorator entirely** and use @task decorators only:

**Before:**
```python
@entrypoint
async def chat_agent(input_data: AgentInput) -> AgentOutput:
    # ... agent logic
```

**After:**
```python
# No decorator - just a regular async function
async def chat_agent(input_data: dict) -> dict:
    # ... agent logic with @task decorated subtasks
```

**Why This Works:**
- @task decorators provide LangGraph integration at the task level
- Main function remains a simple async function that's directly callable
- State management still uses TypedDict internally for type safety
- Simpler, more maintainable approach

### Changes Made

1. **src/orchestration/agent.py**
   - **Removed `@entrypoint` decorator completely**
   - Kept `@task` decorators on `call_llm_task()` and `execute_tools_task()`
   - Changed input type from `AgentInput` to `dict` for flexibility
   - Changed return type from `AgentOutput` to `dict`
   - Updated all return statements to use plain dicts
   - Removed unused imports (AgentInput, AgentOutput)
   - Added `.get()` with defaults for safer dict access

2. **src/api/server.py**
   - Removed `AgentInput` import
   - Changed from `AgentInput(...)` to plain dict `{...}`
   - Updated both REST endpoint and WebSocket handler
   - No changes needed to how we call the agent (still just `await chat_agent(input)`)

### Why This Works
- **@task decorators** provide LangGraph observability and structure
- **Main agent function** is a simple async function (directly callable)
- **State management** still uses TypedDict internally for type safety
- **No Pregel complexity** - straightforward async function calls
- **Simpler and more maintainable** than full StateGraph approach

### Current LangGraph Integration Level
✅ **Hybrid Approach** (as per project requirements):
- `@task` decorators for individual tasks (LLM calls, tool execution)
- Regular async function for orchestration
- TypedDict for internal state management
- Ready to add StateGraph in Phase 3 if needed

### Best Practices Going Forward
For LangGraph Functional API:
- Use `@task` for discrete operations (LLM calls, tool execution)
- Keep main orchestrator as regular async function
- Use TypedDict for state definitions (not as type hints)
- Reserve `@entrypoint` for when you need full Pregel features
- Document expected dict structure in docstrings

### Additional Fixes in This Session

1. **SQLAlchemy metadata conflict** - Renamed to `checkpoint_metadata`
2. **Deprecated datetime.utcnow()** - Updated to `datetime.now(timezone.utc)`
3. **Missing greenlet dependency** - Added for SQLAlchemy async
4. **Environment loading** - Added dotenv to init script

All issues resolved! ✅
