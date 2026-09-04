import os, requests
from dotenv import load_dotenv

load_dotenv()
base = os.getenv("JIRA_BASE_URL")
auth = (os.getenv("JIRA_EMAIL"), os.getenv("JIRA_API_TOKEN"))

r = requests.get(f"{base}/rest/api/3/project/search", auth=auth,
                 params={"maxResults": 50})
print("status:", r.status_code)
for p in r.json().get("values", []):
    print(f"  {p['key']:<10} {p['name']}")
