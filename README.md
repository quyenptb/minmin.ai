# minmin.ai

**A Cognitive Load Balancer for Special Education**

minmin.ai is an adaptive learning system designed for children with special educational needs, especially students with ASD and ADHD.

Digital learning environments often expose these students to excessive sensory input, which can cause cognitive overload, distress, and meltdowns. At the same time, teachers often have to work with complex software when trying to personalize learning activities for each student.

minmin.ai addresses both problems through:

- A **zero-UI teacher experience** powered by Slack.
- A **self-healing interactive frontend** for students.
- A **Multi-Agent System** that monitors student telemetry and adjusts the UI state in real time.
- Safe, deterministic UI adaptation through structured JSON configuration instead of raw code generation.

---

## System Architecture

minmin.ai uses three dedicated micro-agents to keep the system stable, modular, and predictable.

### Sentinel Agent

The Sentinel Agent runs on the student device.

It monitors interaction telemetry using a sliding window algorithm and detects signs of cognitive overload, such as erratic or rapid tapping behavior.

Responsibilities:

- Track student interactions in real time.
- Calculate taps per second.
- Detect anomalous behavior patterns.
- Trigger backend alerts when overload signals are detected.

### Diagnostician Agent

The Diagnostician Agent is a backend OpenAI-powered processor.

It reads contextual learning and student data from external systems, then produces a strict JSON configuration for UI adaptation.

Inputs:

- The student's current learning objective from Jira.
- The student's psychological profile from Confluence.
- Telemetry alerts from the Sentinel Agent.

Output:

- A deterministic JSON payload describing UI adjustments.

Example adaptations may include:

- Reducing visual complexity.
- Switching to a calmer color palette.
- Simplifying the current learning task.
- Adjusting interaction pacing.

### Orchestrator Agent

The Orchestrator Agent is a FastAPI backend service that coordinates the full workflow.

Responsibilities:

- Receive telemetry alerts from the frontend.
- Query the Diagnostician Agent.
- Push the updated UI state back to the frontend.
- Notify the teacher through Slack.
- Coordinate Jira and Confluence integrations.

---

## Integration Layer

### LTI 1.3 Advantage

minmin.ai supports LTI 1.3 Advantage and OIDC login flows.

This allows the application to plug directly into enterprise Learning Management Systems such as:

- MaivenPoint
- Moodle
- Other LTI-compliant LMS platforms

The application does not require standalone authentication when launched from a supported LMS.

### Headless State Machine

minmin.ai uses Jira as a backend engine for tracking Individualized Education Programs.

Teachers do not interact with Jira directly. Instead, they use natural language commands in Slack. The system parses these commands and manages the relevant Jira tickets in the background.

Example teacher command:

```text
Configure a counting lesson for Min
```

The system can then create or update the appropriate learning objective automatically.

---

## Local Development Setup

### Prerequisites

Make sure the following are installed or available:

- Python 3.12+
- OpenAI API key
- Slack bot token
- Atlassian account with Jira and Confluence access
- Ngrok for local webhook testing

---

## Installation

Clone the repository and install the required dependencies:

```bash
pip install -r requirements.txt
```

---

## Environment Configuration

Create a `.env` file in the root directory and add the following variables:

```env
OPENAI_API_KEY=sk-your-key

SLACK_BOT_TOKEN=xoxb-your-token
SLACK_SIGNING_SECRET=your-secret
HUMAN_BUDDY_CHANNEL_ID=your-channel-id

JIRA_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email
JIRA_API_TOKEN=your-jira-token
JIRA_PROJECT_KEY=IEP

CONFLUENCE_URL=https://your-domain.atlassian.net
CONFLUENCE_EMAIL=your-email
CONFLUENCE_API_TOKEN=your-confluence-token
CONFLUENCE_SPACE_KEY=SEN

PORT=8000
```

---

## Running the Server

Start the FastAPI application:

```bash
python main.py
```

By default, the server runs on:

```text
http://localhost:8000
```

---

## Testing the System

You can test the full local pipeline through three main workflows.

### 1. ChatOps Workflow

Expose your local FastAPI server with ngrok:

```bash
ngrok http 8000
```

Then configure your Slack app Event Subscriptions URL to point to your ngrok domain.

Send a message to the Slack bot, for example:

```text
Configure a counting lesson for Min
```

Expected behavior:

1. The bot receives the teacher command.
2. The Orchestrator Agent parses the request.
3. A background Jira ticket is created or updated.
4. The relevant learning objective is stored for later adaptation.

---

### 2. LMS Integration

Use the Saltire LTI 1.3 Platform Emulator to test the LTI launch flow.

Configure the emulator with your ngrok domain for:

- Initiate login URL
- Redirection URI

After launching the tool, the interactive frontend should load securely through the LTI 1.3 handshake.

---

### 3. Telemetry and Adaptation

Once the frontend is loaded, rapidly tap on the screen to simulate signs of cognitive overload.

Expected behavior:

1. The Sentinel Agent detects abnormal tapping behavior.
2. A telemetry alert is sent to the backend webhook.
3. The Orchestrator Agent requests a UI recommendation from the Diagnostician Agent.
4. The Diagnostician Agent returns a strict JSON configuration.
5. The frontend updates itself immediately.
6. The UI reduces visual complexity and shifts to a calmer visual state.

---

## Example UI Adaptation Payload

The Diagnostician Agent should return structured JSON rather than executable code.

Example:

```json
{
  "visualComplexity": "low",
  "colorPalette": "calm",
  "animationLevel": "minimal",
  "taskDifficulty": "reduced",
  "teacherAlert": true,
  "reason": "Rapid repeated tapping detected within the sliding window threshold."
}
```

---

## Project Goals

minmin.ai aims to make digital learning safer and more adaptive for students with special educational needs.

The core goals are:

- Reduce cognitive overload during digital learning.
- Give teachers a simple natural-language workflow.
- Adapt the student interface in real time.
- Avoid fragile runtime code generation.
- Integrate with existing education infrastructure.
- Support individualized learning plans through Jira and Confluence.

---

## Tech Stack

- **Backend:** FastAPI
- **AI Processor:** OpenAI API
- **Teacher Interface:** Slack Bot
- **Learning Objective Tracking:** Jira
- **Student Profile Storage:** Confluence
- **LMS Integration:** LTI 1.3 Advantage
- **Local Webhook Testing:** Ngrok

---

## Repository Structure

A typical project structure may look like this:

```text
minmin.ai/
├── main.py
├── requirements.txt
├── .env
├── app/
│   ├── agents/
│   │   ├── sentinel.py
│   │   ├── diagnostician.py
│   │   └── orchestrator.py
│   ├── integrations/
│   │   ├── slack.py
│   │   ├── jira.py
│   │   ├── confluence.py
│   │   └── lti.py
│   ├── routes/
│   │   ├── telemetry.py
│   │   ├── slack_events.py
│   │   └── lti_launch.py
│   └── models/
│       └── ui_state.py
└── README.md
```

Adjust this structure based on the actual repository implementation.

---

## Security Notes

Do not commit secrets or API tokens to version control.

Make sure `.env` is included in `.gitignore`:

```gitignore
.env
__pycache__/
*.pyc
```

For production deployments, use a secure secret manager instead of local environment files.

---

## License

Add your project license here.

Example:

```text
MIT License
```
