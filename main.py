from src.tools.jira import get_ticket_details
from src.tools.slack import get_slack_messages
from src.tools.confluence import search_confluence

def diagnose_ticket(ticket_id: str) -> dict:
    """
    Full support workflow:
    1. Fetch ticket details from Jira
    2. Search Slack for related messages
    3. Search Confluence for related documentation
    4. Return everything combined
    """
    print(f"\n--- Fetching Jira ticket {ticket_id} ---")
    ticket = get_ticket_details(ticket_id)
    
    if "error" in ticket:
        return {"error": f"Could not fetch ticket: {ticket['error']}"}
    
    # use ticket summary as search keyword
    keyword = ticket["summary"]
    print(f"Ticket summary: {keyword}")
    
    print(f"\n--- Searching Slack for '{keyword}' ---")
    slack_results = get_slack_messages(keyword)
    
    print(f"\n--- Searching Confluence for '{keyword}' ---")
    confluence_results = search_confluence(keyword)
    
    # combine everything into one response
    return {
        "ticket": ticket,
        "slack": slack_results,
        "confluence": confluence_results
    }


if __name__ == "__main__":
    result = diagnose_ticket("SUP-1")
    
    print("\n========= DIAGNOSIS RESULT =========")
    print(f"Ticket: {result['ticket']['summary']}")
    print(f"Status: {result['ticket']['status']}")
    print(f"Priority: {result['ticket']['priority']}")
    print(f"Description: {result['ticket']['description']}")
    
    print(f"\nSlack messages found: {result['slack'].get('total', 0)}")
    for msg in result['slack'].get('results', []):
        print(f"  - {msg['text']}")
    
    print(f"\nConfluence pages found: {result['confluence'].get('total', 0)}")
    for page in result['confluence'].get('results', []):
        print(f"  - {page['title']}: {page['url']}")