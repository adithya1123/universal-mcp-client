# LangGraph Functional API - Complete Reference

**Last Updated:** January 2025
**Source:** https://langchain-ai.github.io/langgraph/

---

## Overview

The Functional API allows adding LangGraph features like **persistence**, **memory**, **human-in-the-loop**, and **streaming** with minimal code changes.

### Key Building Blocks

1. **`@entrypoint`** - Marks workflow starting point
2. **`@task`** - Represents discrete unit of work

Both APIs share the same underlying runtime and can be used together.

---

## @entrypoint Decorator

### Purpose
- Marks a function as the workflow's starting point
- Converts function into a Pregel graph
- Manages execution flow, handles long-running tasks and interrupts

### Signature
```python
@entrypoint(
    checkpointer=None,      # Optional checkpoint saver
    store=None,             # Optional key-value store
    cache=None,             # Optional result cache
    context_schema=None,    # Optional context object schema
    cache_policy=None,      # Optional caching strategy
    retry_policy=None       # Optional retry mechanism
)
def workflow(inputs, *, previous=None, config=None, runtime=None):
    pass
```

### Requirements
- Must accept a **single positional input parameter**
- Inputs and outputs must be **JSON-serializable**
- Can inject additional **keyword-only runtime parameters**:
  - `previous`: Previous saved state from checkpointer
  - `config`: Runtime configuration
  - `runtime`: Runtime information
  - `store`: Key-value store instance

### Basic Example
```python
from langgraph.func import entrypoint
from langgraph.checkpoint.memory import InMemorySaver

@entrypoint(checkpointer=InMemorySaver())
def workflow(inputs: dict, *, previous: dict = None) -> dict:
    if previous:
        # Use previous state
        count = previous.get("count", 0)
    else:
        count = 0

    count += inputs.get("increment", 1)

    return {"count": count}

# Invoke with config
config = {"configurable": {"thread_id": "thread-1"}}
result = workflow.invoke({"increment": 5}, config=config)
print(result)  # {"count": 5}

# Second invocation on same thread
result = workflow.invoke({"increment": 3}, config=config)
print(result)  # {"count": 8} - remembers previous!
```

### With Checkpointing
```python
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()

@entrypoint(checkpointer=checkpointer)
def chat_workflow(inputs: dict, *, previous: dict = None) -> dict:
    messages = previous.get("messages", []) if previous else []
    messages.append(inputs["message"])

    response = {"response": f"Received: {inputs['message']}"}

    # Save messages for next invocation, but return just response
    return entrypoint.final(
        value=response,
        save={"messages": messages}
    )
```

---

## @task Decorator

### Purpose
- Represents discrete unit of work (API call, data processing, etc.)
- Enables asynchronous execution
- Supports checkpointing of results
- Can only be called within entrypoint, another task, or StateGraph node

### Signature
```python
@task(
    name=None,           # Optional task name
    retry_policy=None,   # Optional retry strategy
    cache_policy=None    # Optional result caching
)
def my_task(arg1, arg2):
    return result
```

### Requirements
- Python 3.11+ for async functions
- Serializable inputs/outputs when using checkpointing

### Sync Task Example
```python
from langgraph.func import task, entrypoint

@task
def add_one(a: int) -> int:
    return a + 1

@entrypoint()
def process_numbers(numbers: list[int]) -> list[int]:
    # Create futures for parallel execution
    futures = [add_one(n) for n in numbers]
    # Wait for results
    results = [f.result() for f in futures]
    return results

result = process_numbers.invoke([1, 2, 3])
print(result)  # [2, 3, 4]
```

### Async Task Example
```python
import asyncio
from langgraph.func import task, entrypoint

@task
async def fetch_data(url: str) -> dict:
    # Simulate API call
    await asyncio.sleep(0.1)
    return {"url": url, "data": "..."}

@entrypoint()
async def fetch_all(urls: list[str]) -> list[dict]:
    futures = [fetch_data(url) for url in urls]
    # Gather all results
    return await asyncio.gather(*[f for f in futures])

# Run async workflow
result = asyncio.run(fetch_all.ainvoke(["url1", "url2"]))
```

