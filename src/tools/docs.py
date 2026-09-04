"""
Semantic search over the documentation corpus.

The Confluence tool matches keywords, which is why a page containing the word
"binding" ranks for a binding question even when it is meeting notes about
something else. This ranks by meaning instead.

Both tools stay available. They cover different corpora — Confluence holds
recent internal notes, this holds product documentation — and keeping both
lets the retrieval approaches be compared directly.
"""

import json
from pathlib import Path

from src.fixtures import is_mock, load

INDEX = Path(__file__).parent.parent.parent / "corpus" / ".chroma"
COLLECTION = "kepware_docs"

_collection = None


def _get_collection():
    """Load the index lazily. The embedding model costs ~1s to initialise."""
    global _collection
    if _collection is not None:
        return _collection

    import chromadb
    from chromadb.utils import embedding_functions

    if not INDEX.exists():
        raise RuntimeError(
            "No document index. Run: python -m src.index_corpus"
        )

    embedder = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    client = chromadb.PersistentClient(path=str(INDEX))
    _collection = client.get_collection(COLLECTION, embedding_function=embedder)
    return _collection


async def search_docs(query: str, ticket_id: str = "", max_results: int = 3) -> dict:
    """Search product documentation by meaning rather than keyword.

    Returns the source document, page number, and an excerpt for each hit,
    plus a distance score so a weak match is visible rather than presented
    with the same confidence as a strong one.
    """
    if is_mock():
        return load("docs", ticket_id or query)

    try:
        collection = _get_collection()
        found = collection.query(query_texts=[query], n_results=max_results)
    except Exception as e:
        return {"error": f"Document search failed: {e}", "results": [], "total": 0}

    results = []
    for doc, meta, dist in zip(
        found["documents"][0], found["metadatas"][0], found["distances"][0]
    ):
        results.append({
            "source": meta["source"],
            "page": meta["page"],
            "excerpt": doc[:400],
            "distance": round(dist, 3),
        })

    return {"results": results, "total": len(results), "query": query}