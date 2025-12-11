"""
Vector search tool for forensic agent to perform semantic search on vector database.

This module provides a tool that allows the forensic agent to perform semantic searches
using embeddings on Qdrant vector database for messages, images, and other data.
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from agents import function_tool
import logging
import os
from dotenv import load_dotenv

# Import Qdrant client
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import ScoredPoint
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    QdrantClient = None
    ScoredPoint = None

# Import embedding generation (assuming you have this utility)
# You'll need to implement this based on your embedding model
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None

load_dotenv()
logger = logging.getLogger(__name__)


# Initialize Qdrant client (lazy initialization)
_qdrant_client: Optional[QdrantClient] = None
_embedding_model: Optional[SentenceTransformer] = None


def get_qdrant_client() -> QdrantClient:
    """Get or create Qdrant client instance."""
    global _qdrant_client

    if not QDRANT_AVAILABLE:
        raise ImportError("qdrant-client is not installed. Install with: pip install qdrant-client")

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


def get_embedding_model() -> SentenceTransformer:
    """Get or create embedding model instance."""
    global _embedding_model

    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        raise ImportError("sentence-transformers is not installed. Install with: pip install sentence-transformers")

    if _embedding_model is None:
        # Use a model suitable for semantic search
        model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        _embedding_model = SentenceTransformer(model_name)
        logger.info(f"Initialized embedding model: {model_name}")

    return _embedding_model


def generate_embedding(text: str) -> List[float]:
    """
    Convert text query into an embedding vector.

    Args:
        text: The text to convert to embedding

    Returns:
        List of floats representing the embedding vector
    """
    model = get_embedding_model()
    embedding = model.encode(text)
    return embedding.tolist()


class SearchResult(BaseModel):
    """Represents a single search result from vector database."""

    id: str = Field(..., description="Unique ID of the result")
    score: float = Field(..., description="Similarity score (0-1, higher is better)")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Metadata and content")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "id": "msg_12345",
                "score": 0.95,
                "payload": {
                    "body": "Let's discuss the crypto trading strategy",
                    "from_party_name": "John Doe",
                    "message_timestamp_dt": "2023-06-15T14:30:00",
                    "source_app": "WhatsApp"
                }
            }
        }


class VectorSearchResult(BaseModel):
    """Result of a vector search query."""

    success: bool = Field(..., description="Whether the search succeeded")
    collection_name: str = Field(..., description="Name of the collection searched")
    query: str = Field(..., description="Original search query")
    total_results: int = Field(..., description="Number of results returned")
    results: List[SearchResult] = Field(default_factory=list, description="Search results")
    error_message: Optional[str] = Field(None, description="Error message if search failed")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "success": True,
                "collection_name": "messages",
                "query": "crypto trading",
                "total_results": 5,
                "results": []
            }
        }

    def to_summary(self) -> str:
        """Generate a human-readable summary for the agent."""
        if not self.success:
            return f"❌ Vector search failed: {self.error_message}"

        summary = f"🔍 Vector Search Results\n"
        summary += f"{'=' * 60}\n"
        summary += f"Query: '{self.query}'\n"
        summary += f"Collection: {self.collection_name}\n"
        summary += f"Results found: {self.total_results}\n"
        summary += f"{'=' * 60}\n\n"

        if self.total_results == 0:
            summary += "⚠️  No relevant results found for this query.\n"
        else:
            summary += "Top matches:\n\n"

            for i, result in enumerate(self.results, 1):
                summary += f"{i}. [Score: {result.score:.3f}]\n"

                # Display payload contents
                payload = result.payload

                # Message-specific fields
                if 'body' in payload:
                    body = payload['body']
                    body_preview = body[:150] + "..." if len(body) > 150 else body
                    summary += f"   📝 Message: {body_preview}\n"

                if 'from_party_name' in payload:
                    summary += f"   👤 From: {payload['from_party_name']}\n"
                elif 'from_party_identifier' in payload:
                    summary += f"   👤 From: {payload['from_party_identifier']}\n"

                if 'to_party_name' in payload:
                    summary += f"   👤 To: {payload['to_party_name']}\n"
                elif 'to_party_identifier' in payload:
                    summary += f"   👤 To: {payload['to_party_identifier']}\n"

                if 'message_timestamp_dt' in payload:
                    summary += f"   🕐 Time: {payload['message_timestamp_dt']}\n"

                if 'source_app' in payload:
                    summary += f"   📱 App: {payload['source_app']}\n"

                # Image-specific fields
                if 'image_description' in payload:
                    summary += f"   🖼️  Description: {payload['image_description']}\n"

                if 'file_path' in payload:
                    summary += f"   📄 File: {payload['file_path']}\n"

                # Generic fields
                if 'content' in payload and 'body' not in payload:
                    content = payload['content']
                    content_preview = content[:150] + "..." if len(content) > 150 else content
                    summary += f"   📄 Content: {content_preview}\n"

                summary += f"   🔑 ID: {result.id}\n"
                summary += "\n"

            if self.total_results > 10:
                summary += f"... showing top 10 of {self.total_results} results.\n"

        return summary


async def vector_search(
    query: str,
    collection: str = "messages",
    limit: int = 5,
    score_threshold: Optional[float] = None
) -> str:
    """
    Perform semantic vector search on Qdrant database.

    This tool performs semantic search using embeddings to find relevant data
    based on the meaning of the query, not just keyword matching.

    Args:
        query: Natural language search query (e.g., "Tell me about messages regarding crypto trading")
        collection: Name of the Qdrant collection to search in (default: "messages")
                   Available collections: messages, images, locations, contacts
        limit: Maximum number of results to return (default: 5, max: 20)
        score_threshold: Minimum similarity score (0-1). Only return results above this threshold.
                        Higher values = more strict matching. Recommended: 0.7

    Returns:
        A formatted string containing the search results with relevance scores

    Examples:
        - vector_search("crypto trading messages") - Find messages about crypto trading
        - vector_search("meeting location", collection="locations") - Find locations related to meetings
        - vector_search("suspicious images", collection="images", score_threshold=0.8) - Find relevant images
        - vector_search("John Doe contact info", collection="contacts") - Find contact information
    """
    # Log tool invocation
    log_message = f"""
{'=' * 80}
🔧 VECTOR SEARCH TOOL CALLED
{'=' * 80}
Input Parameters:
  query: {query}
  collection: {collection}
  limit: {limit}
  score_threshold: {score_threshold}
{'=' * 80}
"""
    print(log_message)
    logger.info(log_message)

    try:
        # Validate limit
        if limit > 20:
            limit = 20
        elif limit < 1:
            limit = 5

        # Generate embedding for the query
        query_embedding = generate_embedding(query)

        # Get Qdrant client
        client = get_qdrant_client()

        # Perform vector search
        search_params = {
            "collection_name": collection,
            "query_vector": query_embedding,
            "limit": limit,
        }

        if score_threshold is not None:
            search_params["score_threshold"] = score_threshold

        search_results = client.search(**search_params)

        # Convert to SearchResult objects
        results = []
        for scored_point in search_results:
            results.append(SearchResult(
                id=str(scored_point.id),
                score=scored_point.score,
                payload=scored_point.payload or {}
            ))

        result = VectorSearchResult(
            success=True,
            collection_name=collection,
            query=query,
            total_results=len(results),
            results=results
        )

        output = result.to_summary()
        success_msg = f"""