---

## entrypoint.final()

### Purpose
Decouples **return value** from **checkpoint save value**.

### Signature
```python
entrypoint.final(value=..., save=...)
```

- `value`: What to return to caller
- `save`: What to save in checkpoint for next invocation

### Example
```python
@entrypoint(checkpointer=InMemorySaver())
def workflow(inputs: dict, *, previous: dict = None) -> dict:
    # Process input
    result = {"output": "processed"}

    # Return result to caller, but save full state
    return entrypoint.final(
        value=result,
        save={
            "history": previous.get("history", []) + [inputs],
            "metadata": {"last_run": "2025-01-01"}
        }
    )
```

---

## Checkpointing

### Setup
```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver

# In-memory (testing)
checkpointer = InMemorySaver()

# PostgreSQL (production)
checkpointer = PostgresSaver(connection_string)
```

### Configuration
```python
config = {
    "configurable": {
        "thread_id": "user-123",      # Required: unique conversation ID
        "checkpoint_id": "...",         # Optional: specific checkpoint
    }
}

result = workflow.invoke(inputs, config=config)
```

### Thread-Level Persistence
Each `thread_id` maintains independent state:

```python
# Thread 1
config1 = {"configurable": {"thread_id": "user-1"}}
workflow.invoke({"msg": "Hi"}, config1)

# Thread 2
config2 = {"configurable": {"thread_id": "user-2"}}
workflow.invoke({"msg": "Hello"}, config2)

# Threads are isolated
```

---

## Invocation Methods

### Synchronous
```python
# Single invocation
result = workflow.invoke(inputs, config=config)

# Streaming
for chunk in workflow.stream(inputs, config=config):
    print(chunk)
```

### Asynchronous
```python
# Single invocation
result = await workflow.ainvoke(inputs, config=config)

# Streaming
async for chunk in workflow.astream(inputs, config=config):
    print(chunk)
```

---

## Complete Example: Chat with Memory

```python
from langgraph.func import entrypoint, task
from langgraph.checkpoint.memory import InMemorySaver
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages

# Initialize model
model = ChatAnthropic(model="claude-3-5-sonnet-latest")

# Define task for LLM call
@task
async def call_model(messages: list[BaseMessage]) -> BaseMessage:
    response = await model.ainvoke(messages)
    return response

# Create checkpointer
checkpointer = InMemorySaver()

# Define workflow with persistence
@entrypoint(checkpointer=checkpointer)
async def chat_workflow(
    inputs: list[BaseMessage],
    *,
    previous: list[BaseMessage] = None
) -> BaseMessage:
    # Merge with previous messages
    if previous:
        inputs = add_messages(previous, inputs)

    # Get response
    response = await call_model(inputs)

    # Return response, save full history
    return entrypoint.final(
        value=response,
        save=add_messages(inputs, response)
    )

# Usage
config = {"configurable": {"thread_id": "conversation-1"}}

# First message
msg1 = [{"role": "user", "content": "Hi, I'm Alice"}]
result1 = await chat_workflow.ainvoke(msg1, config=config)

# Second message - remembers Alice!
msg2 = [{"role": "user", "content": "What's my name?"}]
result2 = await chat_workflow.ainvoke(msg2, config=config)
# Response: "Your name is Alice"
```

---

## Best Practices

### 1. Encapsulate Side Effects in Tasks
```python
@task
async def save_to_db(data: dict) -> bool:
    # Side effects in tasks
    await db.insert(data)
    return True

@entrypoint()
async def workflow(inputs: dict) -> dict:
    # Pure logic in entrypoint
    result = process(inputs)
    saved = await save_to_db(result)
    return {"saved": saved}
```

### 2. Make Tasks Idempotent
```python
@task
def fetch_data(url: str, cache_key: str) -> dict:
    # Check cache first
    if cached := cache.get(cache_key):
        return cached

    # Fetch and cache
    data = requests.get(url).json()
    cache.set(cache_key, data)
    return data
```

