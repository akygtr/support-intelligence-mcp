import asyncio, json
from src.tools.docs import search_docs

queries = [
    "tags show bad quality after changing the PLC hardware",
    "OPC UA client cannot verify the server certificate",
    "too many tags on one channel causing slow reads",
]

for q in queries:
    r = asyncio.run(search_docs(q))
    print("=" * 70)
    print("Q:", q)
    for hit in r.get("results", []):
        print(f"  [{hit['distance']}] {hit['source']} p{hit['page']}")
        print(f"     {hit['excerpt'][:150].strip()}")
    print()
