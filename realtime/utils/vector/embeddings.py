"""
Utility functions for generating embeddings and interacting with vector databases.

This module provides helper functions for:
- Converting text/images to embeddings
- Initializing and managing Qdrant client
- Storing and retrieving vectors
"""

from __future__ import annotations

from typing import Optional, List, Union
import os
import logging
from dotenv import load_dotenv

# Import Qdrant client
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    QdrantClient = None

# Import embedding models
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None

load_dotenv()
logger = logging.getLogger(__name__)


# Global instances (lazy initialization)
_qdrant_client: Optional[QdrantClient] = None
_text_embedding_model: Optional[SentenceTransformer] = None


def get_qdrant_client() -> QdrantClient:
    """
    Get or create Qdrant client instance.

    Returns:
        QdrantClient instance

    Raises:
        ImportError: If qdrant-client is not installed
    """
    global _qdrant_client

    if not QDRANT_AVAILABLE:
        raise ImportError(
            "qdrant-client is not installed. Install with: pip install qdrant-client"
        )

    if _qdrant_client is None:
        # Get Qdrant configuration from environment
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        qdrant_api_key = os.getenv("QDRANT_API_KEY", None)

        _qdrant_client = QdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key,
        )
        logger.info(f"Initialized Qdrant client with URL: {qdrant_url}")

    return _qdrant_client


def get_text_embedding_model() -> SentenceTransformer:
    """
    Get or create text embedding model instance.

    Returns:
        SentenceTransformer model instance

    Raises:
        ImportError: If sentence-transformers is not installed
    """
    global _text_embedding_model

    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        raise ImportError(
            "sentence-transformers is not installed. Install with: pip install sentence-transformers"
        )

    if _text_embedding_model is None:
        # Use a model suitable for semantic search
        model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        _text_embedding_model = SentenceTransformer(model_name)
        logger.info(f"Initialized text embedding model: {model_name}")

    return _text_embedding_model


def generate_text_embedding(text: str) -> List[float]:
    """
    Convert text into an embedding vector.

    Args:
        text: The text to convert to embedding

    Returns:
        List of floats representing the embedding vector

    Example:
        >>> embedding = generate_text_embedding("Hello, world!")
        >>> print(len(embedding))
        384  # For all-MiniLM-L6-v2 model
    """
    model = get_text_embedding_model()
    embedding = model.encode(text)
    return embedding.tolist()


