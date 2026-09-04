import asyncio
from src.agent import diagnose_agentic

r = asyncio.run(diagnose_agentic("SUP-20", "Cobalt Systems"))
print("tools:", r["tools_used"])
print("iterations:", r["iterations"])
print("-" * 60)
print(r["diagnosis"])
