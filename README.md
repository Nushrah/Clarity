# Clarity

**AI-powered manager decision-support platform for workforce talent decisions**

![Python](https://img.shields.io/badge/python-3.12+-blue.svg)
![LangGraph](https://img.shields.io/badge/framework-LangGraph-orange.svg)
![OpenRouter](https://img.shields.io/badge/LLM-OpenRouter-green.svg)
![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688.svg)
![React](https://img.shields.io/badge/frontend-React-61dafb.svg)
![MUI](https://img.shields.io/badge/UI-Material--UI-007fff.svg)

## Overview

Clarity is a full-stack AI manager decision-support platform built with FastAPI, React, LangGraph, OpenRouter, SQLite, and ChromaDB. It uses a multi-agent workflow to analyze a 5-person team's capability gaps, recommend hire/promote/upskill actions, process resumes against structured rubrics, detect possible bias in workforce decisions, trigger manager reflection, and learn the manager's recurring decision patterns over time.

**Decision-support only** — the system never auto-hires, auto-rejects, or auto-promotes. All decisions require manager review and logging.

## Quick Start

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # Add your OpenRouter API key
python scripts/seed_team_data.py
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### OpenRouter setup

This project uses OpenRouter as the hosted LLM provider.

Create `backend/.env`:

```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key_here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_FREE_MODEL=openrouter/free
APP_URL=http://localhost:5173
LLM_TEMPERATURE=0.2
LLM_MAX_RETRIES=3
```

Never commit `backend/.env`.

## Multi-Agent Workflow

| Agent | Purpose |
|-------|---------|
| Team Gap Analysis | Analyze team capabilities, gaps, and parse resumes |
| Bias Signal Detection | Detect unconscious bias in workforce decisions |
| Fairness Policy Check | Validate against workforce fairness rules |
| Decision Synthesis | ReAct-style final recommendation |
| Manager Reflection | Pause for manager reflection when bias risk is high |
| Manager Pattern Scoring | Detect recurring manager bias patterns |
| Decision Reconsideration | Handle reconsideration requests |
| Decision Logging | Log decisions to SQLite + ChromaDB |
| Quick Decision Check | Fast single-pass review for short manager notes |

## Key API Routes

- `POST /api/talent/decisions/submit` — Submit workforce decision
- `GET /api/talent/reflections/queue` — Pending manager reflections
- `POST /api/talent/reflections/{id}/submit` — Submit reflection
- `POST /api/talent/resumes/upload` — Upload resume (PDF/DOCX/TXT)
- `GET /api/talent/team/members` — Get 5-person team
- `POST /api/talent/gap-analysis/run` — Run gap analysis
- `GET /api/talent/analytics/summary` — Analytics dashboard

Legacy content moderation routes remain for backward compatibility.

## Seeded Team

- **Manager:** Aisha Rahman (`mgr_001`)
- **Team:** Product Engineering Alpha (`team_alpha`) — 5 members
  - Maya Chen (Frontend, L2)
  - Daniel Wong (Backend, L2)
  - Sara Ahmed (Full-stack, L3)
  - Leo Martin (Data Engineer, L2)
  - Priya Nair (QA Automation, L2)

## Environment Variables

```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key_here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_FREE_MODEL=openrouter/free
APP_URL=http://localhost:5173
ENABLE_QUICK_DECISION_CHECK=true
QUICK_CHECK_DECISION_TYPES=quick_manager_note
QUICK_CHECK_MAX_LENGTH=300
```

## Technology Stack

- **Backend:** FastAPI, LangGraph, OpenRouter, SQLite, ChromaDB
- **Frontend:** React, Vite, Material-UI
- **Resume parsing:** pypdf, python-docx
