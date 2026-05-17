import os
import re
import logging
import requests
from requests.auth import HTTPBasicAuth

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AtlassianConnector")

class AtlassianConnector:
    """
    Connector chịu trách nhiệm gọi API Jira/Confluence trực tiếp.
    Đã cập nhật endpoint search sang /search/jql theo yêu cầu bắt buộc của Atlassian Cloud.
    Đã tăng limit lên 50 để tránh bỏ sót các trang tài liệu mới tạo do dính trang mẫu mặc định.
    """
    
    def __init__(self):
        # Đọc cấu hình Jira
        self.jira_url = os.getenv("JIRA_URL")
        self.jira_email = os.getenv("JIRA_EMAIL")
        self.jira_token = os.getenv("JIRA_API_TOKEN")
        self.jira_project = os.getenv("JIRA_PROJECT_KEY")

        # Đọc cấu hình Confluence
        self.confluence_url = os.getenv("CONFLUENCE_URL")
        self.confluence_email = os.getenv("CONFLUENCE_EMAIL")
        self.confluence_token = os.getenv("CONFLUENCE_API_TOKEN")
        self.confluence_space = os.getenv("CONFLUENCE_SPACE_KEY")

    def clean_html(self, html_content: str) -> str:
        """Lọc bỏ toàn bộ thẻ HTML rác từ Confluence để giữ lại text sạch."""
        if not html_content:
            return ""
        clean_text = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', html_content)
        clean_text = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', clean_text)
        clean_text = re.sub(r'<[^>]+?>', ' ', clean_text)
        clean_text = re.sub(r'\s+', ' ', clean_text)
        return clean_text.strip()

    def fetch_live_jira_tasks(self) -> list[dict]:
        """
        Gọi API Jira lấy các task trong Project chỉ định.
        Sử dụng endpoint /rest/api/3/search/jql để tránh lỗi HTTP 410.
        """
        if not all([self.jira_url, self.jira_email, self.jira_token, self.jira_project]):
            logger.warning("⚠️ Thiếu cấu hình Jira. Sẽ sử dụng Mock Data.")
            return []

        jql = f"project={self.jira_project}"
        headers = {"Accept": "application/json"}
        auth = HTTPBasicAuth(self.jira_email, self.jira_token)
        params = {"jql": jql, "maxResults": 50}

        # Định nghĩa các phương án endpoint mới thử nghiệm tuần tự (/search/jql)
        endpoints = [
            {"version": "v3", "url": f"{self.jira_url.rstrip('/')}/rest/api/3/search/jql"},
            {"version": "v2", "url": f"{self.jira_url.rstrip('/')}/rest/api/2/search/jql"}
        ]

        response = None
        selected_version = "v3"
        
        for ep in endpoints:
            try:
                logger.info(f"[Jira] Thử kết nối bằng API {ep['version']} (/search/jql)...")
                res = requests.get(ep["url"], headers=headers, auth=auth, params=params, timeout=5)
                
                if res.status_code == 200:
                    response = res
                    selected_version = ep["version"]
                    break
                else:
                    logger.warning(f"⚠️ API {ep['version']} trả về HTTP {res.status_code}. Thử phương án tiếp theo...")
            except Exception as e:
                logger.error(f"❌ Lỗi khi gọi endpoint {ep['version']}: {e}")

        if not response:
            logger.error("❌ Không thể lấy dữ liệu từ Jira bằng cả v3 và v2 với endpoint /search/jql.")
            return []

        try:
            data = response.json()
            cleaned_tasks = []
            for issue in data.get("issues", []):
                key = issue.get("key")
                fields = issue.get("fields", {})
                summary = fields.get("summary")
                
                description_text = ""
                description_obj = fields.get("description")
                
                # Xử lý định dạng mô tả dựa trên cấu trúc ADF của v3 hoặc văn bản thô của v2
                if selected_version == "v3" and isinstance(description_obj, dict):
                    content_nodes = description_obj.get("content", [])
                    for node in content_nodes:
                        for text_node in node.get("content", []):
                            if text_node.get("type") == "text":
                                description_text += text_node.get("text", "") + " "
                else:
                    description_text = str(description_obj) if description_obj else ""

                status = fields.get("status", {}).get("name", "Unknown")
                assignee = fields.get("assignee")
                assignee_name = assignee.get("displayName") if assignee else "Chưa phân công"

                semantic_content = (
                    f"[Jira Task {key}] Tiêu đề: {summary}. "
                    f"Trạng thái: {status}. Người thực hiện: {assignee_name}. "
                    f"Mô tả công việc: {description_text.strip()}"
                )
                
                cleaned_tasks.append({
                    "content": semantic_content,
                    "metadata": {"source": f"jira/{key}", "type": "task"}
                })
            
            logger.info(f"⚡ Đã tải thành công {len(cleaned_tasks)} task từ Jira Live (API {selected_version})!")
            return cleaned_tasks

        except Exception as e:
            logger.error(f"❌ Lỗi parse dữ liệu JSON từ Jira: {e}")
            return []

    def fetch_live_confluence_pages(self) -> list[dict]:
        """Gọi API Confluence lấy các tài liệu SOP văn hóa công ty."""
        if not all([self.confluence_url, self.confluence_email, self.confluence_token, self.confluence_space]):
            logger.warning("⚠️ Thiếu cấu hình Confluence. Sẽ sử dụng Mock Data.")
            return []

        url = f"{self.confluence_url.rstrip('/')}/wiki/api/v2/pages"
        headers = {"Accept": "application/json"}
        auth = HTTPBasicAuth(self.confluence_email, self.confluence_token)
        params = {
            "spaceKey": self.confluence_space,
            "body-format": "storage",
            "limit": 50  # Tăng lên 50 để tránh nuốt trang tài liệu mới của người dùng
        }

        try:
            response = requests.get(url, headers=headers, auth=auth, params=params, timeout=5)
            if response.status_code != 200:
                logger.error(f"❌ Confluence API trả về lỗi: {response.status_code}")
                return []

            data = response.json()
            cleaned_pages = []
            for page in data.get("results", []):
                title = page.get("title")
                page_id = page.get("id")
                body_html = page.get("body", {}).get("storage", {}).get("value", "")
                cleaned_body = self.clean_html(body_html)

                # Log chi tiết tên từng trang để kiểm tra trên màn hình log Render
                logger.info(f"📄 Đã nạp thành công trang Confluence: \"{title}\"")

                semantic_content = f"[Confluence Document] Tiêu đề: {title}. Nội dung quy trình: {cleaned_body}"
                cleaned_pages.append({
                    "content": semantic_content,
                    "metadata": {"source": f"confluence/{page_id}", "type": "policy"}
                })

            logger.info(f"⚡ Đã nạp thành công tổng cộng {len(cleaned_pages)} trang từ Confluence Live vào RAG!")
            return cleaned_pages

        except Exception as e:
            logger.error(f"❌ Lỗi kết nối Confluence API: {e}")
            return []