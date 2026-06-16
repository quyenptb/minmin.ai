import os
import logging
from slack_bolt import App
from core.llm_handler import LLMHandler
from core.jira_confluence_connector import AtlassianConnector

logger = logging.getLogger("SlackAdapter")

class SlackTextAdapter:
    """ChatOps cho Giáo viên. Zero-UI."""
    def __init__(self):
        self.app = App(
            token=os.getenv("SLACK_BOT_TOKEN"),
            signing_secret=os.getenv("SLACK_SIGNING_SECRET")
        )
        self.llm_handler = LLMHandler()
        self.jira_conn = AtlassianConnector()
        self.register_events()

    def register_events(self):
        @self.app.event("message")
        def handle_message(event, client, ack):
            ack()
            if event.get("bot_id"): return

            channel_id = event["channel"]
            raw_text = event.get("text", "")

            # 1. Báo đang xử lý
            tmp = client.chat_postMessage(channel=channel_id, text="🔄 Đang cấu hình lộ trình IEP...")
            
            # 2. Agent 1: Parse lệnh NLP
            parsed = self.llm_handler.parse_teacher_command(raw_text)
            
            # BEST PRACTICE: Tránh lỗi null/None khi LLM không trích xuất được thực thể (như khi nhắn "Hello")
            student = parsed.get("student_name") or "Học sinh"
            new_goal = parsed.get("new_goal") or "Chưa rõ mục tiêu cụ thể"
            
            # Nếu tin nhắn quá ngắn và không có thông tin hợp lệ, gán mặc định thông minh hơn
            if student == "Unknown" or new_goal == "Unspecified":
                student = "Học sinh"
                new_goal = f"Hỗ trợ học tập theo yêu cầu: '{raw_text}'"
            
            # 3. Headless Action: Tạo Jira Task (Không bao giờ gửi giá trị None/null gây sập API)
            jira_key = self.jira_conn.create_jira_task(
                summary=new_goal, 
                description=f"Auto-generated IEP goal for {student} based on request: '{raw_text}'", 
                assignee_name=student
            )

            # 4. Trả kết quả trực quan
            blocks = [{
                "type": "section",
                "text": {
                    "type": "mrkdwn", 
                    "text": f"✅ *Đã tiếp nhận yêu cầu học tập!*\n"
                            f"• *Học sinh:* {student}\n"
                            f"• *Mục tiêu:* {new_goal}\n"
                            f"• *Jira Ticket:* `{jira_key}`\n"
                            f"_Hệ thống Neuro-Sync sẵn sàng giám sát trạng thái nhận thức của trẻ._"
                }
            }]
            client.chat_update(channel=channel_id, ts=tmp["ts"], text="Done", blocks=blocks)