### 3. Use JSON-Serializable Types
```python
# Good
@entrypoint()
def workflow(inputs: dict) -> dict:
    return {"result": 42}

# Bad - objects not serializable
@entrypoint()
def workflow(inputs: CustomObject) -> CustomObject:
    return CustomObject()  # Won't work with checkpointing
```

### 4. Handle Previous State Safely
```python
@entrypoint(checkpointer=checkpointer)
def workflow(inputs: dict, *, previous: dict = None) -> dict:
    # Safe access with defaults
    count = previous.get("count", 0) if previous else 0
    history = previous.get("history", []) if previous else []

    # Process
    count += 1
    history.append(inputs)

    return entrypoint.final(
        value={"count": count},
        save={"count": count, "history": history}
    )
```

---

## Common Patterns

### Pattern 1: Stateless Workflow
```python
@entrypoint()
def stateless_workflow(inputs: dict) -> dict:
    # No checkpointer, no state
    return {"processed": inputs["data"]}
```

### Pattern 2: Stateful Workflow
```python
@entrypoint(checkpointer=checkpointer)
def stateful_workflow(inputs: dict, *, previous: dict = None) -> dict:
    # Accumulate state across invocations
    state = previous or {"items": []}
    state["items"].append(inputs["item"])
    return entrypoint.final(value=state, save=state)
```

### Pattern 3: Human-in-the-Loop
```python
from langgraph.types import interrupt

@entrypoint(checkpointer=checkpointer)
def approval_workflow(inputs: dict, *, previous: dict = None) -> dict:
    if not previous:
        # First run: generate content
        content = generate_content(inputs)
        is_approved = interrupt({"content": content, "action": "approve"})
    else:
        # Resumed: check approval
        is_approved = previous.get("is_approved")

    if is_approved:
        return {"status": "approved"}
    else:
        return {"status": "rejected"}
```

### Pattern 4: Parallel Task Execution
```python
@task
async def process_item(item: dict) -> dict:
    # Process single item
    return {"processed": item}

@entrypoint()
async def batch_process(items: list[dict]) -> list[dict]:
    # Create futures for all items
    futures = [process_item(item) for item in items]
    # Wait for all to complete
    return await asyncio.gather(*futures)
```

---

## Error Handling

```python
@task
async def risky_operation(data: dict) -> dict:
    try:
        result = await external_api(data)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

@entrypoint(checkpointer=checkpointer)
async def workflow(inputs: dict, *, previous: dict = None) -> dict:
    result = await risky_operation(inputs)

    if result["success"]:
        return entrypoint.final(
            value=result["data"],
            save={"last_success": result["data"]}
        )
    else:
        # Don't save failed state
        return {"error": result["error"]}
```

---

## Migration from Regular Functions

### Before (Regular Function)
```python
async def process_message(message: str, history: list) -> dict:
    history.append({"role": "user", "content": message})
    response = await llm.invoke(history)
    history.append({"role": "assistant", "content": response})
    return {"response": response, "history": history}
```

### After (LangGraph Functional API)
```python
@entrypoint(checkpointer=checkpointer)
async def process_message(
    inputs: dict,
    *,
    previous: dict = None
) -> dict:
    history = previous.get("history", []) if previous else []
    history.append({"role": "user", "content": inputs["message"]})

    response = await llm.invoke(history)
    history.append({"role": "assistant", "content": response})

    return entrypoint.final(
        value={"response": response},
        save={"history": history}
    )

# Invoke with thread_id
config = {"configurable": {"thread_id": "user-1"}}
result = await process_message.ainvoke({"message": "Hello"}, config=config)
```

---

## Deprecation Notice

⚠️ **Note:** These docs will be deprecated with LangGraph v1.0 release (October 2025).

---

## References

- **Concepts:** https://langchain-ai.github.io/langgraph/concepts/functional_api/
- **How-to Guide:** https://langchain-ai.github.io/langgraph/how-tos/use-functional-api/
- **API Reference:** https://langchain-ai.github.io/langgraph/reference/func/
- **Persistence Guide:** https://langchain-ai.github.io/langgraph/how-tos/persistence-functional/
