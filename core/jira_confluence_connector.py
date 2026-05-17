import os
import re
import time
import logging
import requests
from typing import List, Dict, Optional, Union
from requests.auth import HTTPBasicAuth
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AtlassianConnector")


class AtlassianConnector:
    """
    Connector chịu trách nhiệm gọi API Jira/Confluence trực tiếp.
    
    Features:
    - ✅ Hỗ trợ cả endpoint /search/jql (v2/v3) với fallback tự động
    - ✅ Smart unwrapping: xử lý cấu trúc response lồng nhau từ Jira API
    - ✅ Parse ADF (Atlassian Document Format) cho description field
    - ✅ Clean HTML tự động cho Confluence content
    - ✅ Retry logic với exponential backoff cho transient errors
    - ✅ Type hints đầy đủ để dễ maintain và debug
    - ✅ Logging chi tiết phục vụ monitoring trên production
    """
    
    # Constants for API configuration
    DEFAULT_TIMEOUT: int = 10
    DEFAULT_MAX_RESULTS: int = 50
    MAX_RETRIES: int = 3
    RETRY_BACKOFF_FACTOR: float = 0.5
    
    def __init__(self, 
                 timeout: Optional[int] = None,
                 max_results: Optional[int] = None,
                 enable_retry: bool = True):
        """
        Khởi tạo connector với cấu hình linh hoạt.
        
        Args:
            timeout: Timeout cho mỗi request (seconds), default: 10
            max_results: Số lượng tối đa trả về mỗi lần fetch, default: 50
            enable_retry: Bật/tắt cơ chế retry khi gặp lỗi transient
        """
        # Jira configuration
        self.jira_url = os.getenv("JIRA_URL")
        self.jira_email = os.getenv("JIRA_EMAIL")
        self.jira_token = os.getenv("JIRA_API_TOKEN")
        self.jira_project = os.getenv("JIRA_PROJECT_KEY")

        # Confluence configuration
        self.confluence_url = os.getenv("CONFLUENCE_URL")
        self.confluence_email = os.getenv("CONFLUENCE_EMAIL")
        self.confluence_token = os.getenv("CONFLUENCE_API_TOKEN")
        self.confluence_space = os.getenv("CONFLUENCE_SPACE_KEY")
        
        # Runtime configuration
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.max_results = max_results or self.DEFAULT_MAX_RESULTS
        self.enable_retry = enable_retry
        
        # Initialize session with retry strategy if enabled
        self.session = self._init_session()

    def _init_session(self) -> requests.Session:
        """Khởi tạo requests session với retry strategy tùy chọn."""
        session = requests.Session()
        
        if self.enable_retry:
            retry_strategy = Retry(
                total=self.MAX_RETRIES,
                backoff_factor=self.RETRY_BACKOFF_FACTOR,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET", "POST"]
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("https://", adapter)
            session.mount("http://", adapter)
            logger.debug("[Connector] Enabled retry strategy for transient errors")
            
        return session

    def _validate_config(self, service: str) -> bool:
        """Kiểm tra cấu hình môi trường cho service chỉ định."""
        if service == "jira":
            required = [self.jira_url, self.jira_email, self.jira_token, self.jira_project]
            missing = [name for name, val in zip(
                ["JIRA_URL", "JIRA_EMAIL", "JIRA_API_TOKEN", "JIRA_PROJECT_KEY"], 
                required
            ) if not val]
            if missing:
                logger.warning(f"⚠️ Thiếu cấu hình Jira: {', '.join(missing)}. Sẽ sử dụng Mock Data.")
                return False
            return True
        elif service == "confluence":
            required = [self.confluence_url, self.confluence_email, self.confluence_token, self.confluence_space]
            missing = [name for name, val in zip(
                ["CONFLUENCE_URL", "CONFLUENCE_EMAIL", "CONFLUENCE_API_TOKEN", "CONFLUENCE_SPACE_KEY"], 
                required
            ) if not val]
            if missing:
                logger.warning(f"⚠️ Thiếu cấu hình Confluence: {', '.join(missing)}. Sẽ sử dụng Mock Data.")
                return False
            return True
        return False

    @staticmethod
    def clean_html(html_content: str) -> str:
        """
        Lọc bỏ toàn bộ thẻ HTML/JS/CSS từ Confluence để giữ lại text sạch.
        
        Args:
            html_content: Chuỗi HTML cần clean
            
        Returns:
            str: Text đã được làm sạch, chuẩn hóa whitespace
        """
        if not html_content:
            return ""
        
        # Remove style và script blocks trước
        clean_text = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', html_content, flags=re.IGNORECASE)
        clean_text = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', clean_text, flags=re.IGNORECASE)
        
        # Remove all HTML tags
        clean_text = re.sub(r'<[^>]+?>', ' ', clean_text)
        
        # Normalize whitespace: multiple spaces/tabs/newlines → single space
        clean_text = re.sub(r'[\s\n\r\t]+', ' ', clean_text)
        
        return clean_text.strip()

    @staticmethod
    def _unwrap_jira_issue(item: Dict) -> Optional[Dict]:
        """
        Cơ chế giải bọc thông minh cho Jira issue từ response API.
        Xử lý các trường hợp:
        - Issue nằm trực tiếp trong array
        - Issue bọc trong key "issue"
        - Issue bọc trong dict bất kỳ nhưng chứa "fields"
        
        Args:
            item: Dict từ response JSON
            
        Returns:
            Optional[Dict]: Issue dict đã unwrap, hoặc None nếu không hợp lệ
        """
        if not isinstance(item, dict):
            return None
            
        # Case 1: Item đã là issue (có "fields" và "key")
        if "fields" in item and "key" in item:
            return item
            
        # Case 2: Issue bọc trong key "issue"
        if "issue" in item and isinstance(item["issue"], dict):
            return item["issue"]
            
        # Case 3: Issue bọc trong dict con bất kỳ - tìm đệ quy 1 level
        for val in item.values():
            if isinstance(val, dict) and "fields" in val and "key" in val:
                return val
                
        logger.debug(f"⚠️ Không thể unwrap issue từ item: {list(item.keys())[:5]}...")
        return None

    @staticmethod
    def _parse_adf_description(description_obj: Optional[Union[Dict, str]]) -> str:
        """
        Parse description field từ Atlassian Document Format (ADF) hoặc plain text.
        
        Args:
            description_obj: Description từ Jira API (ADF dict hoặc string)
            
        Returns:
            str: Plain text đã được extract
        """
        if not description_obj:
            return ""
            
        # Case: ADF format (Jira API v3)
        if isinstance(description_obj, dict):
            text_parts = []
            content_nodes = description_obj.get("content", [])
            
            for node in content_nodes:
                if not isinstance(node, dict):
                    continue
                # Handle paragraph, heading, list items
                node_content = node.get("content", [])
                if isinstance(node_content, list):
                    for text_node in node_content:
                        if isinstance(text_node, dict) and text_node.get("type") == "text":
                            text_parts.append(text_node.get("text", ""))
                # Handle direct text in node (fallback)
                elif node.get("type") == "text":
                    text_parts.append(node.get("text", ""))
                    
            return " ".join(text_parts).strip()
            
        # Case: Plain text or HTML string (Jira API v2 or fallback)
        return str(description_obj).strip()

    def fetch_live_jira_tasks(self, 
                             custom_jql: Optional[str] = None,
                             fields: Optional[List[str]] = None) -> List[Dict]:
        """
        Gọi API Jira lấy các task trong Project chỉ định.
        
        Args:
            custom_jql: JQL query tùy chỉnh (default: "project={JIRA_PROJECT_KEY}")
            fields: Danh sách fields cần fetch (default: key, summary, description, status, assignee)
            
        Returns:
            List[Dict]: Danh sách tasks đã được chuẩn hóa cho RAG
        """
        if not self._validate_config("jira"):
            return []

        jql = custom_jql or f"project={self.jira_project}"
        headers = {"Accept": "application/json"}
        auth = HTTPBasicAuth(self.jira_email, self.jira_token)
        
        # Default fields optimized for RAG: minimal but sufficient
        default_fields = ["summary", "description", "status", "assignee"]
        fields_param = ",".join(fields) if fields else ",".join(default_fields)
        
        params = {
            "jql": jql, 
            "maxResults": self.max_results,
            "fields": fields_param
        }

        # Try endpoints in order: v3 → v2 (both with /search/jql)
        endpoints = [
            {"version": "v3", "url": f"{self.jira_url.rstrip('/')}/rest/api/3/search/jql"},
            {"version": "v2", "url": f"{self.jira_url.rstrip('/')}/rest/api/2/search/jql"}
        ]

        response = None
        selected_version = "v3"
        
        for ep in endpoints:
            try:
                logger.info(f"[Jira] Thử kết nối API {ep['version']}: {ep['url']}")
                res = self.session.get(
                    ep["url"], 
                    headers=headers, 
                    auth=auth, 
                    params=params, 
                    timeout=self.timeout
                )
                
                if res.status_code == 200:
                    response = res
                    selected_version = ep["version"]
                    logger.info(f"✓ Kết nối thành công với Jira API {selected_version}")
                    break
                else:
                    logger.warning(f"⚠️ API {ep['version']} trả về HTTP {res.status_code}. Thử phương án tiếp theo...")
                    # Log response body for debugging (truncated)
                    if res.text:
                        logger.debug(f"  Response preview: {res.text[:200]}...")
                        
            except requests.exceptions.RequestException as e:
                logger.error(f"❌ Lỗi network khi gọi {ep['version']}: {type(e).__name__}: {e}")
            except Exception as e:
                logger.error(f"❌ Lỗi không mong đợi khi gọi {ep['version']}: {e}")

        if not response:
            logger.error("❌ Không thể lấy dữ liệu từ Jira sau khi thử tất cả endpoints.")
            return []

        try:
            data = response.json()
            cleaned_tasks = []
            
            # Extract issues array with fallback to "results" key
            raw_items = data.get("issues") or data.get("results") or []
            logger.debug(f"📦 Found {len(raw_items)} raw items in Jira response")
            
            for idx, item in enumerate(raw_items):
                # Smart unwrapping
                issue = self._unwrap_jira_issue(item)
                if not issue:
                    logger.warning(f"⚠️ Skip item #{idx}: không thể parse thành issue valid")
                    continue
                    
                key = issue.get("key", f"UNKNOWN-{idx}")
                fields_data = issue.get("fields", {})
                summary = fields_data.get("summary") or "No summary"
                
                # Parse description with ADF support
                description_obj = fields_data.get("description")
                description_text = self._parse_adf_description(description_obj)
                
                # Extract metadata
                status = fields_data.get("status", {}).get("name", "Unknown") if fields_data.get("status") else "Unknown"
                assignee = fields_data.get("assignee")
                assignee_name = assignee.get("displayName") if assignee and isinstance(assignee, dict) else "Chưa phân công"
                issue_type = fields_data.get("issuetype", {}).get("name", "Task") if fields_data.get("issuetype") else "Task"

                # Build semantic content optimized for RAG retrieval
                semantic_content = (
                    f"[Jira {issue_type} {key}] {summary}. "
                    f"Status: {status} | Assignee: {assignee_name} | "
                    f"Description: {description_text.strip()}"
                )
                
                cleaned_tasks.append({
                    "content": semantic_content,
                    "metadata": {
                        "source": f"jira/{key}", 
                        "type": "task",
                        "jira_key": key,
                        "status": status,
                        "assignee": assignee_name,
                        "issue_type": issue_type
                    }
                })
                
                # Log progress for monitoring (every 10 items to avoid spam)
                if (idx + 1) % 10 == 0 or idx == len(raw_items) - 1:
                    logger.info(f"📋 Progress: {idx + 1}/{len(raw_items)} tasks processed")
            
            logger.info(f"⚡ Success: Loaded {len(cleaned_tasks)}/{len(raw_items)} valid tasks from Jira (API {selected_version})")
            return cleaned_tasks

        except requests.exceptions.JSONDecodeError as e:
            logger.error(f"❌ Lỗi parse JSON từ Jira: {e}")
            logger.debug(f"  Raw response preview: {response.text[:500]}...")
            return []
        except Exception as e:
            logger.error(f"❌ Lỗi không mong đợi khi process Jira data: {type(e).__name__}: {e}")
            return []

    def fetch_live_confluence_pages(self, 
                                   custom_space: Optional[str] = None,
                                   limit: Optional[int] = None) -> List[Dict]:
        """
        Gọi API Confluence lấy các tài liệu từ Space chỉ định.
        
        Args:
            custom_space: Space key tùy chỉnh (default: từ env CONFLUENCE_SPACE_KEY)
            limit: Số trang tối đa fetch (default: self.max_results)
            
        Returns:
            List[Dict]: Danh sách pages đã được chuẩn hóa cho RAG
        """
        space_key = custom_space or self.confluence_space
        fetch_limit = limit or self.max_results
        
        if not self._validate_config("confluence"):
            return []

        url = f"{self.confluence_url.rstrip('/')}/wiki/api/v2/pages"
        headers = {"Accept": "application/json"}
        auth = HTTPBasicAuth(self.confluence_email, self.confluence_token)
        
        params = {
            "spaceKey": space_key,
            "body-format": "storage",  # Get raw storage format for reliable parsing
            "limit": fetch_limit,
            "expand": "body.storage"  # Ensure body content is included
        }

        try:
            logger.info(f"[Confluence] Fetching pages from space '{space_key}' (limit={fetch_limit})...")
            response = self.session.get(
                url, 
                headers=headers, 
                auth=auth, 
                params=params, 
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Confluence API error: HTTP {response.status_code}")
                if response.text:
                    logger.debug(f"  Response: {response.text[:300]}...")
                return []

            data = response.json()
            cleaned_pages = []
            results = data.get("results", [])
            
            logger.info(f"📦 Found {len(results)} pages in Confluence response")
            
            for idx, page in enumerate(results):
                title = page.get("title", "Untitled")
                page_id = page.get("id")
                
                # Extract body content from storage format
                body_storage = page.get("body", {}).get("storage", {})
                body_html = body_storage.get("value", "") if isinstance(body_storage, dict) else ""
                cleaned_body = self.clean_html(body_html)
                
                # Build semantic content
                semantic_content = f"[Confluence Page] {title}. Content: {cleaned_body[:2000]}"  # Truncate for RAG efficiency
                
                cleaned_pages.append({
                    "content": semantic_content,
                    "metadata": {
                        "source": f"confluence/{page_id}", 
                        "type": "policy",
                        "page_id": page_id,
                        "title": title,
                        "space_key": space_key
                    }
                })
                
                # Log every 5 pages for monitoring
                if (idx + 1) % 5 == 0:
                    logger.info(f"📄 Progress: {idx + 1}/{len(results)} pages processed")

            logger.info(f"⚡ Success: Loaded {len(cleaned_pages)} pages from Confluence space '{space_key}'")
            return cleaned_pages

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Network error fetching Confluence: {type(e).__name__}: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Unexpected error processing Confluence data: {type(e).__name__}: {e}")
            return []

    def health_check(self) -> Dict[str, bool]:
        """
        Kiểm tra kết nối đến cả Jira và Confluence.
        
        Returns:
            Dict[str, bool]: {"jira": True/False, "confluence": True/False}
        """
        results = {"jira": False, "confluence": False}
        
        # Check Jira
        if self._validate_config("jira"):
            try:
                url = f"{self.jira_url.rstrip('/')}/rest/api/3/myself"
                auth = HTTPBasicAuth(self.jira_email, self.jira_token)
                res = self.session.get(url, auth=auth, timeout=5)
                results["jira"] = (res.status_code == 200)
                logger.info(f"{'✓' if results['jira'] else '✗'} Jira health check: {res.status_code}")
            except Exception as e:
                logger.warning(f"✗ Jira health check failed: {e}")
        
        # Check Confluence
        if self._validate_config("confluence"):
            try:
                url = f"{self.confluence_url.rstrip('/')}/wiki/api/v2/user/me"
                auth = HTTPBasicAuth(self.confluence_email, self.confluence_token)
                res = self.session.get(url, auth=auth, timeout=5)
                results["confluence"] = (res.status_code == 200)
                logger.info(f"{'✓' if results['confluence'] else '✗'} Confluence health check: {res.status_code}")
            except Exception as e:
                logger.warning(f"✗ Confluence health check failed: {e}")
                
        return results