def generate_batch_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Convert multiple texts into embedding vectors efficiently.

    Args:
        texts: List of texts to convert to embeddings

    Returns:
        List of embedding vectors

    Example:
        >>> texts = ["Hello", "World", "Embedding"]
        >>> embeddings = generate_batch_embeddings(texts)
        >>> print(len(embeddings))
        3
    """
    model = get_text_embedding_model()
    embeddings = model.encode(texts)
    return [emb.tolist() for emb in embeddings]


def create_collection(
    collection_name: str,
    vector_size: int = 384,
    distance: str = "Cosine"
) -> bool:
    """
    Create a new collection in Qdrant.

    Args:
        collection_name: Name of the collection to create
        vector_size: Dimension of the vectors (default: 384 for all-MiniLM-L6-v2)
        distance: Distance metric to use ("Cosine", "Euclid", "Dot")

    Returns:
        True if collection was created successfully

    Example:
        >>> create_collection("messages", vector_size=384)
        True
    """
    client = get_qdrant_client()

    # Map distance string to Qdrant Distance enum
    distance_map = {
        "Cosine": Distance.COSINE,
        "Euclid": Distance.EUCLID,
        "Dot": Distance.DOT,
    }

    distance_metric = distance_map.get(distance, Distance.COSINE)

    try:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=distance_metric),
        )
        logger.info(f"Created collection: {collection_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to create collection {collection_name}: {e}")
        return False


def insert_vector(
    collection_name: str,
    vector_id: Union[str, int],
    vector: List[float],
    payload: dict
) -> bool:
    """
    Insert a single vector with metadata into Qdrant.

    Args:
        collection_name: Name of the collection
        vector_id: Unique ID for this vector
        vector: The embedding vector
        payload: Metadata dictionary to store with the vector

    Returns:
        True if insertion was successful

    Example:
        >>> embedding = generate_text_embedding("Hello crypto traders")
        >>> payload = {
        ...     "body": "Hello crypto traders",
        ...     "from_party_name": "John",
        ...     "source_app": "WhatsApp"
        ... }
        >>> insert_vector("messages", "msg_123", embedding, payload)
        True
    """
    client = get_qdrant_client()

    try:
        client.upsert(
            collection_name=collection_name,
            points=[
                PointStruct(
                    id=vector_id,
                    vector=vector,
                    payload=payload
                )
            ]
        )
        logger.debug(f"Inserted vector {vector_id} into {collection_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to insert vector {vector_id}: {e}")
        return False


def insert_batch_vectors(
    collection_name: str,
    vectors: List[tuple[Union[str, int], List[float], dict]]
) -> bool:
    """
    Insert multiple vectors with metadata into Qdrant efficiently.

    Args:
        collection_name: Name of the collection
        vectors: List of tuples (id, vector, payload)

    Returns:
        True if batch insertion was successful

    Example:
        >>> vectors = [
        ...     ("msg_1", embedding1, {"body": "Text 1"}),
        ...     ("msg_2", embedding2, {"body": "Text 2"}),
        ... ]
        >>> insert_batch_vectors("messages", vectors)
        True
    """
    client = get_qdrant_client()

    try:
        points = [
            PointStruct(id=vid, vector=vec, payload=payload)
            for vid, vec, payload in vectors
        ]

        client.upsert(
            collection_name=collection_name,
            points=points
        )
        logger.info(f"Inserted {len(points)} vectors into {collection_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to insert batch vectors: {e}")
        return False


def search_vectors(
    collection_name: str,
    query_vector: List[float],
    limit: int = 5,
    score_threshold: Optional[float] = None
) -> List[dict]:
    """
    Search for similar vectors in Qdrant.

    Args:
        collection_name: Name of the collection to search
        query_vector: The query embedding vector
        limit: Maximum number of results to return
        score_threshold: Minimum similarity score (0-1)

    Returns:
        List of search results with id, score, and payload

    Example:
        >>> query_embedding = generate_text_embedding("crypto trading")
        >>> results = search_vectors("messages", query_embedding, limit=5)
        >>> for result in results:
        ...     print(f"Score: {result['score']}, Body: {result['payload']['body']}")
    """
    client = get_qdrant_client()

    try:
        search_params = {
            "collection_name": collection_name,
            "query_vector": query_vector,
            "limit": limit,
        }

        if score_threshold is not None:
            search_params["score_threshold"] = score_threshold

        results = client.search(**search_params)

        return [
            {
                "id": str(result.id),
                "score": result.score,
                "payload": result.payload or {}
            }
            for result in results
        ]
    except Exception as e:
        logger.error(f"Failed to search vectors: {e}")
        return []


def delete_collection(collection_name: str) -> bool:
    """
    Delete a collection from Qdrant.

    Args:
        collection_name: Name of the collection to delete

    Returns:
        True if deletion was successful

    Example:
        >>> delete_collection("old_messages")
        True
    """
    client = get_qdrant_client()

    try:
        client.delete_collection(collection_name=collection_name)
        logger.info(f"Deleted collection: {collection_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete collection {collection_name}: {e}")
        return False


def list_collections() -> List[str]:
    """
    List all collections in Qdrant.

    Returns:
        List of collection names

    Example:
        >>> collections = list_collections()
        >>> print(collections)
        ['messages', 'images', 'contacts']
    """
    client = get_qdrant_client()

    try:
        collections = client.get_collections()
        return [col.name for col in collections.collections]
    except Exception as e:
        logger.error(f"Failed to list collections: {e}")
        return []
