"""
Embeddings module using Ollama.

Generates vector embeddings for text using a local Ollama instance.
"""

import httpx
from typing import List

from .config import settings


async def get_embeddings(text: str) -> List[float]:
    """
    Generate embeddings for text using Ollama.
    
    Args:
        text: Text to embed (will be truncated if too long)
        
    Returns:
        List of floats representing the embedding vector
        
    Raises:
        Exception: If Ollama request fails
    """
    # Truncate very long texts (Ollama has context limits)
    max_chars = 8000
    if len(text) > max_chars:
        text = text[:max_chars]
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{settings.ollama_host}/api/embeddings",
            json={
                "model": settings.embedding_model,
                "prompt": text
            }
        )
        response.raise_for_status()
        data = response.json()
        
        return data["embedding"]


async def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for multiple texts.
    
    Args:
        texts: List of texts to embed
        
    Returns:
        List of embedding vectors
    """
    embeddings = []
    for text in texts:
        embedding = await get_embeddings(text)
        embeddings.append(embedding)
    return embeddings
