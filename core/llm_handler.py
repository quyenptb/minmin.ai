import os
import json
import time
import logging
import requests
from typing import Dict

logger = logging.getLogger("LLMHandler")

class LLMHandler:
    """
    Trái tim của Neuro-Sync MAS chứa 2 Đại lý (Agents) chuyên biệt.
    Đã được nâng cấp để sử dụng OpenAI (Codex/GPT) theo yêu cầu, 
    đảm bảo Deterministic Engineering (Luôn trả về JSON chuẩn).
    """
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        # Khuyên dùng gpt-4o-mini hoặc gpt-4o để tốc độ nhanh nhất trong Hackathon
        self.model_name = "gpt-4o-mini" 
        self.endpoint = "https://api.openai.com/v1/chat/completions"

    def _call_openai(self, system_prompt: str, user_prompt: str) -> dict:
        if not self.api_key:
            logger.error("OPENAI_API_KEY is missing. Vui lòng cấu hình trong file .env")
            return {}

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            # Tính năng tối thượng của OpenAI để ép LLM trả về JSON
            "response_format": {"type": "json_object"}
        }

        delay = 1.0
        for attempt in range(3):
            try:
                res = requests.post(self.endpoint, headers=headers, json=payload, timeout=20)
                if res.status_code == 200:
                    raw_text = res.json()["choices"][0]["message"]["content"]
                    return json.loads(raw_text)
                
                if res.status_code in [429, 500, 502, 503, 504]:
                    time.sleep(delay)
                    delay *= 2
                    continue
                else:
                    logger.error(f"OpenAI Error {res.status_code}: {res.text}")
                    break
            except Exception as e:
                logger.error(f"Network error calling OpenAI: {e}")
                time.sleep(delay)
                delay *= 2
        return {}

    # ==========================================
    # AGENT 1: CHATOPS PARSER (Slack -> Jira)
    # ==========================================
    def parse_teacher_command(self, raw_command: str) -> Dict:
        """Trích xuất thực thể từ câu nói của giáo viên thành data cấu trúc."""
        system_prompt = (
            "You are an NLP parser for an Individualized Education Program (IEP). "
            "Extract student name, completed goal, and new goal. "
            "Output MUST be valid JSON: {\"student_name\": \"str\", \"completed_goal\": \"str|null\", \"new_goal\": \"str\"}"
        )
        user_prompt = f"Teacher command: '{raw_command}'"
        
        result = self._call_openai(system_prompt, user_prompt)
        if not result:
            return {"student_name": "Unknown", "completed_goal": None, "new_goal": "Unspecified"}
        return result

    # ==========================================
    # AGENT 2: DIAGNOSTICIAN (Telemetry -> UI JSON)
    # ==========================================
    def diagnostician_reasoning(self, jira_context: str, confluence_context: str, telemetry_event: str) -> Dict:
        """Trả về JSON cấu hình UI dựa trên dữ liệu RAG và Telemetry."""
        system_prompt = (
            "You are the Diagnostician Agent in a Neuro-Sync System. "
            "Provide real-time UI/UX interventions for children with special educational needs. "
            "OUTPUT STRICTLY VALID JSON."
        )
        user_prompt = (
            f"INPUT DATA:\n"
            f"1. JIRA_CONTEXT (Task): {jira_context}\n"
            f"2. CONFLUENCE_CONTEXT (Profile): {confluence_context}\n"
            f"3. TELEMETRY_EVENT (Anomaly): {telemetry_event}\n\n"
            "Output schema:\n"
            "{\n"
            "  \"intervention_id\": \"INT-XYZ\",\n"
            "  \"reasoning\": \"Brief logical explanation\",\n"
            "  \"ui_state\": {\"theme_color\": \"#HexColor\", \"lottie_speed_multiplier\": 0.5, \"visual_complexity\": \"low\"},\n"
            "  \"slack_notification\": \"Vietnamese alert for teacher\"\n"
            "}"
        )

        result = self._call_openai(system_prompt, user_prompt)
        if not result:
            return {
                "intervention_id": "FALLBACK-01",
                "ui_state": {"theme_color": "#e2e8f0", "lottie_speed_multiplier": 0.5, "visual_complexity": "low"},
                "slack_notification": "Hệ thống tự động chuyển sang Calm Mode do mất kết nối AI."
            }
        return result