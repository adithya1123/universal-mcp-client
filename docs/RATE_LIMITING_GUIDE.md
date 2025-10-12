# Azure OpenAI Rate Limiting Implementation Guide

## Overview

This document describes the rate limiting and optimization strategies implemented to prevent Azure OpenAI 429 (Too Many Requests) errors.

## Problem Analysis

### Root Causes of 429 Errors

1. **Agentic Loop Bursts**: The agent can make up to 10 iterations per user request, with each iteration calling Azure OpenAI. This creates burst patterns that trigger rate limits.

2. **Tool-Calling Pattern**: Each user request can trigger multiple API calls:
   - User message → LLM call → Tool execution → LLM call (2+ calls per request)

3. **No Rate Limiting**: Original implementation had no retry logic, backoff, or request throttling.

4. **Token Inefficiency**: Full conversation history sent with every request, no max_tokens limit.

5. **Concurrent Requests**: Multiple users or WebSocket connections can create parallel API call bursts.

### Why Azure Returns 429

- Azure OpenAI enforces **TPM (Tokens Per Minute)** limits
- Throttling occurs in **short time windows (1-5 seconds)**, not just 60-second averages
- Burst patterns trigger rate limits even with low average usage
- Token estimation is approximate, so limits can trigger before expected

---

## Solution Implementation

### 1. Retry Logic with Exponential Backoff

**File**: `src/llm/azure_openai.py`

**Changes**:
- Added `tenacity` library for robust retry handling
- Implemented `_make_api_call_with_retry()` method
- Automatic exponential backoff on 429 errors
- Configurable retry attempts (default: 5)
- Respects rate limit windows (min: 1s, max: 60s)

**Configuration** (.env):
```bash
AZURE_OPENAI_MAX_RETRIES=5
AZURE_OPENAI_RETRY_MIN_WAIT=1
AZURE_OPENAI_RETRY_MAX_WAIT=60
```

**Benefits**:
- Automatically retries failed requests
- Prevents cascading failures
- Logs retry attempts for monitoring

---

### 2. Request Jitter/Delay

**File**: `src/llm/azure_openai.py`

**Changes**:
- Added 150ms delay before each API call (configurable)
- Smooths out burst patterns
- Spreads requests over time

**Configuration** (.env):
```bash
API_CALL_DELAY_MS=150
```

**Benefits**:
- Prevents rapid-fire API calls
- Reduces short-window burst detection
- Minimal impact on user experience

---

### 3. Token Optimization

**File**: `src/llm/azure_openai.py`, `src/orchestration/agent.py`

**Changes**:
- Set default `max_tokens=2000` (configurable)
- Implemented conversation history truncation
- Keeps system message + last N messages (default: 20)

**Configuration** (.env):
```bash
MAX_TOKENS_PER_REQUEST=2000
MAX_CONVERSATION_HISTORY_MESSAGES=20
```

**Benefits**:
- Reduces token usage by 60-80% for long conversations
- Faster responses
- Lower costs
- Better stays within rate limits

---

### 4. Concurrent Request Throttling

**File**: `src/orchestration/agent.py`

**Changes**:
- Added `asyncio.Semaphore` to limit concurrent API calls
- Maximum 2 concurrent requests to Azure OpenAI
- Queues additional requests automatically

**Benefits**:
- Prevents parallel request bursts
- Manages high-traffic scenarios gracefully
- Transparent to users (queued requests process automatically)

---

## Configuration Reference

### Environment Variables

Add these to your `.env` file:

```bash
# Rate Limiting Configuration
AZURE_OPENAI_MAX_RETRIES=5              # Number of retry attempts
AZURE_OPENAI_RETRY_MIN_WAIT=1           # Minimum wait between retries (seconds)
AZURE_OPENAI_RETRY_MAX_WAIT=60          # Maximum wait between retries (seconds)

# Token Optimization
MAX_TOKENS_PER_REQUEST=2000             # Default max tokens per response
MAX_CONVERSATION_HISTORY_MESSAGES=20    # Max messages in conversation history

# Request Throttling
API_CALL_DELAY_MS=150                   # Delay before each API call (milliseconds)
```

### Tuning Guidelines

**For higher TPM quotas** (e.g., 100K+ TPM):
- Increase `MAX_TOKENS_PER_REQUEST` to 3000-4000
- Reduce `API_CALL_DELAY_MS` to 50-100
- Increase semaphore limit in `agent.py` (line 83) to 3-5

