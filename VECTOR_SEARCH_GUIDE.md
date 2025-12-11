# Vector Search Tool Guide

## Overview

The vector search tool enables semantic search across forensic data using embeddings and Qdrant vector database. Unlike traditional database queries that rely on exact matches, vector search finds data based on **meaning and context**.

## Features

- **Semantic Search**: Find relevant data based on meaning, not just keywords
- **Multi-Modal Support**: Search text, images, and other data types
- **Flexible Collections**: Search across messages, contacts, locations, images, etc.
- **Score Filtering**: Control result relevance with similarity thresholds
- **Batch Processing**: Efficiently process multiple queries

## Installation

### Required Libraries

```bash
pip install qdrant-client sentence-transformers
```

### Qdrant Server

You can run Qdrant using Docker:

```bash
docker run -p 6333:6333 qdrant/qdrant
```

Or install locally: https://qdrant.tech/documentation/quick-start/

### Environment Variables

Create a `.env` file in your project root:

```env
# Qdrant Configuration
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=  # Optional, for Qdrant Cloud

# Embedding Model
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

## Architecture

### Components

1. **Vector Search Tool** (`realtime/tools/vector_search.py`)
   - Agent-facing tool for semantic search
   - Converts queries to embeddings
   - Returns formatted results

2. **Embedding Utilities** (`realtime/utils/vector/embeddings.py`)
   - Generate embeddings from text
   - Manage Qdrant client
   - CRUD operations for vectors

3. **Forensic Agent Integration** (`realtime/utils/ai/agent.py`)
   - Vector search tool registered with agent
   - Available alongside other forensic tools

## Usage

### 1. Using the Vector Search Tool (for Agents)

The forensic agent can use the `vector_search` tool:

```python
# The agent will automatically call this tool when appropriate
user_query = "Tell me about messages regarding crypto trading"

# Tool parameters:
# - query: Natural language search query
# - collection: Qdrant collection name (default: "messages")
# - limit: Max results (default: 5, max: 20)
# - score_threshold: Minimum similarity score (0-1)

result = await vector_search(
    query="crypto trading messages",
    collection="messages",
    limit=5,
    score_threshold=0.7
)
```

### 2. Using Embedding Utilities (for Developers)

#### Generate Embeddings

```python
from realtime.utils.vector import generate_text_embedding, generate_batch_embeddings

# Single text
embedding = generate_text_embedding("Tell me about crypto trading")
print(f"Embedding dimension: {len(embedding)}")  # 384 for all-MiniLM-L6-v2

# Batch processing
texts = ["Message 1", "Message 2", "Message 3"]
embeddings = generate_batch_embeddings(texts)
```

#### Create and Manage Collections

```python
from realtime.utils.vector import (
    create_collection,
    insert_vector,
    insert_batch_vectors,
    search_vectors,
    list_collections,
    delete_collection
)

# Create a collection
create_collection("messages", vector_size=384, distance="Cosine")

# Insert a single vector
embedding = generate_text_embedding("Hello, world!")
payload = {
    "body": "Hello, world!",
    "from_party_name": "John",
    "source_app": "WhatsApp",
    "message_timestamp_dt": "2023-06-15T14:30:00"
}
insert_vector("messages", "msg_123", embedding, payload)

# Insert batch vectors
vectors = [
    ("msg_1", embedding1, payload1),
    ("msg_2", embedding2, payload2),
    ("msg_3", embedding3, payload3),
]
insert_batch_vectors("messages", vectors)

# Search vectors
query_embedding = generate_text_embedding("crypto trading")
results = search_vectors(
    collection_name="messages",
    query_vector=query_embedding,
    limit=5,
    score_threshold=0.7
)

# List all collections
collections = list_collections()
print(collections)  # ['messages', 'images', 'contacts']

