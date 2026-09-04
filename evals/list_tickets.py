import os, requests
from dotenv import load_dotenv

load_dotenv()
base = os.getenv("JIRA_BASE_URL")
auth = (os.getenv("JIRA_EMAIL"), os.getenv("JIRA_API_TOKEN"))

r = requests.get(
    f"{base}/rest/api/3/search/jql",
    auth=auth,
    params={"jql": "project = SUP ORDER BY created DESC",
            "maxResults": 20, "fields": "summary,status"},
)
print("status:", r.status_code)
for issue in r.json().get("issues", []):
    f = issue["fields"]
    print(f"  {issue['key']:<10} {f['status']['name']:<12} {f['summary'][:60]}")
