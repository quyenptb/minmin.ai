import os
import logging
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from slack_sdk import WebClient
from core.llm_handler import LLMHandler
from core.rag_engine import SimpleRAGEngine

logger = logging.getLogger("TelemetryAdapter")
router = APIRouter()

llm_handler = LLMHandler()
rag_engine = SimpleRAGEngine()

class TelemetryEvent(BaseModel):
    student_id: str
    anomaly_type: str
    taps_per_second: float

def send_slack_alert(message: str):
    token = os.getenv("SLACK_BOT_TOKEN")
    channel = os.getenv("HUMAN_BUDDY_CHANNEL_ID")
    if token and channel:
        try: WebClient(token=token).chat_postMessage(channel=channel, text=f"🚨 *[Neuro-Sync Alert]*\n{message}")
        except: pass

@router.post("/api/v1/telemetry/overload")
async def handle_telemetry(event: TelemetryEvent, bg_tasks: BackgroundTasks):
    """Orchestrator Agent nhận tín hiệu và điều phối xử lý."""
    logger.info(f"Anomaly detected for {event.student_id}: {event.taps_per_second} taps/s")

    # 1. RAG Context
    rag_docs = rag_engine.search(event.student_id)
    jira_ctx = next((d["content"] for d in rag_docs if d.get("type") == "task"), "Đang làm bài tập.")
    conf_ctx = next((d["content"] for d in rag_docs if d.get("type") == "profile"), "Hồ sơ bình thường.")

    # 2. Diagnostician Agent -> JSON
    telemetry_str = f"{event.anomaly_type} detected ({event.taps_per_second} taps/s)."
    ui_config = llm_handler.diagnostician_reasoning(jira_ctx, conf_ctx, telemetry_str)

    # 3. Notify Teacher
    msg = ui_config.get("slack_notification", "Đã tự động can thiệp giao diện.")
    bg_tasks.add_task(send_slack_alert, msg)

    # 4. Return UI State to iPad
    return {
        "status": "success",
        "intervention": ui_config
    }