# Delete a collection
delete_collection("old_messages")
```

#### Search and Retrieve

```python
# Search with custom parameters
query_embedding = generate_text_embedding("suspicious activity")
results = search_vectors(
    collection_name="messages",
    query_vector=query_embedding,
    limit=10,
    score_threshold=0.8  # Only highly relevant results
)

for result in results:
    print(f"Score: {result['score']:.3f}")
    print(f"Message: {result['payload']['body']}")
    print(f"From: {result['payload']['from_party_name']}")
```

## Example Workflow

### Populating the Vector Database

```python
import asyncio
from realtime.utils.vector import (
    create_collection,
    generate_text_embedding,
    insert_vector
)
from realtime.utils.db.connection import get_db_connection

async def populate_messages_collection():
    """Populate messages collection with embeddings from database."""

    # Create collection
    create_collection("messages", vector_size=384)

    # Fetch messages from PostgreSQL
    async with get_db_connection() as conn:
        rows = await conn.fetch("""
            SELECT
                id,
                body,
                from_party_name,
                to_party_name,
                source_app,
                message_timestamp_dt
            FROM messages
            WHERE body IS NOT NULL
            LIMIT 10000
        """)

    # Generate embeddings and insert
    for row in rows:
        # Generate embedding from message body
        embedding = generate_text_embedding(row['body'])

        # Prepare payload
        payload = {
            'body': row['body'],
            'from_party_name': row['from_party_name'],
            'to_party_name': row['to_party_name'],
            'source_app': row['source_app'],
            'message_timestamp_dt': row['message_timestamp_dt'].isoformat()
        }

        # Insert into Qdrant
        insert_vector(
            collection_name="messages",
            vector_id=f"msg_{row['id']}",
            vector=embedding,
            payload=payload
        )

    print(f"Populated {len(rows)} messages")

# Run the population script
asyncio.run(populate_messages_collection())
```

### Performing Semantic Search

```python
from realtime.tools.vector_search import vector_search

# The agent or API can now perform semantic searches
result = await vector_search(
    query="Tell me about messages regarding crypto trading",
    collection="messages",
    limit=5,
    score_threshold=0.7
)

print(result)
```

## Comparison: Vector Search vs Traditional Query

### Traditional Query (Exact Match)
```python
# Only finds messages with exact words "crypto" or "trading"
await query_messages("body:crypto")
```

### Vector Search (Semantic)
```python
# Finds messages about cryptocurrencies, bitcoin, trading strategies, etc.
# Even if they don't contain exact words "crypto" or "trading"
await vector_search("crypto trading", collection="messages")
```

**Example Results:**

Traditional query finds:
- "Let's discuss crypto trading"
- "Crypto prices are rising"

Vector search finds:
- "Let's discuss crypto trading" ✓
- "Crypto prices are rising" ✓
- "Bitcoin investment strategies" ✓ (semantic match!)
- "Should we buy more ETH?" ✓ (semantic match!)
- "The cryptocurrency market is volatile" ✓ (semantic match!)

## Collections

Recommended collections for forensic data:

| Collection | Description | Embedding Source |
|------------|-------------|------------------|
| `messages` | Message bodies | `body` field |
| `images` | Image descriptions | OCR text or image captions |
| `locations` | Location contexts | Combined address/place info |
| `contacts` | Contact information | Name + notes |
| `browsing` | Browser history | URL + page title |

## Performance Considerations

### Embedding Generation
- **Single text**: ~10-50ms
- **Batch (100 texts)**: ~100-500ms
- **Recommendation**: Use batch processing for bulk operations

### Vector Search
- **Search time**: ~1-10ms for collections up to 1M vectors
- **Indexing**: HNSW algorithm for fast approximate search
- **Memory**: ~4KB per vector (for 384-dimensional embeddings)

## Best Practices

### 1. Choose Appropriate Score Thresholds

```python
# Strict matching (high precision)
vector_search(query, score_threshold=0.8)

# Balanced (recommended)
vector_search(query, score_threshold=0.7)

