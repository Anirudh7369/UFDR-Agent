# Vector Search - Quick Start Guide

## 🚀 Quick Setup (5 minutes)

### 1. Install Dependencies
```bash
pip install qdrant-client sentence-transformers
```

### 2. Start Qdrant Server
```bash
# Using the setup script (recommended)
./scripts/setup_qdrant.sh

# OR manually with Docker
docker run -p 6333:6333 qdrant/qdrant
```

### 3. Test Installation
```bash
python examples/vector_search_example.py
```

## 📝 Basic Usage

### Using the Tool (for Agents)

```python
from realtime.tools.vector_search import vector_search

# Semantic search
result = await vector_search(
    query="Tell me about crypto trading messages",
    collection="messages",
    limit=5,
    score_threshold=0.7
)
print(result)
```

### Using Utilities (for Developers)

```python
from realtime.utils.vector import (
    generate_text_embedding,
    create_collection,
    insert_vector,
    search_vectors
)

# 1. Create a collection
create_collection("messages", vector_size=384)

# 2. Generate embedding
embedding = generate_text_embedding("Hello crypto traders")

# 3. Insert into Qdrant
payload = {"body": "Hello crypto traders", "from": "John"}
insert_vector("messages", "msg_1", embedding, payload)

# 4. Search
query_emb = generate_text_embedding("crypto trading")
results = search_vectors("messages", query_emb, limit=5)
```

## 🔍 Common Use Cases

### Use Case 1: Populate from Database

```python
from realtime.utils.vector import generate_batch_embeddings, insert_batch_vectors
from realtime.utils.db.connection import get_db_connection

async def populate_messages():
    # Fetch messages
    async with get_db_connection() as conn:
        rows = await conn.fetch("SELECT * FROM messages WHERE body IS NOT NULL LIMIT 1000")

    # Generate embeddings
    bodies = [row['body'] for row in rows]
    embeddings = generate_batch_embeddings(bodies)

    # Prepare vectors
    vectors = [
        (f"msg_{row['id']}", emb, dict(row))
        for row, emb in zip(rows, embeddings)
    ]

    # Insert batch
    insert_batch_vectors("messages", vectors)
```

### Use Case 2: Agent Query

```python
# Agent automatically uses vector_search when semantics matter
user_query = "Tell me about crypto trading"
# Agent will call vector_search tool internally
```

### Use Case 3: Custom Search with Filters

```python
from qdrant_client.models import Filter, FieldCondition, MatchValue

results = client.search(
    collection_name="messages",
    query_vector=query_embedding,
    query_filter=Filter(
        must=[
            FieldCondition(key="source_app", match=MatchValue(value="WhatsApp"))
        ]
    ),
    limit=5
)
```

## ⚙️ Configuration

### Environment Variables (.env)

```env
# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=  # Optional

# Embedding Model
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

### Model Selection

| Model | Dimensions | Speed | Use Case |
|-------|-----------|-------|----------|
| `all-MiniLM-L6-v2` | 384 | Fast | General search |
| `all-mpnet-base-v2` | 768 | Medium | Better accuracy |
| `text-embedding-ada-002` | 1536 | API call | Best quality |

## 🎯 When to Use What

| Scenario | Use This |
|----------|----------|
| Find messages with exact app name | `query_messages` tool |
| Find messages about a topic | `vector_search` tool |
| Get all WhatsApp contacts | `query_contacts` tool |
| Find business-related contacts | `vector_search` tool |
| Messages from specific person | `query_messages` tool |
| Messages about crypto/trading | `vector_search` tool |

## 📊 Performance Tips

### Batch Processing (Faster)
```python
# ✓ Good - 100x faster
embeddings = generate_batch_embeddings(texts)

# ✗ Slow
embeddings = [generate_text_embedding(text) for text in texts]
```

### Score Thresholds

```python
# High precision (strict)
vector_search(query, score_threshold=0.8)

# Balanced (recommended)
vector_search(query, score_threshold=0.7)

# High recall (loose)
vector_search(query, score_threshold=0.5)
```

### Minimize Payload Size

```python
# ✓ Good - only essentials
payload = {
    'body': message['body'],
    'from': message['from_party_name'],
    'timestamp': message['timestamp']
}

# ✗ Bad - full database row
payload = dict(message)  # 50+ fields
```

## 🛠️ Troubleshooting

### Error: "qdrant-client is not installed"
```bash
pip install qdrant-client
```

### Error: "Connection refused to localhost:6333"
```bash
# Start Qdrant
docker run -p 6333:6333 qdrant/qdrant
```

### Error: "Collection not found"
```python
from realtime.utils.vector import create_collection
create_collection("messages", vector_size=384)
```

### Error: "Dimension mismatch"
- Ensure collection vector_size matches model output
- `all-MiniLM-L6-v2` = 384 dimensions
- `all-mpnet-base-v2` = 768 dimensions

## 🔗 Useful Commands

```bash
# Check Qdrant status
curl http://localhost:6333/collections

# View Qdrant dashboard
open http://localhost:6333/dashboard

# Stop Qdrant
docker stop qdrant

# Start Qdrant
docker start qdrant

# View logs
docker logs qdrant

# Remove Qdrant
docker rm -f qdrant
```

## 📚 Full Documentation

- **Complete Guide**: `VECTOR_SEARCH_GUIDE.md`
- **Implementation Details**: `IMPLEMENTATION_SUMMARY.md`
- **Examples**: `examples/vector_search_example.py`
- **Tool Code**: `realtime/tools/vector_search.py`
- **Utilities**: `realtime/utils/vector/embeddings.py`

## 💡 Example Queries

### Semantic Search (Vector Search)
- "Tell me about crypto trading"
- "Find suspicious messages"
- "Messages about meeting locations"
- "Contacts related to business"
- "Images with people"

### Exact Search (Traditional Query)
- "Get all WhatsApp messages"
- "Show messages from John Doe"
- "List deleted contacts"
- "Find messages with attachments"
- "Get calls on 2023-06-15"

## 🎓 Learning Path

1. **Read**: `VECTOR_SEARCH_QUICK_START.md` (this file)
2. **Run**: `python examples/vector_search_example.py`
3. **Study**: `VECTOR_SEARCH_GUIDE.md`
4. **Experiment**: Modify examples
5. **Integrate**: Add to your workflow

## 📞 Support

- **Issues**: Check `VECTOR_SEARCH_GUIDE.md` troubleshooting section
- **Examples**: See `examples/vector_search_example.py`
- **API Reference**: See `VECTOR_SEARCH_GUIDE.md`

---

**Ready to start?** Run: `./scripts/setup_qdrant.sh && python examples/vector_search_example.py`
