import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from adapters.slack_text_adapter import SlackTextAdapter
from slack_bolt.adapter.fastapi import SlackRequestHandler
from adapters.telemetry_adapter import router as telemetry_router
from adapters.lti_adapter import router as lti_router

app = FastAPI(
    title="Neuro-Sync MAS Backend",
    description="Multi-Agent System for Cognitive Load Balancing (LTI 1.3 Ready)",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Slack Adapter (Control Center)
slack_adapter = SlackTextAdapter()
slack_handler = SlackRequestHandler(slack_adapter.app)

# 2. Routers
app.include_router(telemetry_router)
app.include_router(lti_router)

@app.get("/")
def health_check():
    return {"status": "healthy", "system": "Neuro-Sync MAS"}

@app.post("/slack/events")
async def slack_events(req: Request):
    """Webhook cho Slack"""
    return await slack_handler.handle(req)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)