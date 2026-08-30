import requests
from requests.auth import HTTPBasicAuth
import os

def get_sprint_items(url: str, email: str, API_TOKEN: str) -> dict:
    resp = requests.get(
            url=url,
            params={"state": "active"},
            auth=HTTPBasicAuth(email, API_TOKEN),
            headers={"Accept": "application/json"},
        )

    resp.raise_for_status()

    return resp.json()


def handler(event, context) -> dict:
    base_url = "https://joshnelson00.atlassian.net"
    board_id = os.environ['JIRA_BOARD_ID']
    email = os.environ['EMAIL']
    JIRA_API_TOKEN = os.environ['JIRA_API_TOKEN']

    url = f"{base_url}/rest/agile/1.0/board/{board_id}/sprint"

    sprint_items = get_sprint_items(url=url, email=email, API_TOKEN=JIRA_API_TOKEN)
    
    print(sprint_items)

    return {
        "version": "1.0",
        "response": {
            "outputSpeech": {
                "type": "PlainText",
                "text": "Placeholder Jira Summary",
                }
        }
    }


