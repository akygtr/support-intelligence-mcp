import json
from pathlib import Path
from src.injection import scan

for name in ["slack_sup-20", "slack_sup-1", "confluence_sup-16"]:
    payload = json.loads(Path(f"fixtures/{name}.json").read_text(encoding="utf-8"))
    findings = scan(payload)
    print(f"{name}: {len(findings)} finding(s)")
    for f in findings:
        print(f"   at {f['where']}: {', '.join(f['labels'])}")
        print(f"   {f['excerpt'][:110]}")
    print()
