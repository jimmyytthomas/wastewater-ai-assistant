"""Persistent Chroma index of the wastewater document chunks.

Uses Chroma's default local embedding model, so no API key is required.
"""

from pathlib import Path

import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from ingest import load_chunks

# ./chroma_db from the project root. Git ignores this directory.
ROOT = Path(__file__).resolve().parents[1]
CHROMA_PATH = ROOT / "chroma_db"
COLLECTION_NAME = "wastewater_docs"
BATCH_SIZE = 100

# One shared embedder so indexing and search use the same default model.
EMBEDDING = DefaultEmbeddingFunction()


def _client():
    return chromadb.PersistentClient(
        path=str(CHROMA_PATH),
        settings=Settings(anonymized_telemetry=False),
    )


def build_index():
    """Delete and recreate wastewater_docs, then add every chunk in batches."""
    client = _client()
    names = [collection.name for collection in client.list_collections()]
    if COLLECTION_NAME in names:
        client.delete_collection(COLLECTION_NAME)

    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=EMBEDDING,
    )

    chunks = load_chunks()
    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start : start + BATCH_SIZE]
        collection.add(
            ids=[chunk["id"] for chunk in batch],
            documents=[chunk["text"] for chunk in batch],
            metadatas=[_metadata(chunk) for chunk in batch],
        )

    return len(chunks)


def _metadata(chunk):
    """Store every field except the id and the text, which Chroma keeps separately."""
    return {key: value for key, value in chunk.items() if key not in ("id", "text")}


def search(question, k=8):
    """Return the top k chunks, each with text, metadata, and distance."""
    client = _client()
    if COLLECTION_NAME not in [collection.name for collection in client.list_collections()]:
        raise RuntimeError(
            "The document index is missing. Build it with: python src/store.py"
        )
    collection = client.get_collection(
        name=COLLECTION_NAME,
        embedding_function=EMBEDDING,
    )
    total = collection.count()
    if total == 0:
        return []
    result = collection.query(query_texts=[question], n_results=min(k, total))

    hits = []
    documents = result["documents"][0]
    metadatas = result["metadatas"][0]
    distances = result["distances"][0]
    for text, metadata, distance in zip(documents, metadatas, distances):
        hits.append({"text": text, "metadata": metadata, "distance": distance})
    return hits


if __name__ == "__main__":
    total = build_index()
    print(f"Total chunks: {total}")
