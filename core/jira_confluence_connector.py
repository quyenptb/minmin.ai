import os
import re
import logging
import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger("AtlassianConnector")

class AtlassianConnector:
    """Connector kết nối Atlassian (Headless Backend)."""
    
    def __init__(self):
        self.jira_url = os.getenv("JIRA_URL")
        self.jira_email = os.getenv("JIRA_EMAIL")
        self.jira_token = os.getenv("JIRA_API_TOKEN")
        self.jira_project = os.getenv("JIRA_PROJECT_KEY", "IEP")

        self.confluence_url = os.getenv("CONFLUENCE_URL")
        self.confluence_email = os.getenv("CONFLUENCE_EMAIL")
        self.confluence_token = os.getenv("CONFLUENCE_API_TOKEN")
        self.confluence_space = os.getenv("CONFLUENCE_SPACE_KEY", "SEN")

    def _get_auth(self, service: str):
        if service == "jira":
            return HTTPBasicAuth(self.jira_email, self.jira_token)
        return HTTPBasicAuth(self.confluence_email, self.confluence_token)

    # --- HÀM GHI (CHATOPS) ---
    def create_jira_task(self, summary: str, description: str, assignee_name: str) -> str:
        """Tạo Ticket Jira mới (Mục tiêu IEP) từ lệnh Slack."""
        if not all([self.jira_url, self.jira_email, self.jira_token, self.jira_project]):
            logger.warning("Mocking Jira Task (Missing Env).")
            return "MOCK-IEP-101"

        url = f"{self.jira_url.rstrip('/')}/rest/api/2/issue"
        payload = {
            "fields": {
                "project": {"key": self.jira_project},
                "summary": f"[IEP: {assignee_name}] {summary}",
                "description": description,
                "issuetype": {"name": "Task"}
            }
        }
        
        try:
            res = requests.post(url, json=payload, headers={"Accept": "application/json"}, auth=self._get_auth("jira"), timeout=10)
            if res.status_code == 201:
                return res.json().get("key", "SUCCESS")
            return "ERROR"
        except Exception as e:
            logger.error(f"Jira Create Exception: {e}")
            return "ERROR"

    # --- CÁC HÀM ĐỌC (RAG) ĐƯỢC GIỮ NGUYÊN ---
    def fetch_live_jira_tasks(self) -> list[dict]:
        """Lấy danh sách mục tiêu học tập."""
        if not all([self.jira_url, self.jira_email, self.jira_token]): return []
        try:
            url = f"{self.jira_url.rstrip('/')}/rest/api/2/search/jql"
            res = requests.get(url, headers={"Accept": "application/json"}, auth=self._get_auth("jira"), params={"jql": f"project={self.jira_project}", "maxResults": 10}, timeout=5)
            if res.status_code != 200: return []
            
            tasks = []
            for issue in res.json().get("issues", []):
                key = issue.get("key")
                summary = issue.get("fields", {}).get("summary", "")
                tasks.append({"content": f"Task {key}: {summary}", "metadata": {"source": f"jira/{key}", "type": "task"}})
            return tasks
        except: return []

    def fetch_live_confluence_pages(self) -> list[dict]:
        """Lấy hồ sơ tâm lý trẻ."""
        if not all([self.confluence_url, self.confluence_token]): return []
        try:
            url = f"{self.confluence_url.rstrip('/')}/wiki/api/v2/pages"
            res = requests.get(url, headers={"Accept": "application/json"}, auth=self._get_auth("confluence"), params={"spaceKey": self.confluence_space}, timeout=5)
            if res.status_code != 200: return []
            
            pages = []
            for page in res.json().get("results", []):
                pages.append({"content": f"Profile: {page.get('title')}", "metadata": {"source": f"confluence/{page.get('id')}", "type": "profile"}})
            return pages
        except: return []