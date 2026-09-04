"""
Chunk and embed the documentation corpus into a local vector store.

Runs offline with a local embedding model. The corpus PDFs are gitignored —
they are PTC copyright — but the index is small and reproducible from
corpus/SOURCES.md, so anyone can rebuild it from their own copies.

Usage:
    python -m src.index_corpus          # build or rebuild the index
    python -m src.index_corpus --stats  # report what is indexed
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
CORPUS = ROOT / "corpus"
INDEX = ROOT / "corpus" / ".chroma"
COLLECTION = "kepware_docs"

# ~1000 chars with overlap. Small enough that a hit is specific, large enough
# that a procedure is not split across chunks mid-step.
CHUNK_CHARS = 1000
OVERLAP = 200


def extract_pages(pdf_path: Path) -> list:
    """Return (page_number, text) for each page with usable content."""
    import pypdf

    reader = pypdf.PdfReader(str(pdf_path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if len(text) > 50:  # skip covers, blank pages, pure-image pages
            pages.append((i, text))
    return pages


def chunk_text(text: str) -> list:
    """Split on paragraph boundaries where possible, hard-split when not."""
    text = re.sub(r"\n{3,}", "\n\n", text)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) < CHUNK_CHARS:
            current = f"{current}\n\n{para}" if current else para
            continue

        if current:
            chunks.append(current)
        # A single paragraph longer than the chunk size gets hard-split.
        while len(para) > CHUNK_CHARS:
            chunks.append(para[:CHUNK_CHARS])
            para = para[CHUNK_CHARS - OVERLAP:]
        current = para

    if current:
        chunks.append(current)

    return chunks


def build() -> None:
    import chromadb
    from chromadb.utils import embedding_functions

    pdfs = sorted(CORPUS.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(
            "No PDFs in corpus/. See corpus/SOURCES.md for what to download."
        )

    embedder = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    client = chromadb.PersistentClient(path=str(INDEX))
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    collection = client.create_collection(
        name=COLLECTION, embedding_function=embedder
    )

    total = 0
    for pdf in pdfs:
        print(f"  {pdf.name} ...", end=" ", flush=True)
        docs, metas, ids = [], [], []

        for page_no, page_text in extract_pages(pdf):
            for j, chunk in enumerate(chunk_text(page_text)):
                docs.append(chunk)
                metas.append({"source": pdf.name, "page": page_no})
                ids.append(f"{pdf.stem}_p{page_no}_c{j}")

        if docs:
            # Batched — Chroma has a per-call limit and these are large files.
            for start in range(0, len(docs), 200):
                collection.add(
                    documents=docs[start:start + 200],
                    metadatas=metas[start:start + 200],
                    ids=ids[start:start + 200],
                )
        print(f"{len(docs)} chunks")
        total += len(docs)

    print(f"\nIndexed {total} chunks from {len(pdfs)} documents into {INDEX.name}")


def stats() -> None:
    import chromadb

    client = chromadb.PersistentClient(path=str(INDEX))
    collection = client.get_collection(COLLECTION)
    print(f"{COLLECTION}: {collection.count()} chunks")


if __name__ == "__main__":
    stats() if "--stats" in sys.argv else build()