"""
Example script demonstrating how to use the vector search functionality.

This script shows:
1. How to generate embeddings from text/images
2. How to store vectors in Qdrant
3. How to perform semantic search
4. How to use the vector_search tool
"""

import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from realtime.utils.vector import (
    generate_text_embedding,
    generate_batch_embeddings,
    create_collection,
    insert_vector,
    insert_batch_vectors,
    search_vectors,
    list_collections
)
from realtime.tools.vector_search import vector_search


async def example_1_basic_embedding():
    """Example 1: Generate embeddings from text."""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Generate Text Embeddings")
    print("=" * 80)

    # Convert a single text to embedding
    text = "Tell me about messages regarding crypto trading"
    embedding = generate_text_embedding(text)

    print(f"Text: '{text}'")
    print(f"Embedding dimension: {len(embedding)}")
    print(f"First 5 values: {embedding[:5]}")
    print(f"Embedding type: {type(embedding)}")


async def example_2_batch_embeddings():
    """Example 2: Generate embeddings for multiple texts."""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Batch Text Embeddings")
    print("=" * 80)

    texts = [
        "Let's discuss crypto trading strategies",
        "Meeting tomorrow at 3 PM",
        "Can you send me the report?",
        "Bitcoin price is rising",
    ]

    embeddings = generate_batch_embeddings(texts)

    print(f"Generated {len(embeddings)} embeddings")
    for i, (text, emb) in enumerate(zip(texts, embeddings)):
        print(f"{i+1}. '{text}' -> dimension: {len(emb)}")


async def example_3_create_and_populate_collection():
    """Example 3: Create a collection and insert vectors."""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Create Collection and Insert Vectors")
    print("=" * 80)

    collection_name = "example_messages"

    # Create collection
    print(f"Creating collection: {collection_name}")
    create_collection(collection_name, vector_size=384)

    # Sample messages
    messages = [
        {
            "id": "msg_001",
            "body": "Let's discuss the crypto trading strategy for Bitcoin",
            "from_party_name": "Alice",
            "source_app": "WhatsApp",
            "message_timestamp_dt": "2023-06-15T14:30:00"
        },
        {
            "id": "msg_002",
            "body": "Can we meet tomorrow to talk about the project?",
            "from_party_name": "Bob",
            "source_app": "Telegram",
            "message_timestamp_dt": "2023-06-15T15:00:00"
        },
        {
            "id": "msg_003",
            "body": "The cryptocurrency market is very volatile today",
            "from_party_name": "Charlie",
            "source_app": "WhatsApp",
            "message_timestamp_dt": "2023-06-15T16:00:00"
        },
    ]

    # Generate embeddings and insert
    print(f"Inserting {len(messages)} messages...")

    for msg in messages:
        # Generate embedding from message body
        embedding = generate_text_embedding(msg["body"])

        # Prepare payload (everything except id)
        payload = {k: v for k, v in msg.items() if k != "id"}

        # Insert into Qdrant
        success = insert_vector(
            collection_name=collection_name,
            vector_id=msg["id"],
            vector=embedding,
            payload=payload
        )

        if success:
            print(f"✓ Inserted {msg['id']}: '{msg['body'][:50]}...'")

    print(f"\nCollection '{collection_name}' ready for search!")


async def example_4_search_vectors():
    """Example 4: Search for similar vectors."""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Search for Similar Vectors")
    print("=" * 80)

    collection_name = "example_messages"
    query_text = "Tell me about crypto trading"

    print(f"Query: '{query_text}'")
    print(f"Collection: {collection_name}\n")

    # Generate query embedding
    query_embedding = generate_text_embedding(query_text)

    # Search for similar vectors
    results = search_vectors(
        collection_name=collection_name,
        query_vector=query_embedding,
        limit=5,
        score_threshold=0.3
    )

    print(f"Found {len(results)} results:\n")

    for i, result in enumerate(results, 1):
        print(f"{i}. Score: {result['score']:.3f}")
        print(f"   Message: {result['payload']['body']}")
        print(f"   From: {result['payload']['from_party_name']}")
        print(f"   App: {result['payload']['source_app']}")
        print(f"   ID: {result['id']}\n")


async def example_5_vector_search_tool():
    """Example 5: Use the vector_search tool (as the agent would)."""
    print("\n" + "=" * 80)
    print("EXAMPLE 5: Using Vector Search Tool")
    print("=" * 80)

    # This is how the forensic agent would use the tool
    query = "Tell me about crypto trading"
    collection = "example_messages"

    print(f"Calling vector_search tool...")
    print(f"Query: '{query}'")
    print(f"Collection: {collection}\n")

    # Call the tool
    result = await vector_search(
        query=query,
        collection=collection,
        limit=5,
        score_threshold=0.3
    )

    print(result)


async def example_6_list_collections():
    """Example 6: List all collections."""
    print("\n" + "=" * 80)
    print("EXAMPLE 6: List All Collections")
    print("=" * 80)

    collections = list_collections()
    print(f"Found {len(collections)} collections:\n")

    for i, collection in enumerate(collections, 1):
        print(f"{i}. {collection}")


async def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("VECTOR SEARCH EXAMPLES")
    print("=" * 80)

    try:
        # Run examples
        await example_1_basic_embedding()
        await example_2_batch_embeddings()
        await example_3_create_and_populate_collection()
        await example_4_search_vectors()
        await example_5_vector_search_tool()
        await example_6_list_collections()

        print("\n" + "=" * 80)
        print("ALL EXAMPLES COMPLETED SUCCESSFULLY!")
        print("=" * 80)

    except ImportError as e:
        print("\n" + "=" * 80)
        print("ERROR: Missing required libraries")
        print("=" * 80)
        print(f"\n{str(e)}\n")
        print("To install required libraries:")
        print("  pip install qdrant-client sentence-transformers")
        print("=" * 80)

    except Exception as e:
        print("\n" + "=" * 80)
        print("ERROR:")
        print("=" * 80)
        print(f"\n{str(e)}\n")
        print("Make sure Qdrant server is running:")
        print("  docker run -p 6333:6333 qdrant/qdrant")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