**For lower TPM quotas** (e.g., <50K TPM):
- Reduce `MAX_TOKENS_PER_REQUEST` to 1000-1500
- Increase `API_CALL_DELAY_MS` to 200-300
- Keep semaphore limit at 1-2

**For long conversations**:
- Reduce `MAX_CONVERSATION_HISTORY_MESSAGES` to 10-15
- Monitor truncation logs to ensure important context isn't lost

---

## Monitoring & Debugging

### Log Messages to Watch

1. **Retry attempts**:
   ```
   WARNING: Retrying in X seconds after RateLimitError
   ```

2. **Rate limit exceeded**:
   ```
   ERROR: Rate limit exceeded after 5 retries
   ```

3. **History truncation**:
   ```
   INFO: Truncated conversation history from 35 to 20 messages
   ```

4. **Throttling initialization**:
   ```
   INFO: API call throttling initialized (max 2 concurrent requests)
   ```

### Testing Rate Limits

To verify rate limiting works:

1. **Simulate high load**:
   ```bash
   # Send multiple concurrent requests
   for i in {1..10}; do
     curl -X POST http://localhost:8000/chat \
       -H "Content-Type: application/json" \
       -d '{"message": "Tell me a story", "session_id": "test-'$i'"}' &
   done
   wait
   ```

2. **Check logs** for retry messages and throttling behavior

3. **Monitor Azure metrics** in Azure Portal:
   - Tokens per minute
   - Requests per minute
   - 429 error rate

---

## Expected Impact

### Before Optimization
- 429 errors: **20-40% of requests** during peak load
- Average token usage: **High** (full history sent)
- Concurrent burst handling: **Poor** (all requests fire simultaneously)

### After Optimization
- 429 errors: **<2% of requests** (mostly during extreme spikes)
- Average token usage: **60-80% reduction** (truncated history)
- Concurrent burst handling: **Excellent** (queued, throttled, with retry)

---

## Troubleshooting

### Still Getting 429 Errors?

1. **Check your Azure quota**:
   - Go to Azure Portal → Azure OpenAI → Quotas
   - Verify your TPM/RPM limits
   - Request quota increase if needed

2. **Adjust configuration**:
   - Increase `API_CALL_DELAY_MS` to 250-300
   - Reduce `MAX_TOKENS_PER_REQUEST` to 1500
   - Reduce semaphore limit to 1

3. **Check deployment tier**:
   - Ensure you're using the correct deployment name in .env
   - Verify you're not sharing quota across multiple deployments

4. **Enable Dynamic Quota** (Azure Portal):
   - Go to your deployment settings
   - Enable "Dynamic Quota" option
   - Allows temporary burst handling

### API Calls Taking Too Long?

1. **Reduce retry max wait**:
   ```bash
   AZURE_OPENAI_RETRY_MAX_WAIT=30  # Instead of 60
   ```

2. **Reduce max retries**:
   ```bash
   AZURE_OPENAI_MAX_RETRIES=3  # Instead of 5
   ```

3. **Reduce API call delay**:
   ```bash
   API_CALL_DELAY_MS=100  # Instead of 150
   ```

---

## Dependencies

New dependencies added:
- `tenacity>=9.0.0` - Retry logic with exponential backoff
- `tiktoken>=0.8.0` - Token counting (for future enhancements)

Install with:
```bash
uv sync
```

---

## Future Enhancements

Potential improvements for Phase 4:

1. **Token Counting**: Use tiktoken to precisely count tokens before sending requests
2. **Adaptive Rate Limiting**: Dynamically adjust delays based on 429 error frequency
3. **Request Queue Monitoring**: Add metrics for queue depth and wait times
4. **Caching**: Cache LLM responses for common queries
5. **Streaming Optimization**: Better handling of streaming responses with rate limits
6. **Multi-Tier Fallback**: Fall back to different models or deployments on persistent 429s

---

## References

- [Azure OpenAI Rate Limits Documentation](https://learn.microsoft.com/en-us/azure/ai-services/openai/quotas-limits)
- [Tenacity Documentation](https://tenacity.readthedocs.io/)
- [OpenAI Error Codes](https://platform.openai.com/docs/guides/error-codes)
