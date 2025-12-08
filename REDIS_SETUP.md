# Redis Session Cache Setup Guide

This guide explains how to set up and use the Redis-based session cache for the UFDR-Analyst backend.

## Overview

The Redis session cache provides:
- Fast access to recent conversation history for LLM context
- Automatic message trimming (keeps last 30 messages per session)
- Automatic expiration (7-day TTL, refreshed on each message)
- Graceful degradation when Redis is unavailable

## Architecture

### Storage Pattern

**Redis Key:** `session:{session_id}:messages`
**Data Structure:** Redis LIST
**Element Format:** JSON-encoded message objects

**Message Schema:**
```json
{
  "role": "user" | "assistant" | "system",
  "content": "message text",
  "timestamp": "2024-01-15T10:30:00Z",
  "metadata": {
    "email_id": "user@example.com"
  }
}
```

### Components

1. **redis_client.py** - Singleton Redis client with graceful error handling
2. **chat_session.py** - SessionCache interface for managing conversations
3. **analytics/routes.py** - Integration with API endpoints

## Setup

### 1. Install Redis

**Using Docker (Recommended):**
```bash
docker run -d --name ufdr-redis -p 6379:6379 redis:7-alpine
```

**Using Docker Compose:**
```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data

volumes:
  redis-data:
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

This will install `redis>=5.0.0` along with other dependencies.

### 3. Configure Environment Variables

Add to your `.env` file:

```env
# Option 1: Use full URL (recommended)
REDIS_URL=redis://localhost:6379/0

# Option 2: Or use individual components
# REDIS_HOST=localhost
# REDIS_PORT=6379
# REDIS_DB=0
```

### 4. Start the Application

```bash
cd UFDR-Agent
python -m uvicorn realtime.main:app --reload
```

The app will automatically connect to Redis if available. If Redis is not available, the app will continue to run without session caching.

## Usage

### API Integration

The session cache is automatically integrated into the `/api/analytics` endpoint:

1. **User sends query** → Cached in Redis
2. **Agent processes query** → Can access conversation history
3. **Agent responds** → Response cached in Redis

**Example Request:**
```bash
curl -X POST http://localhost:8000/api/analytics \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is a UFDR report?",
    "session_id": "session-abc-123",
    "email_id": "investigator@example.com",
    "current_timestamp": "2024-01-15T10:30:00Z"
  }'
```

### Debug Endpoints

#### Inspect Session Cache

```bash
GET /api/session/{session_id}/debug
```

**Example:**
```bash
curl http://localhost:8000/api/session/session-abc-123/debug
```

**Response:**
```json
{
  "session_id": "session-abc-123",
  "exists": true,
  "message_count": 6,
  "messages": [
    {
      "role": "user",
      "content": "What is a UFDR report?",
      "timestamp": "2024-01-15T10:30:00Z",
      "metadata": {"email_id": "investigator@example.com"}
    },
    {
      "role": "assistant",
      "content": "A UFDR report is...",
      "timestamp": "2024-01-15T10:30:05Z"
    }
  ],
  "redis_available": true
}
```

#### Clear Session

```bash
DELETE /api/session/{session_id}
```

**Example:**
```bash
curl -X DELETE http://localhost:8000/api/session/session-abc-123
```

### Programmatic Usage

```python
from utils.chat_session import SessionCache

# Append a message
await SessionCache.append_message(
    session_id="session-123",
    role="user",
    content="What is UFDR?",
    metadata={"email_id": "user@example.com"}
)

# Retrieve recent messages
messages = await SessionCache.get_messages(
    session_id="session-123",
    limit=10  # Get last 10 messages
)

# Check if session exists
exists = await SessionCache.session_exists("session-123")

# Get message count
count = await SessionCache.get_session_message_count("session-123")

# Clear session
await SessionCache.clear_session("session-123")
```

## Configuration

### Message Retention

Edit `UFDR-Agent/realtime/utils/chat_session.py`:

```python
DEFAULT_MESSAGE_LIMIT = 30  # Number of messages to keep per session
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days
```

### Connection Timeouts

Edit `UFDR-Agent/realtime/utils/ai/redis_client.py`:

```python
socket_connect_timeout=5,  # Connection timeout in seconds
socket_timeout=5,          # Operation timeout in seconds
```

## Monitoring

### Check Redis Connection

```bash
# Using Redis CLI
redis-cli ping
# Should return: PONG

# Check keys
redis-cli keys "session:*"

# View session data
redis-cli LRANGE session:session-abc-123:messages 0 -1
```

### Application Logs

The application logs Redis connection status:

```
INFO - Redis client initialized successfully: redis://localhost:6379/0
```

If Redis is unavailable:
```
WARNING - Failed to connect to Redis: [Errno 111] Connection refused. Session cache will be disabled.
```

## Security & Data Minimization

**IMPORTANT:** The Redis cache only stores:
- Chat dialogue (user queries and agent responses)
- Lightweight metadata (email_id, session_id)

**Do NOT store:**
- Raw UFDR evidence blobs
- Media files
- Full database records
- Sensitive investigative data

The "source of truth" for all evidence remains in your primary database (e.g., Postgres).

## Troubleshooting

### Redis Not Connecting

1. **Check Redis is running:**
   ```bash
   docker ps | grep redis
   ```

2. **Test connection:**
   ```bash
   redis-cli -h localhost -p 6379 ping
   ```

3. **Check environment variables:**
   ```bash
   echo $REDIS_URL
   ```

4. **Check application logs** for connection errors

### App Works Without Redis

This is expected behavior! The app gracefully degrades:
- All endpoints continue to work
- Session history is not cached
- No errors are thrown

To verify Redis is being used:
- Check logs for "Redis client initialized successfully"
- Use the debug endpoint to inspect cached messages

### Messages Not Being Cached

1. **Verify session_id is provided** in API requests
2. **Check Redis logs:**
   ```bash
   docker logs ufdr-redis
   ```
3. **Use debug endpoint** to verify messages are being stored

## Production Considerations

### Redis Persistence

Configure Redis to persist data to disk:

```bash
docker run -d \
  --name ufdr-redis \
  -p 6379:6379 \
  -v redis-data:/data \
  redis:7-alpine redis-server --appendonly yes
```

### Redis Password

Add password protection:

```bash
docker run -d \
  --name ufdr-redis \
  -p 6379:6379 \
  redis:7-alpine redis-server --requirepass yourpassword
```

Update `.env`:
```env
REDIS_URL=redis://:yourpassword@localhost:6379/0
```

### High Availability

For production, consider:
- Redis Sentinel for automatic failover
- Redis Cluster for horizontal scaling
- Regular backups of Redis data

## Future Enhancements

Potential improvements to the session cache:

1. **Context-Aware Agent:**
   - Pass cached conversation history to LLM for better context
   - Implement conversation summarization for long sessions

2. **Advanced Caching:**
   - Cache frequently accessed UFDR metadata (not raw evidence)
   - Implement cache warming strategies

3. **Analytics:**
   - Track session duration and message counts
   - Monitor cache hit/miss rates

4. **Multi-User Sessions:**
   - Add user-specific context within sessions
   - Implement session sharing for collaborative investigations

## Support

For issues or questions:
1. Check application logs for errors
2. Use debug endpoint to inspect cache state
3. Verify Redis connection with `redis-cli`
4. Review this documentation

---

**Last Updated:** 2024-12-08
**Version:** 1.0.0