✅ VECTOR SEARCH TOOL - Success
Collection: {collection}, Results: {len(results)}
Query: {query}
Output length: {len(output)} characters
{'=' * 80}
"""
        print(success_msg)
        logger.info(success_msg)
        return output

    except ImportError as e:
        error_msg = f"""
{'=' * 80}
❌ VECTOR SEARCH TOOL - Import Error
Error: {str(e)}
{'=' * 80}
"""
        print(error_msg)
        logger.error(error_msg)

        result = VectorSearchResult(
            success=False,
            collection_name=collection,
            query=query,
            total_results=0,
            results=[],
            error_message=f"Required libraries not installed: {str(e)}"
        )
        return result.to_summary()

    except Exception as e:
        error_msg = f"""
{'=' * 80}
❌ VECTOR SEARCH TOOL - Error occurred
Error: {str(e)}
{'=' * 80}
"""
        print(error_msg)
        logger.error(error_msg)
        logger.error(f"Full traceback:", exc_info=True)

        result = VectorSearchResult(
            success=False,
            collection_name=collection,
            query=query,
            total_results=0,
            results=[],
            error_message=str(e)
        )
        output = result.to_summary()
        print(f"Error output:\n{output}")
        print("=" * 80)
        return output


# Create the tool for the agent
vector_search_tool = function_tool(
    vector_search,
    name_override="vector_search",
    description_override="Perform semantic vector search on Qdrant database to find relevant messages, images, locations, or contacts based on query meaning"
)
