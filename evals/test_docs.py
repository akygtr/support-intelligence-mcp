import asyncio
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
    print(f"   {r.get('strong_matches', 0)} strong of {r.get('total', 0)}")
    for hit in r.get("results", []):
        print(f"  [{hit['distance']} {hit['match']:>6}] {hit['source']} p{hit['page']}")
        print(f"     {hit['excerpt'][:120].strip()}")
    print()