# Loose matching (high recall)
vector_search(query, score_threshold=0.5)

# No threshold (all results)
vector_search(query, score_threshold=None)
```

### 2. Optimize Payload Size

Store only necessary fields in payload:

```python
# ✓ Good - minimal payload
payload = {
    'body': message['body'],
    'from': message['from_party_name'],
    'timestamp': message['timestamp']
}

# ✗ Bad - storing entire database row
payload = dict(message)  # Contains 50+ fields
```

### 3. Use Batch Operations

```python
# ✓ Good - batch insert
embeddings = generate_batch_embeddings([msg['body'] for msg in messages])
vectors = [(f"msg_{i}", emb, payload) for i, (emb, payload) in enumerate(zip(embeddings, payloads))]
insert_batch_vectors("messages", vectors)

# ✗ Bad - individual inserts
for msg in messages:
    embedding = generate_text_embedding(msg['body'])
    insert_vector("messages", msg['id'], embedding, payload)
```

### 4. Regular Maintenance

```python
# Periodically update embeddings for modified data
# Delete vectors for deleted messages
# Recreate collections if embedding model changes
```

## Troubleshooting

### Issue: "qdrant-client is not installed"

```bash
pip install qdrant-client
```

### Issue: "sentence-transformers is not installed"

```bash
pip install sentence-transformers
```

### Issue: "Connection refused to localhost:6333"

Start Qdrant server:
```bash
docker run -p 6333:6333 qdrant/qdrant
```

### Issue: "Collection not found"

Create the collection first:
```python
from realtime.utils.vector import create_collection
create_collection("messages", vector_size=384)
```

### Issue: "Dimension mismatch"

Ensure vector size matches model output:
- `all-MiniLM-L6-v2`: 384 dimensions
- `all-mpnet-base-v2`: 768 dimensions
- `text-embedding-ada-002` (OpenAI): 1536 dimensions

## Advanced Usage

### Custom Embedding Models

Update `.env`:
```env
EMBEDDING_MODEL=sentence-transformers/all-mpnet-base-v2
```

Then update collection vector size:
```python
create_collection("messages", vector_size=768)  # mpnet uses 768 dimensions
```

### Multi-Modal Search (Images + Text)

```python
# For image search, use CLIP or similar multi-modal models
from transformers import CLIPProcessor, CLIPModel

# Generate image embeddings
# Store in "images" collection
# Search using text queries
```

### Filtering with Metadata

```python
# Qdrant supports filtering by payload
from qdrant_client.models import Filter, FieldCondition, MatchValue

results = client.search(
    collection_name="messages",
    query_vector=query_embedding,
    query_filter=Filter(
        must=[
            FieldCondition(
                key="source_app",
                match=MatchValue(value="WhatsApp")
            )
        ]
    ),
    limit=5
)
```

## Examples

See `examples/vector_search_example.py` for complete working examples.

## API Reference

### vector_search(query, collection, limit, score_threshold)

Perform semantic search on Qdrant database.

**Parameters:**
- `query` (str): Natural language search query
- `collection` (str): Collection name (default: "messages")
- `limit` (int): Max results (default: 5, max: 20)
- `score_threshold` (float, optional): Minimum similarity score (0-1)

**Returns:**
- `str`: Formatted search results with scores and metadata

### generate_text_embedding(text)

Convert text to embedding vector.

**Parameters:**
- `text` (str): Text to embed

**Returns:**
- `List[float]`: Embedding vector (384 dimensions by default)

### create_collection(collection_name, vector_size, distance)

Create a new Qdrant collection.

**Parameters:**
- `collection_name` (str): Name of collection
- `vector_size` (int): Vector dimension (default: 384)
- `distance` (str): Distance metric ("Cosine", "Euclid", "Dot")

**Returns:**
- `bool`: Success status

## License

Part of UFDR-Agent forensic analysis system.
