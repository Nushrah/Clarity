# Clarity - Complete End-to-End Architecture

## 🎯 System Overview

This document provides a comprehensive view of Clarity — a manager decision-support platform for one manager and one 5-person team. It covers workforce gap analysis, hire/promote/upskill recommendations, resume screening, bias detection, manager reflection, and pattern learning across all components, databases, and workflows.

---

## 📑 Table of Contents

1. [📊 High Level Architecture](#📊-high-level-architecture-diagram)
2. [🔧 Backend Module Overview](#🔧-backend-module-overview)
3. [🤖 AI/ML Models & Embedding Systems](#🤖-aiml-models--embedding-systems)
4. [🔄 Complete Workforce Decision Flow](#-complete-workforce-decision-flow)
5. [📐 Sequence Diagrams](#📐-sequence-diagrams)
6. [🗄️ Database Schema Details](#🗄️-database-schema-details)
7. [📈 System Performance Metrics](#📈-system-performance-metrics)
8. [🔐 Security & Privacy](#🔐-security--privacy)
9. [🚀 Deployment Architecture](#🚀-deployment-architecture)
10. [⚙️ Configuration](#⚙️-configuration)
11. [📊 Complete Flow Summary](#📊-complete-flow-summary)

---

## 📊 High Level Architecture Diagram

![End-to-End Architecture](images/end-to-end-architecture-content-moderation.png)
---

## 🔧 Backend Module Overview

### 📁 Backend Structure

```
backend/
├── main.py                          # FastAPI application & REST endpoints
├── src/
│   ├── core/
│   │   ├── models.py                # TalentDecisionState & type definitions
│   │   ├── llm_provider.py          # OpenRouter LLM client (get_llm)
│   │   ├── llm_retry.py             # Retry wrapper for LLM calls
│   │   └── llm_schemas.py           # Pydantic schemas for LLM responses
│   ├── api/
│   │   └── talent_routes.py         # Clarity REST routes
│   ├── agents/
│   │   ├── agents.py                # 9 ClarityTalentAgents implementations
│   │   ├── workflow.py              # LangGraph workflow orchestration
│   │   ├── reasoning.py             # ReAct decision synthesis logic
│   │   └── tool_manager.py          # Tool management for agents
│   ├── database/
│   │   ├── moderation_db.py         # TalentDecisionDatabase (SQLite)
│   │   └── auth_db.py               # User authentication database
│   ├── memory/
│   │   ├── memory.py                # TalentDecisionMemoryManager (ChromaDB)
│   │   ├── agent_episodic_memory.py # Episode-level memory
│   │   ├── agent_semantic_memory.py # Pattern learning
│   │   └── learning_tracker.py      # Decision outcome tracking
│   ├── ml/
│   │   ├── ml_classifier.py         # Optional ML classifiers
│   │   ├── keyword_detectors.py     # Keyword-based detection
│   │   └── guardrails.py            # Safety guardrails
│   └── utils/
│       ├── tools.py                 # Utility functions
│       ├── json_utils.py            # LLM JSON response parsing
│       ├── resume_parser.py         # PDF/DOCX/TXT resume extraction
│       ├── evaluation.py            # Model evaluation metrics
│       └── observability.py         # Logging and monitoring
```

---

### 1. Core Modules (`src/core/`)

#### `models.py`
**Purpose**: Central data model definitions for workforce decisions

**Key Components**:
- `TalentDecisionState` (TypedDict): Main state object passed through all agents
- `AgentDecision` (Dataclass): Individual agent decision record
- `ManagerProfile` / `TeamMemberProfile`: Manager and team member data
- Enums: `TalentDecisionStatus`, `TalentDecisionType`, `BiasRiskLevel`, `FairnessPolicyCategory`, `ManagerPatternTier`

**Usage**: Every module imports types from here for type safety

---

#### `llm_provider.py`
**Purpose**: Central OpenRouter LLM client

**Key Components**:
- `get_llm(model_type)`: Returns configured `ChatOpenAI` pointed at OpenRouter
- Reads `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `OPENROUTER_FREE_MODEL` from environment

**Usage**: All agents initialize LLM via `get_llm()` — no Gemini dependency

---

#### `llm_retry.py`
**Purpose**: Resilient LLM invocation with exponential backoff

**Key Components**:
- `invoke_llm(llm, prompt)`: Wraps `llm.invoke()` with tenacity retry (3 attempts)

**Usage**: All agent LLM calls go through `invoke_llm()` for rate-limit resilience

---

#### `llm_schemas.py`
**Purpose**: Pydantic schemas for structured LLM outputs

**Key Components**:
- `TopicExtractionResponse`: Structured topic extraction
- `ToxicityAnalysisResponse`: Toxicity detection output
- `parse_llm_response()`: Parse and validate LLM JSON responses
- `create_structured_prompt()`: Format prompts for structured outputs

**Usage**: Agents use these to get reliable, parseable outputs from LLMs

---

### 2. Agent Modules (`src/agents/`)

#### `agents.py` — `ClarityTalentAgents`
**Purpose**: Implementation of 9 specialized workforce decision agents

**Key Agents**:
1. **Team Gap Analysis Agent**: Analyzes team capabilities, gaps, and parses resumes
2. **Bias Signal Detection Agent**: Detects bias signals in workforce decisions
3. **Fairness Policy Check Agent**: Validates against workforce fairness rules
4. **Decision Synthesis Agent**: ReAct-style final recommendation (Think-Act-Observe)
5. **Manager Reflection Agent**: Pauses workflow when bias risk or low confidence is high
6. **Manager Pattern Scoring Agent**: Detects recurring manager bias patterns
7. **Decision Reconsideration Agent**: Handles reconsideration requests
8. **Decision Logging Agent**: Logs decisions to SQLite + ChromaDB
9. **Quick Decision Check Agent**: Single-pass review for short manager notes

**Usage**: Called by [workflow.py](backend/src/agents/workflow.py) in sequence based on routing logic

---

#### `workflow.py`
**Purpose**: LangGraph workflow orchestration

**Key Functions**:
- `create_talent_decision_workflow()`: Builds the state graph
- `process_talent_decision()`: Executes workflow for a workforce decision
- `resume_from_reflection()`: Resumes paused workflow after manager reflection
- `should_use_quick_decision_check()`: Determines quick-check eligibility
- Routing functions: Direct flow between agents based on state

**Usage**: [main.py](backend/main.py) creates workflow on startup, calls it for each talent decision

---

#### `reasoning.py`
**Purpose**: ReAct (Think-Act-Observe) decision synthesis logic

**Key Functions**:
- Think phase: Analyzes all agent decisions
- Act phase: Makes final consolidated recommendation
- Observe phase: Evaluates manager reflection triggers and confidence
- Consensus calculation: Weights agent agreements

**Usage**: Called by Decision Synthesis Agent to synthesize multi-agent outputs

---

### 3. Database Modules (`src/database/`)

#### `moderation_db.py` — `TalentDecisionDatabase`
**Purpose**: All talent decision database operations

**Key Tables**:
- `teams`, `team_members`: Manager team roster
- `talent_decision_logs`: Logged workforce decisions
- `candidate_resumes`: Uploaded resume records
- `manager_bias_patterns`: Recurring bias pattern tracking
- `training_recommendations`: Adaptive training modules
- Legacy tables retained for backward compatibility

**Key Operations**:
- `save_talent_decision_log()`: Persist decision audit trail
- `get_team_members()`: Retrieve 5-person team
- `save_candidate_resume()`: Store parsed/anonymized resume
- `get_talent_decision_history()`: Decision timeline for manager

**Usage**: Called by agents and `/api/talent/*` endpoints

---

#### `auth_db.py`
**Purpose**: User authentication and management

**Key Tables**:
- `users`: User accounts with credentials
- `user_profiles`: Extended profile information
- `sessions`: Active user sessions

**Key Operations**:
- `create_user()`: Register new user
- `authenticate_user()`: Verify credentials
- `update_user_role()`: Change user permissions
- `get_all_users()`: Admin user management

**Usage**: Called by authentication endpoints and user management APIs

---

### 4. Memory Modules (`src/memory/`)

#### `memory.py` — `TalentDecisionMemoryManager`
**Purpose**: ChromaDB-based memory management

**Key Collections**:
- `talent_decisions`: Historical workforce decisions
- `manager_bias_patterns`: Recurring manager bias patterns
- `manager_decision_history`: Manager decision history
- `resume_screening_decisions`: Resume screening outcomes

**Key Operations**:
- `store_talent_decision()`: Save decision for pattern learning
- `retrieve_similar_decisions_for_agent()`: Find similar past decisions
- `get_manager_decision_history()`: Get manager's past decisions

**Usage**: Agents store and retrieve decisions for pattern learning

---

#### `learning_tracker.py`
**Purpose**: Track decision outcomes and learn from appeals

**Key Functions**:
- `record_decision()`: Log agent decision with metadata
- `update_outcome()`: Update when decision is appealed
- `get_success_rate()`: Calculate agent accuracy
- `analyze_patterns()`: Identify learning opportunities

**Usage**: Called by agents to enable continuous improvement from feedback

---

### 5. ML Modules (`src/ml/`)

#### `ml_classifier.py`
**Purpose**: ML-based toxicity detection using transformer models

**Supported Models**:
- DistilBERT Toxic (default)
- HateBERT (hate speech specialist)
- Toxic BERT (multi-category)
- RoBERTa Hate (robust detection)

**Key Functions**:
- `load_models()`: Initialize transformer models
- `predict_toxicity()`: Get toxicity predictions
- `ensemble_predict()`: Combine multiple model predictions

**Usage**: Optional - used by Toxicity Detection Agent if `USE_ML_MODELS=true`

---

#### `keyword_detectors.py`
**Purpose**: Fast keyword-based toxicity detection (default)

**Key Functions**:
- `keyword_toxicity_detection()`: Pattern matching for toxic phrases
- `keyword_hate_speech_detection()`: Detect hate speech patterns
- Built-in pattern libraries for common violations

**Usage**: Default toxicity detection method (fast, no ML dependencies)

---

#### `guardrails.py`
**Purpose**: Safety guardrails for AI agent behavior

**Key Features**:
- Loop detection (max 10 iterations)
- Hallucination detection (contradiction checking)
- Cost budget tracking
- Execution time limits
- Consistency validation across agents

**Usage**: Wraps all agent functions to ensure safe, bounded execution

---

### 6. Main Application (`main.py`)

#### `main.py`
**Purpose**: FastAPI REST API server

**Key Endpoints**:

**Authentication**:
- `POST /api/auth/login`: User login
- `POST /api/auth/register`: New user registration
- `PUT /api/auth/password`: Update password

**Talent Decision API** (`/api/talent/*`):
- `POST /api/talent/decisions/submit`: Submit workforce decision
- `POST /api/talent/gap-analysis/run`: Run team gap analysis
- `POST /api/talent/resumes/upload`: Upload resume (PDF/DOCX/TXT)
- `GET /api/talent/reflections/queue`: Pending manager reflections
- `POST /api/talent/reflections/{id}/submit`: Submit manager reflection
- `POST /api/talent/reconsiderations/submit`: Submit reconsideration
- `GET /api/talent/team/members`: Get 5-person team
- `GET /api/talent/decisions/history`: Decision audit log
- `GET /api/talent/analytics/*`: Gap, bias, pattern, resume metrics

**Legacy endpoints** (backward compatible):
- `POST /api/content/submit`, `GET /api/hitl/queue`, `POST /api/appeals/submit`

**Usage**: Entry point for all frontend interactions

---

## 🤖 AI/ML Models & Embedding Systems

This section clarifies the different AI models and embedding systems used throughout the platform.

### 🧠 OpenRouter LLM (Primary Hosted AI Engine)

**Model**: `openrouter/free` via [OpenRouter API](https://openrouter.ai/api/v1)

OpenRouter is used as the primary hosted LLM provider because it offers free-tier models and is more suitable for Hong Kong access than alternatives like Groq or OpenRouter.

**Usage Locations** (all via `get_llm()` + `invoke_llm()`):

1. **Team Gap Analysis Agent** ([agents.py](backend/src/agents/agents.py))
   - Capability gap identification
   - Team skill mapping
   - Resume profile extraction (structured JSON)

2. **Bias Signal Detection Agent**
   - Bias risk scoring
   - Bias category detection (affinity, visibility, prestige, culture-fit, etc.)
   - Reflection trigger evaluation

3. **Fairness Policy Check Agent**
   - Workforce fairness rule validation
   - Hire/promote/upskill recommendation generation
   - Resume rubric scoring

4. **Decision Synthesis Agent**
   - ReAct reasoning loop (Think-Act-Observe)
   - Multi-agent output aggregation
   - Final recommendation with confidence scoring

5. **Manager Pattern Scoring Agent**
   - Recurring bias pattern detection across manager history
   - Adaptive training recommendations

6. **Decision Reconsideration Agent**
   - Reconsideration request evaluation
   - Uphold/revise/overturn decisions

7. **Quick Decision Check Agent**
   - Fast single-pass review for short manager notes

**API Configuration**:
```python
# backend/.env — never commit this file
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key_here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_FREE_MODEL=openrouter/free
APP_URL=http://localhost:5173
LLM_TEMPERATURE=0.2
LLM_MAX_RETRIES=3

# LLM client initialization (backend/src/core/llm_provider.py)
from langchain_openai import ChatOpenAI

def get_llm(model_type: str = "default") -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("OPENROUTER_FREE_MODEL", "openrouter/free"),
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
        max_retries=0,
        default_headers={
            "HTTP-Referer": os.getenv("APP_URL", "http://localhost:5173"),
            "X-Title": "Clarity",
        },
    )

# Agent usage (backend/src/core/llm_retry.py)
from src.core.llm_retry import invoke_llm
response = invoke_llm(self.llm, prompt)
result = extract_json_from_llm_response(response)
```

**Retry & Error Handling**:
- `invoke_llm()` retries up to 3 times with exponential backoff (1–12s)
- Talent routes return HTTP 503 if OpenRouter is unavailable or rate-limited
- No `GOOGLE_API_KEY` or Gemini dependency required

**Cost per Request** (free tier):
- Quick Decision Check (1 LLM call): $0.00 on `openrouter/free`
- Full Pipeline (4–7 LLM calls): $0.00 on `openrouter/free`
- Reconsideration (2 LLM calls): $0.00 on `openrouter/free`

---

### 🔍 ChromaDB Vector Embeddings (Memory System)

**Embedding Function**: ChromaDB Default (sentence-transformers/all-MiniLM-L6-v2)

**NOT using a cloud embedding API** - The memory system uses ChromaDB's built-in embedding function for:
- Fast local embedding generation
- No API call overhead
- Cost-free vector operations
- Consistent semantic search

**Implementation** ([memory.py:45-60](content-moderation-system/backend/src/memory/memory.py#L45-L60)):
```python
from chromadb import PersistentClient, Settings

# Initialize ChromaDB with default embedding function
self.client = chromadb.PersistentClient(
    path=persist_directory,
    settings=Settings(
        anonymized_telemetry=False,
        allow_reset=True
    )
)

# Collections use ChromaDB default embeddings
self.decisions_collection = self.client.get_or_create_collection(
    name="talent_decisions",
    metadata={"description": "Historical talent decisions and outcomes"}
    # No embedding_function specified = uses ChromaDB default
)
```

**Vector Collections**:

1. **talent_decisions**
   - **Documents**: Historical workforce decisions and outcomes
   - **Embeddings**: 384-dim vectors (sentence-transformers)
   - **Purpose**: Find similar past decisions for consistency
   - **Query Example**: "Find decisions similar to current gap analysis"

2. **manager_bias_patterns**
   - **Documents**: Recurring manager bias patterns
   - **Embeddings**: 384-dim vectors
   - **Purpose**: Pattern matching and adaptive training triggers
   - **Query Example**: "Check if manager shows repeated prestige bias"

3. **manager_decision_history**
   - **Documents**: Manager decision history and context
   - **Embeddings**: 384-dim vectors
   - **Purpose**: Manager pattern scoring and trend analysis
   - **Query Example**: "Retrieve manager's historical hiring decisions"

**Embedding Dimensions**: 384 (all-MiniLM-L6-v2) or 768 (depending on ChromaDB version)

**Performance**:
- Embedding Generation: <10ms locally
- Similarity Search: <50ms for typical queries
- No API latency or costs

---

### 🛡️ ML Toxicity Detection Models (Optional)

**Framework**: HuggingFace Transformers

**Activation**: Set `USE_ML_MODELS=true` in environment variables

**Supported Models** ([ml_classifier.py:25-45](content-moderation-system/backend/src/ml/ml_classifier.py#L25-L45)):

1. **DistilBERT Toxic** (default)
   - Model: `unitary/toxic-bert`
   - Categories: toxic, severe_toxic, obscene, threat, insult, identity_hate
   - Speed: Fast (~50-100ms inference)

2. **HateBERT**
   - Model: `GroNLP/hateBERT`
   - Specialization: Hate speech detection
   - Performance: High precision on hate speech

3. **Toxic BERT**
   - Model: `unitary/multilingual-toxic-xlm-roberta`
   - Features: Multi-language support
   - Languages: 100+ languages

4. **RoBERTa Hate**
   - Model: `facebook/roberta-hate-speech-dynabench-r4-target`
   - Features: Robust against adversarial examples
   - Use case: Production-grade hate detection

**Default Mode**: Keyword-based detection ([keyword_detectors.py](content-moderation-system/backend/src/ml/keyword_detectors.py))
- No ML model loading required
- Fast pattern matching (~1-5ms)
- Built-in toxic phrase libraries
- Good for basic toxicity screening

---

### 📊 AI/ML Architecture Summary

```
┌─────────────────────────────────────────────────────────────┐
│              WORKFORCE DECISION SUBMISSION                   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │  Quick Decision Check │
         │  (note ≤ 300 chars)   │
         └───────┬───────────────┘
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
   [Quick Check]     [Full Pipeline]
        │                 │
        ▼                 ▼
┌───────────────┐  ┌──────────────────────┐
│ OpenRouter    │  │  9 Agent Pipeline    │
│ 1 LLM call    │  │  OpenRouter LLM      │
│ Bias scan     │  │  4–7 LLM calls total │
└───────┬───────┘  └──────┬───────────────┘
        │                 │
        │                 ▼
        │          ┌─────────────────────┐
        │          │ ChromaDB Query      │
        │          │ (Default Embeddings)│
        │          │ - Similar decisions │
        │          │ - Bias patterns     │
        │          │ - Manager history   │
        │          └──────┬──────────────┘
        │                 │
        └────────┬────────┘
                 │
                 ▼
         ┌───────────────┐
         │ Recommendation│
         │ + Bias Audit  │
         └───────┬───────┘
                 │
                 ▼
         ┌───────────────────┐
         │ Store in ChromaDB │
         │ (Pattern Learning)│
         └───────────────────┘
```

**Key Distinctions**:
- **OpenRouter**: Hosted LLM for reasoning, gap analysis, bias detection, and decision synthesis
- **ChromaDB Embeddings**: Vector storage and similarity search for manager pattern learning
- **HuggingFace Models**: Optional ML classifiers (disabled by default)
- **Resume Parser**: Local PDF/DOCX/TXT extraction with anonymization

---

### Component Interaction Diagrams

#### Database Interactions

```
           ┌──────────────┐
           │   Agents     │
           └──────┬───────┘
                  │
                  │ Read/Write
                  ↓
┌────────────────────────────────────────┐
│ moderation_db.py                       │
│ ─────────────────────────────────────  │
│ Operations:                            │
│ • store_content_submission()           │
│ • update_story_moderation()            │
│ • get_user_violations()                │
│ • record_agent_execution()             │
└────────────────┬───────────────────────┘
                 │
                 │ SQL Operations
                 ↓
┌────────────────────────────────────────┐
│ SQLite Database                        │
│ databases/moderation_data.db           │
│ ─────────────────────────────────────  │
│ Tables:                                │
│ • content_submissions                  │
│ • stories                              │
│ • story_comments                       │
│ • agent_executions                     │
│ • policy_violations                    │
│ • user_actions                         │
└────────────────────────────────────────┘
```

#### Memory System Interactions

```
            ┌──────────────┐
            │   Agents     │
            └──────┬───────┘
                   │
                   │ Store/Retrieve Decisions
                   ↓
┌────────────────────────────────────────┐
│ memory.py (TalentDecisionMemoryManager)    │
│ ─────────────────────────────────────  │
│ Methods:                               │
│ • store_talent_decision()              │
│ • retrieve_similar_decisions_for_agent()│
│ • get_manager_decision_history()       │
└─────────────────┬──────────────────────┘
                  │
                  │ Vector Operations
                  ↓
┌────────────────────────────────────────┐
│ ChromaDB                               │
│ databases/chroma_moderation_db/        │
│ ─────────────────────────────────────  │
│ Collections:                           │
│ • talent_decisions                 │
│ • flagged_patterns                     │
│ • user_violations                      │
│                                        │
│ Used for:                              │
│ • Finding similar past content         │
│ • Learning from patterns               │
│ • Improving agent decisions            │
└────────────────────────────────────────┘
```

#### LLM Interactions

```
            ┌──────────────┐
            │   Agents     │
            └──────┬───────┘
                   │
                   │ LLM Calls
                   ↓
┌────────────────────────────────────────┐
│ OpenRouter API                      │
│ ─────────────────────────────────────  │
│ Used for:                              │
│ • Content analysis                     │
│ • Topic extraction                     │
│ • Policy checking                      │
│ • ReAct synthesis                      │
│ • Appeal review                        │
│ • Action reason generation             │
│                                        │
│ Full Pipeline: 6-8 LLM calls           │
│ Quick Decision Check: 1 LLM call                  │
└────────────────────────────────────────┘
```

---

## 🔄 Complete Workforce Decision Flow

> **Note:** Detailed step-by-step flows below describe the original content-moderation submission paths retained for reference. The active Clarity pipeline uses the 9-agent workforce workflow documented in [Configuration](#-configuration) and routes via `/api/talent/*`. All LLM calls in both paths use **OpenRouter** via `get_llm()` + `invoke_llm()`.

### Story 1: User Submits a Story (Happy Path - Auto-Approved)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: USER SUBMISSION                                                 │
└──────────────────────────────────────────────────────────────────────────┘

1. User Login
   ├─> User enters credentials on frontend
   ├─> POST /api/auth/login
   │   Body: { username: "john_doe", password: "****" }
   │
   ├─> Auth Database Query
   │   └─> SELECT * FROM users WHERE username=? AND password_hash=?
   │
   └─> Response: { session_token: "abc123...", user_info: {...} }

2. Story Submission
   ├─> User writes story in text editor
   ├─> User clicks "Submit Story"
   ├─> POST /api/stories/submit
   │   Headers: { Authorization: "Bearer abc123..." }
   │   Body: {
   │     title: "My Amazing Day at the Park",
   │     content: "I had a wonderful time at the park today...",
   │     user_id: "user_12345",
   │     author_name: "John Doe"
   │   }
   │
   └─> API validates token and user

┌──────────────────────────────────────────────────────────────────────────┐
│ PHASE 2: CONTENT PROCESSING INITIALIZATION                               │
└──────────────────────────────────────────────────────────────────────────┘

3. Workflow Initialization
   ├─> Generate content_id: "story_1733334567_abc"
   │
   ├─> Create TalentDecisionState object:
   │   {
   │     content_id: "story_1733334567_abc",
   │     content_type: "story",
   │     content_text: "I had a wonderful time...",
   │     user_id: "user_12345",
   │     author_name: "John Doe",
   │     metadata: {
   │       title: "My Amazing Day at the Park",
   │       submission_timestamp: "2025-12-04T10:30:00Z"
   │     },
   │     user_profile: {
   │       reputation_score: 0.85,
   │       total_violations: 0,
   │       account_age_days: 365
   │     },
   │     status: "pending",
   │     decisions: []
   │   }
   │
   └─> Invoke LangGraph Workflow: process_content(state)

┌──────────────────────────────────────────────────────────────────────────┐
│ PHASE 3: MULTI-AGENT AI ANALYSIS                                         │
└──────────────────────────────────────────────────────────────────────────┘

4. Entry Router Decision
   ├─> Check: content_type == "story"
   ├─> Check: ENABLE_FAST_MODE = true
   ├─> Check: len(content) = 450 chars > 200 (FAST_MODE_MAX_LENGTH)
   │
   └─> Route: "content_analysis" (Full Pipeline)
       ⚠️  Story too long for fast mode - using full analysis

5. Agent 1: Content Analysis Agent
   ┌────────────────────────────────────────────────────────┐
   │ Execution Time: ~2 seconds                             │
   ├────────────────────────────────────────────────────────┤
   │ 1. Call OpenRouter API (LLM)                        │
   │    Prompt: "Analyze this content for sentiment..."     │
   │    Response: {                                         │
   │      sentiment: "positive",                            │
   │      topics: ["leisure", "outdoor activities"],        │
   │      category: "personal_story"                        │
   │    }                                                   │
   │                                                        │
   │ 2. Query ChromaDB for Similar Content                  │
   │    └─> retrieve_similar_content(text)                  │
   │        Found: 3 similar approved stories               │
   │                                                        │
   │ 3. Initial Toxicity Check                              │
   │    └─> keyword_toxicity_detection(text)                │
   │        Result: toxicity_score = 0.05 (very low)        │
   │                                                        │
   │ 4. Make Decision                                       │
   │    Decision: APPROVE                                   │
   │    Confidence: 0.92                                    │
   │    Reasoning: "Positive personal story, no red flags"  │
   └────────────────────────────────────────────────────────┘
   │
   └─> Update TalentDecisionState.decisions[]
       └─> Add AgentDecision record

6. Agent 2: Toxicity Detection Agent
   ┌────────────────────────────────────────────────────────┐
   │ Execution Time: ~1.5 seconds                           │
   ├────────────────────────────────────────────────────────┤
   │ 1. Keyword-Based Detection (Default)                   │
   │    └─> keyword_toxicity_detection(text)                │
   │        • Profanity score: 0.0                          │
   │        • Hate speech: None detected                    │
   │        • Harassment patterns: None                     │
   │                                                        │
   │ 2. Calculate Overall Toxicity                          │
   │    toxicity_score = 0.03                               │
   │    toxicity_level = "none"                             │
   │                                                        │
   │ 3. Make Decision                                       │
   │    Decision: APPROVE                                   │
   │    Confidence: 0.95                                    │
   │    Reasoning: "No toxic content detected"              │
   └────────────────────────────────────────────────────────┘
   │
   └─> Update TalentDecisionState

7. Agent 3: Policy Violation Agent
   ┌────────────────────────────────────────────────────────┐
   │ Execution Time: ~2 seconds                             │
   ├────────────────────────────────────────────────────────┤
   │ 1. Call OpenRouter API                              │
   │    Prompt: "Check for policy violations..."            │
   │    Community Guidelines:                               │
   │    • No hate speech                                    │
   │    • No harassment                                     │
   │    • No spam/misinformation                            │
   │    • No sexual/violent content                         │
   │    • No illegal activity                               │
   │                                                        │
   │ 2. LLM Analysis Result                                 │
   │    {                                                   │
   │      violations: [],                                   │
   │      violation_severity: "none",                       │
   │      explanation: "Content follows all guidelines"     │
   │    }                                                   │
   │                                                        │
   │ 3. Make Decision                                       │
   │    Decision: APPROVE                                   │
   │    Confidence: 0.88                                    │
   │    Reasoning: "No policy violations found"             │
   └────────────────────────────────────────────────────────┘
   │
   └─> Update TalentDecisionState

8. Agent 4: ReAct Decision Loop (Synthesis)
   ┌────────────────────────────────────────────────────────┐
   │ Execution Time: ~2.5 seconds                           │
   ├────────────────────────────────────────────────────────┤
   │ THINK PHASE:                                           │
   │ ───────────────────────────────────────────────────────│
   │ 1. Gather all agent decisions                          │
   │    • Agent 1: APPROVE (conf: 0.92)                     │
   │    • Agent 2: APPROVE (conf: 0.95)                     │
   │    • Agent 3: APPROVE (conf: 0.88)                     │
   │                                                        │
   │ 2. Calculate consensus                                 │
   │    Consensus = 100% (all agree on APPROVE)             │
   │    Avg Confidence = (0.92 + 0.95 + 0.88) / 3 = 0.917   │
   │                                                        │
   │ 3. Identify conflicts                                  │
   │    Conflicts: None                                     │
   │                                                        │
   │ ACT PHASE:                                             │
   │ ───────────────────────────────────────────────────────│
   │ 4. Call LLM for synthesis                              │
   │    Prompt: "Synthesize final decision..."              │
   │    All agents recommend approval                       │
   │                                                        │
   │ 5. Generate final decision                             │
   │    Final Decision: APPROVE                             │
   │    Final Confidence: 0.92                              │
   │                                                        │
   │ OBSERVE PHASE:                                         │
   │ ───────────────────────────────────────────────────────│
   │ 6. Evaluate Manager Reflection triggers (8 conditions)               │
   │    ✗ Low confidence (<70%)? No (92%)                  │
   │    ✗ High severity violation? No                      │
   │    ✗ Conflicting decisions (<60% consensus)? No       │
   │    ✗ High-profile user? No                            │
   │    ✗ Sensitive content? No                            │
   │    ✗ Potential false positive? No                     │
   │    ✗ First offense + severe? No                       │
   │    ✗ Legal concern? No                                │
   │                                                        │
   │ 7. Manager Reflection decision                                       │
   │    hitl_required = False                               │
   │    hitl_trigger_reasons = []                           │
   └────────────────────────────────────────────────────────┘
   │
   └─> Update TalentDecisionState

9. Route Decision: Manager Reflection Not Required
   └─> Proceed to: user_reputation_scoring

10. Agent 5b: User Reputation Scoring Agent
    ┌────────────────────────────────────────────────────────┐
    │ Execution Time: ~1 second                              │
    ├────────────────────────────────────────────────────────┤
    │ 1. Query User History from Database                    │
    │    └─> get_user_violations(user_id="user_12345")       │
    │        Result: violations = []                         │
    │                                                        │
    │ 2. Calculate Reputation Metrics                        │
    │    • Account age: 365 days                             │
    │    • Total submissions: 24                             │
    │    • Approved: 24, Removed: 0                          │
    │    • Approval rate: 100%                               │
    │    • Previous violations: 0                            │
    │                                                        │
    │ 3. Compute Reputation Score                            │
    │    reputation_score = 0.85 (Good standing)             │
    │    user_risk_score = 0.05 (Very low risk)              │
    │                                                        │
    │ 4. Make Decision                                       │
    │    Decision: APPROVE                                   │
    │    Confidence: 0.90                                    │
    │    Reasoning: "Trusted user with clean history"        │
    └────────────────────────────────────────────────────────┘
    │
    └─> Update TalentDecisionState

11. Agent 6: Action Enforcement Agent
    ┌────────────────────────────────────────────────────────┐
    │ Execution Time: ~1.5 seconds                           │
    ├────────────────────────────────────────────────────────┤
    │ 1. Determine final action                              │
    │    final_decision = "approve"                          │
    │    final_confidence = 0.92                             │
    │                                                        │
    │ 2. Generate user-friendly reason (LLM)                 │
    │    Prompt: "Generate approval message..."              │
    │    Response: "Your story has been approved!"           │
    │                                                        │
    │ 3. Execute Actions:                                    │
    │    ├─> Update story visibility = "public"              │
    │    ├─> Set moderation_status = "approved"              │
    │    ├─> Generate notification message                   │
    │    └─> Record action timestamp                         │
    │                                                        │
    │ 4. Store decision in ChromaDB memory                   │
    │    └─> store_moderation_decision(state)                │
    │        Stored for future pattern learning              │
    │                                                        │
    │ 5. Update databases                                    │
    │    └─> See Phase 4 below                               │
    └────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│ PHASE 4: DATABASE PERSISTENCE                                            │
└──────────────────────────────────────────────────────────────────────────┘

12. Database Operations (All executed together)

    A. Moderation Database (moderation_data.db)

       Table: content_submissions
       INSERT INTO content_submissions VALUES (
         content_id: "story_1733334567_abc",
         content_type: "story",
         content_text: "I had a wonderful time...",
         user_id: "user_12345",
         author_name: "John Doe",
         final_decision: "approve",
         confidence_score: 0.92,
         processing_time_ms: 10500,
         hitl_required: false,
         created_at: "2025-12-04T10:30:00Z",
         updated_at: "2025-12-04T10:30:11Z"
       )

       Table: stories
       INSERT INTO stories VALUES (
         story_id: "story_1733334567_abc",
         title: "My Amazing Day at the Park",
         content: "I had a wonderful time...",
         author_id: "user_12345",
         author_name: "John Doe",
         moderation_status: "approved",
         visibility: "public",
         created_at: "2025-12-04T10:30:00Z",
         approved_at: "2025-12-04T10:30:11Z"
       )

       Table: agent_executions (6 records inserted)
       For each agent:
       INSERT INTO agent_executions VALUES (
         execution_id: "exec_...",
         content_id: "story_1733334567_abc",
         agent_name: "content_analysis_agent",
         decision: "approve",
         confidence: 0.92,
         reasoning: "Positive personal story...",
         execution_time_ms: 2000,
         timestamp: "2025-12-04T10:30:01Z"
       )

    B. ChromaDB Vector Memory

       Collection: talent_decisions
       ADD document:
       {
         id: "story_1733334567_abc",
         text: "I had a wonderful time...",
         metadata: {
           decision: "approve",
           confidence: 0.92,
           topics: ["leisure", "outdoor activities"],
           toxicity_score: 0.03,
           user_reputation: 0.85
         },
         embedding: [0.234, -0.145, ...] (768-dim vector)
       }

┌──────────────────────────────────────────────────────────────────────────┐
│ PHASE 5: USER NOTIFICATION & RESPONSE                                    │
└──────────────────────────────────────────────────────────────────────────┘

13. API Response to Frontend
    └─> POST /api/stories/submit
        Status: 200 OK
        Body: {
          success: true,
          content_id: "story_1733334567_abc",
          status: "approved",
          message: "Your story has been approved and is now public!",
          moderation_result: {
            decision: "approve",
            confidence: 0.92,
            processing_time_ms: 10500,
            reviewed_by: "AI_System"
          }
        }

14. Frontend Updates
    ├─> Display success notification
    ├─> Redirect to story page
    └─> Story is immediately visible to all users

┌──────────────────────────────────────────────────────────────────────────┐
│ SUMMARY: Happy Path - Auto-Approved Story                                │
└──────────────────────────────────────────────────────────────────────────┘

Total Processing Time: ~10.5 seconds
LLM API Calls: 4 (Content Analysis, Policy Check, ReAct Synthesis, Action Reason)
Agents Executed: 6 agents
Database Writes: 8 operations
Final Status: Approved ✅
User Impact: Story published immediately
```

---

### 🔴 Story 2: User Submits Toxic Comment (Removal Path)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ SCENARIO: User posts a toxic comment that violates community guidelines  │
└──────────────────────────────────────────────────────────────────────────┘

1. Comment Submission
   POST /api/stories/story_123/comments
   Body: {
     content: "This is stupid. You're an idiot for posting this garbage.",
     user_id: "user_99999",
     story_id: "story_123"
   }

2. Quick Decision Check Check
   ├─> len(content) = 68 chars < 200 ✅
   ├─> content_type = "story_comment" ✅
   └─> Route: "fast_mode" (Single-agent processing)

3. Quick Decision Check Agent Execution
   ┌────────────────────────────────────────────────────────┐
   │ Execution Time: ~1.2 seconds                           │
   ├────────────────────────────────────────────────────────┤
   │ 1. Single LLM call with combined analysis              │
   │                                                        │
   │ 2. Toxicity Detection                                  │
   │    └─> keyword_toxicity_detection()                    │
   │        Detected: "stupid", "idiot", "garbage"          │
   │        toxicity_score = 0.72 (High)                    │
   │                                                        │
   │ 3. Policy Check                                        │
   │    Violation: Harassment/Bullying                      │
   │    Severity: Medium                                    │
   │                                                        │
   │ 4. User History Check                                  │
   │    get_user_violations("user_99999")                   │
   │    Found: 2 previous warnings                          │
   │                                                        │
   │ 5. Decision                                            │
   │    Decision: REMOVE                                    │
   │    Confidence: 0.88                                    │
   │    Reasoning: "Contains harassment. Repeat offender."  │
   │                                                        │
   │ 6. User Action                                         │
   │    └─> Apply 7-day suspension (3rd violation)          │
   └────────────────────────────────────────────────────────┘

4. Action Enforcement
   ├─> Delete comment from database
   ├─> Update user: suspended = true, suspended_until = +7 days
   ├─> Generate notification
   └─> Store in memory for learning

5. Database Updates

   Table: story_comments
   INSERT ... moderation_status = "removed"

   Table: policy_violations
   INSERT (user_id="user_99999", violation_type="harassment", severity="medium")

   Table: user_actions
   INSERT (user_id="user_99999", action="suspend", duration_days=7, reason="Repeated harassment")

6. API Response
   Status: 200 OK
   Body: {
     success: false,
     status: "removed",
     message: "Your comment violates our harassment policy and has been removed.",
     user_action: {
       type: "suspension",
       duration_days: 7,
       reason: "Repeated policy violations",
       appeal_allowed: true
     }
   }

Total Processing Time: ~1.2 seconds ⚡
Decision: Removed + 7-day suspension ❌
```

---

### ⏸️ Story 3: Content Requires Human Review (Manager Reflection Path)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ SCENARIO: Borderline case requiring human judgment                       │
└──────────────────────────────────────────────────────────────────────────┘

1. Story Submission
   POST /api/stories/submit
   Body: {
     title: "My Views on Recent Elections",
     content: "I think the recent election was unfair. Many people believe..."
   }

2. Multi-Agent Analysis
   • Agent 1 (Content Analysis): FLAG (conf: 0.68) - Sensitive political content
   • Agent 2 (Toxicity): APPROVE (conf: 0.75) - Low toxicity
   • Agent 3 (Policy): WARN (conf: 0.62) - Potential misinformation

3. ReAct Decision Loop
   ┌────────────────────────────────────────────────────────┐
   │ THINK: Agents disagree (consensus = 33%)               │
   │ ACT: Synthesize → FLAG                                 │
   │ OBSERVE: Check Manager Reflection triggers                           │
   │                                                        │
   │ ✓ Low confidence: 0.68 < 0.70                          │
   │ ✓ Conflicting decisions: consensus 33% < 60%           │
   │ ✓ Sensitive content: political topic                   │
   │                                                        │
   │ Result: hitl_required = TRUE                           │
   └────────────────────────────────────────────────────────┘

4. Manager Reflection Checkpoint Agent
   ┌────────────────────────────────────────────────────────┐
   │ 1. Calculate priority score                            │
   │    • Low confidence: +30                               │
   │    • Conflicting decisions: +40                        │
   │    • Sensitive content: +50                            │
   │    Total: 120 points → CRITICAL priority               │
   │                                                        │
   │ 2. Prepare review packet                               │
   │    • Content text                                      │
   │    • All agent decisions + reasoning                   │
   │    • User context                                      │
   │    • Similar past cases                                │
   │                                                        │
   │ 3. Add to Manager Reflection queue in database                       │
   │    INSERT INTO hitl_queue VALUES (...)                 │
   │                                                        │
   │ 4. Pause workflow using LangGraph checkpointer         │
   │    └─> Workflow state saved, execution paused          │
   └────────────────────────────────────────────────────────┘

5. Workflow Paused - Wait for Human
   Status: PENDING_HUMAN_REVIEW

   └─> Store state in memory:
       hitl_pending_reviews["story_1733334567_xyz"] = TalentDecisionState

6. API Response (Immediate)
   Status: 202 Accepted
   Body: {
     success: true,
     status: "pending_review",
     message: "Your story is under review by our moderation team.",
     estimated_review_time: "< 1 hour"
   }

7. Moderator Reviews (Separate Session)

   A. Moderator Login
      └─> GET /api/hitl/queue
          Returns: [
            {
              content_id: "story_1733334567_xyz",
              priority: "critical",
              submitted_at: "2025-12-04T14:30:00Z",
              ai_recommendation: "flag",
              reason: "Conflicting AI decisions, sensitive content"
            }
          ]

   B. Moderator Reviews Content
      └─> GET /api/hitl/review/story_1733334567_xyz
          Returns full review packet with all AI analysis

   C. Moderator Makes Decision
      └─> POST /api/hitl/review/story_1733334567_xyz
          Body: {
            decision: "approve",
            reviewer_name: "Moderator Sarah",
            notes: "Factual discussion, no misinformation detected",
            confidence_override: 0.95
          }

8. Resume Workflow
   ┌────────────────────────────────────────────────────────┐
   │ resume_from_hitl() called                              │
   │                                                        │
   │ 1. Retrieve saved state from checkpointer              │
   │ 2. Update state with human decision                    │
   │    • hitl_human_decision = "approve"                   │
   │    • reviewer_name = "Moderator Sarah"                 │
   │    • hitl_resolution_timestamp = now()                 │
   │                                                        │
   │ 3. Route to action_enforcement                         │
   │ 4. Workflow continues from pause point                 │
   └────────────────────────────────────────────────────────┘

9. Action Enforcement
   └─> Apply human decision (approve)
   └─> Publish story
   └─> Notify user: "Your story has been reviewed and approved"

10. Learning Update
    └─> Store in memory: Human overrode AI flag → approve
    └─> System learns: Similar political content may be acceptable

Total Time: Variable (depends on moderator availability)
Manager Reflection ensures quality on edge cases ✅
```

---

### 📝 Story 4: User Appeals a Removal Decision

```
┌──────────────────────────────────────────────────────────────────────────┐
│ SCENARIO: User appeals removed content                                   │
└──────────────────────────────────────────────────────────────────────────┘

1. User Submits Appeal
   POST /api/appeals/submit
   Body: {
     content_id: "comment_12345",
     user_id: "user_99999",
     appeal_reason: "This was sarcasm, not actual harassment. Context was missed."
   }

2. Appeal Review Agent Execution
   ┌────────────────────────────────────────────────────────┐
   │ Execution Time: ~2.5 seconds                           │
   ├────────────────────────────────────────────────────────┤
   │ 1. Retrieve original content and decision              │
   │    └─> get_content_by_id("comment_12345")              │
   │        Original decision: REMOVE (toxicity detected)   │
   │                                                        │
   │ 2. Get user violation history                          │
   │    └─> get_user_violations("user_99999")               │
   │        Found: 2 previous warnings, 1 suspension        │
   │                                                        │
   │ 3. Analyze appeal with LLM                             │
   │    Prompt: "Review this appeal considering context"    │
   │    LLM Response: {                                     │
   │      appeal_valid: true,                               │
   │      confidence: 0.78,                                 │
   │      reasoning: "Sarcasm indicators present,           │
   │                  context supports user claim"          │
   │    }                                                   │
   │                                                        │
   │ 4. Make appeal decision                                │
   │    Decision: UPHOLD_APPEAL (restore content)           │
   │    Confidence: 0.78                                    │
   │                                                        │
   │ 5. Update databases                                    │
   │    • Restore comment visibility                        │
   │    • Reverse suspension                                │
   │    • Update violation count (-1)                       │
   │    • Record appeal outcome                             │
   │                                                        │
   │ 6. Learning update                                     │
   │    └─> Update patterns: Sarcasm detection improved     │
   └────────────────────────────────────────────────────────┘

3. Database Updates

   Table: appeals
   UPDATE appeals SET
     status = "upheld",
     reviewed_at = now(),
     reviewer = "appeal_review_agent"
   WHERE appeal_id = "appeal_789"

   Table: story_comments
   UPDATE story_comments SET
     moderation_status = "approved",
     visibility = "visible"
   WHERE comment_id = "comment_12345"

   Table: user_actions
   UPDATE user_actions SET
     reversed = true,
     reversal_reason = "Appeal upheld - context misunderstood"
   WHERE action_id = "action_456"

4. User Notification
   └─> Email/In-app: "Your appeal has been approved. Your comment has been restored."

5. System Learning
   └─> ChromaDB: Store appeal outcome for future reference
   └─> Update sarcasm detection patterns

Total Processing Time: ~2.5 seconds
Outcome: Appeal upheld, content restored ✅
Learning: System improved for similar cases
```

---

## 📐 Sequence Diagrams

### 1. Story Submission Flow

User → Frontend → API → Workflow → Agents → Database → Frontend → User

![Story Submission Sequence Diagram](images/story-submission-seq-diagram.png)

- **Processing Time:** 6-12 seconds (Full Pipeline)
- **LLM Calls:** 6-8 calls

---

### 2. Comment Submission Flow (Quick Decision Check)

User → Frontend → API → Workflow → Quick Decision Check Agent → Database → User

![Comment Submission Sequence Diagram](images/comment-submission-seq-diagram.png)

- **Processing Time:** 1-2 seconds (Quick Decision Check)
- **LLM Calls:** 1 call
- **Cost Savings:** 87.5% reduction

---

### 3. Full Multi-Agent Pipeline

```
Entry → Content Analysis → Toxicity → Policy → ReAct → Reputation → Action → END

                            ┌──────────────┐
                            │ Entry Router │
                            └──────┬───────┘
                                   │ content_type = "story"
                                   ↓
┌──────────────────────────────────────────────────────────────────────┐
│ AGENT 1: Content Analysis Agent                                      │
│ ──────────────────────────────────────────────────────────────────── │
│ • Sentiment analysis (positive/negative/neutral)                     │
│ • Topic extraction (using LLM)                                       │
│ • Category detection                                                 │
│ • Explicit content check                                             │
│ • Retrieve similar historical content from ChromaDB                  │
│ • Initial toxicity detection                                         │
│                                                                      │
│ Output: content_category, content_topics, sentiment                  │
│ Decision: APPROVE → continue | FLAG → END                            │
│ Confidence: 0.85                                                     │
└─────────────────────────────────┬────────────────────────────────────┘
                                  ↓
┌──────────────────────────────────────────────────────────────────────┐
│ AGENT 2: Toxicity Detection Agent                                    │
│ ──────────────────────────────────────────────────────────────────── │
│ • Calculate toxicity score (0.0-1.0)                                 │
│ • Detect profanity patterns                                          │
│ • Identify hate speech indicators                                    │
│ • Check for harassment/bullying                                      │
│ • Use ML models (if enabled) or keyword detection                    │
│                                                                      │
│ Thresholds:                                                          │
│   0.0-0.2: None → APPROVE                                            │
│   0.2-0.4: Low → MONITOR                                             │
│   0.4-0.6: Medium → FLAG                                             │
│   0.6-0.8: High → REMOVE                                             │
│   0.8-1.0: Severe → REMOVE + User Action                             │
│                                                                      │
│ Output: toxicity_score, toxicity_level, categories                   │
│ Decision: APPROVE | FLAG | REMOVE                                    │
│ Confidence: 0.80                                                     │
└──────────────────────────────┬───────────────────────────────────────┘
                               ↓
┌──────────────────────────────────────────────────────────────────────┐
│ AGENT 3: Policy Violation Agent                                      │
│ ──────────────────────────────────────────────────────────────────── │
│ • Check against community guidelines                                 │
│ • Identify specific violations:                                      │
│   - Hate speech, harassment, bullying                                │
│   - Spam, misinformation                                             │
│   - Sexual content, violence                                         │
│   - Self-harm, illegal activity                                      │
│ • Assess severity: low/medium/high/critical                          │
│                                                                      │
│ Output: policy_violations[], violation_severity                      │
│ Decision: APPROVE | WARN | REMOVE                                    │
│ Confidence: 0.75                                                     │
└──────────────────────────────┬───────────────────────────────────────┘
                               ↓
┌──────────────────────────────────────────────────────────────────────┐
│ AGENT 4: ReAct Decision Loop (Think-Act-Observe)                     │
│ ──────────────────────────────────────────────────────────────────── │
│ THINK Phase:                                                         │
│ • Analyze all 3 agent decisions                                      │
│ • Calculate consensus level (% agreement)                            │
│ • Compute average confidence                                         │
│ • Identify conflicts in recommendations                              │
│ • Run LLM synthesis on combined analysis                             │
│                                                                      │
│ ACT Phase:                                                           │
│ • Synthesize final decision                                          │
│ • Map to: APPROVE | WARN | REMOVE | SUSPEND | BAN                    │
│ • Calculate final confidence score                                   │
│                                                                      │
│ OBSERVE Phase:                                                       │
│ • Evaluate 8 Manager Reflection trigger conditions:                                │
│   1. Low confidence (<70%)                                           │
│   2. High severity violation (critical/high)                         │
│   3. Conflicting decisions (consensus <60%)                          │
│   4. High-profile user (10k+ followers)                              │
│   5. Sensitive content (politics/religion)                           │
│   6. Potential false positive                                        │
│   7. First offense + severe                                          │
│   8. Legal concern                                                   │
│                                                                      │
│ Output: react_act_decision, react_confidence, hitl_required          │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
                            ↓
                     ┌──────┴───────┐
                     │ Manager Reflection Needed? │
                     └──────┬───────┘
                            │
              ┌─────────────┴──────────────┐
              │ YES                      NO│
              ↓                            ↓
       ┌────────────────────┐      ┌────────────────────┐
       │ AGENT 5a:          │      │ AGENT 5b:          │
       │ Manager Reflection Checkpoint    │      │ User Reputation    │
       │                    │      │ Scoring Agent      │
       │ • Pause workflow   │      │                    │
       │ • Calculate        │      │ • Get user history │
       │   priority         │      │ • Count violations │
       │ • Add to queue     │      │ • Identify repeat  │
       │ • Wait for human   │      │   offenders        │
       │                    │      │ • Calculate risk   │
       │ Status: PENDING    │      │ • Update rep score │
       │                    │      │                    │
       │ [Workflow pauses   │      │ Output: user_      │
       │  until human       │      │ reputation_score,  │
       │  provides          │      │ user_risk_score    │
       │  decision via      │      │                    │
       │  /api/hitl/review] │      │ Decision: APPROVE  │
       │                    │      │ | WARN | REMOVE    │
       │                    │      │ | SUSPEND | BAN    │
       └────────┬───────────┘      └────────┬───────────┘
                │                           │
                │ Human Decision            │
                └─────────────┬─────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────────┐
│ AGENT 6: Action Enforcement Agent                                    │
│ ──────────────────────────────────────────────────────────────────── │
│ • Execute final moderation action                                    │
│ • Generate user-friendly reason (via LLM)                            │
│ • Update content visibility                                          │
│ • Apply user penalties if needed:                                    │
│   - WARN: Notify user, keep content                                  │
│   - REMOVE: Delete content, notify user                              │
│   - SUSPEND: Calculate duration, notify user                         │
│   - BAN: Permanent ban, notify user                                  │
│ • Store decision in ChromaDB memory                                  │
│ • Record audit log in database                                       │
│ • Update user profile (violations count, reputation)                 │
│                                                                      │
│ Output: action_timestamp, user_notified, content_removed             │
│ Decision: Always APPROVE (action completed)                          │
└───────────────────────────┬──────────────────────────────────────────┘
                            ↓
                        ┌───────┐
                        │  END  │
                        └───────┘
```

---

### 4. Manager Reflection Review Process

```
Agent Pause → Queue → Moderator → Decision → Resume → Complete

┌──────────────────────────────────────────────────────────────┐
│ Content triggers Manager Reflection (from ReAct Loop)                      │
│ • Low confidence: 65% (below 70% threshold)                  │
│ • Conflicting decisions: Agents disagree                     │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ↓
┌──────────────────────────────────────────────────────────────┐
│ Manager Reflection Checkpoint Agent                                        │
│ ──────────────────────────────────────────────────────────── │
│ 1. Calculate Priority Score:                                 │
│    • Low confidence: +30 points                              │
│    • High severity: +80 points                               │
│    • Conflicting decisions: +40 points                       │
│    • High-profile user: +60 points                           │
│    • Sensitive content: +50 points                           │
│    • Potential false positive: +45 points                    │
│    • First offense severe: +70 points                        │
│    • Legal concern: +100 points                              │
│                                                              │
│ 2. Assign Priority Level:                                    │
│    • Critical: 100+ points → Immediate review                │
│    • High: 75-99 points → <1 hour SLA                        │
│    • Medium: 50-74 points → <4 hours SLA                     │
│    • Low: 0-49 points → <24 hours SLA                        │
│                                                              │
│ 3. Prepare Review Packet:                                    │
│    • Content text                                            │
│    • All agent decisions + reasoning                         │
│    • Toxicity scores                                         │
│    • Policy violations                                       │
│    • User context (reputation, history)                      │
│    • ReAct synthesis                                         │
│                                                              │
│ 4. Add to Manager Reflection Queue (in database)                           │
│                                                              │
│ 5. Pause Workflow (using LangGraph checkpointer)             │
│                                                              │
│ Status: PENDING_HUMAN_REVIEW                                 │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         │ [Workflow is saved and paused]
                         │
                         ↓
┌──────────────────────────────────────────────────────────────┐
│ Moderator Dashboard                                          │
│ ──────────────────────────────────────────────────────────── │
│ 1. Moderator logs in                                         │
│                                                              │
│ 2. GET /api/hitl/queue                                       │
│    • Returns items sorted by priority                        │
│    • Shows pending count by priority level                   │
│                                                              │
│ 3. Moderator selects item                                    │
│                                                              │
│ 4. GET /api/hitl/review/{content_id}                         │
│    • Returns detailed review packet:                         │
│      - Content details                                       │
│      - AI analysis (all agents)                              │
│      - User context                                          │
│      - Suggested actions                                     │
│                                                              │
│ 5. Moderator Reviews:                                        │
│    • Reads content                                           │
│    • Reviews AI reasoning                                    │
│    • Checks user history                                     │
│    • Considers context                                       │
│                                                              │
│ 6. Moderator Makes Decision:                                 │
│    • APPROVE: Content is acceptable                          │
│    • WARN: Minor violation, warn user                        │
│    • REMOVE: Violates policy, remove                         │
│    • SUSPEND_USER: Suspend for X days                        │
│    • BAN_USER: Permanent ban                                 │
│    • ESCALATE: Needs senior review                           │
│                                                              │
│ 7. POST /api/hitl/review/{content_id}                        │
│    Body: {                                                   │
│      decision: "remove",                                     │
│      reviewer_name: "Moderator Jane",                        │
│      notes: "Clear harassment",                              │
│      confidence_override: 0.95                               │
│    }                                                         │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ↓
┌──────────────────────────────────────────────────────────────┐
│ Resume Workflow (resume_from_hitl)                           │
│ ──────────────────────────────────────────────────────────── │
│ 1. Retrieve saved state from checkpointer                    │
│                                                              │
│ 2. Update state with human decision:                         │
│    • hitl_human_decision = "remove"                          │
│    • hitl_human_notes = "Clear harassment"                   │
│    • reviewer_name = "Moderator Jane"                        │
│    • hitl_resolution_timestamp = now()                       │
│                                                              │
│ 3. Route based on human decision:                            │
│    • APPROVE → Action Enforcement → END                      │
│    • WARN/REMOVE → Action Enforcement → END                  │
│    • SUSPEND/BAN → Reputation Scoring → Action Enforcement   │
│    • ESCALATE → END (handled externally)                     │
│                                                              │
│ 4. Workflow continues from pause point                       │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ↓
┌──────────────────────────────────────────────────────────────┐
│ Action Enforcement Agent                                     │
│ ──────────────────────────────────────────────────────────── │
│ • Uses human decision as final authority                     │
│ • Executes action (remove content, notify user, etc.)        │
│ • Records in audit log: "Human Override"                     │
│ • Stores decision in memory for learning                     │
│ • If overturned AI decision, updates learning patterns       │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ↓
                     ┌───────┐
                     │  END  │
                     └───────┘

Total Time: Variable (depends on moderator availability)
Manager Reflection adds human judgment to edge cases and low-confidence decisions
```

---

### 5. Appeal Workflow

User Appeal → Review Agent → Decision → Database → Notify User

![Appeal Workflow](images/appeal-workflow-seq-diagram.png)

- **Appeal Processing Time:** 2-3 seconds
- **Outcome:** Content restored if appeal successful
- **Learning:** System learns from overturned decisions to improve future accuracy

---

## 🗄️ Database Schema Details

### Database 1: Auth Database (moderation_auth.db)

```sql
-- User Management
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL,  -- 'moderator', 'senior_moderator', 'admin'
    email TEXT,
    phone TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_login TEXT
);

-- Session Management
CREATE TABLE user_sessions (
    session_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT,
    ip_address TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Audit Trail
CREATE TABLE audit_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    content_id TEXT,
    details TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    ip_address TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Moderator Performance
CREATE TABLE moderator_stats (
    user_id INTEGER PRIMARY KEY,
    total_reviews INTEGER DEFAULT 0,
    approved_count INTEGER DEFAULT 0,
    removed_count INTEGER DEFAULT 0,
    warned_count INTEGER DEFAULT 0,
    escalated_count INTEGER DEFAULT 0,
    avg_response_time_seconds REAL DEFAULT 0,
    accuracy_score REAL DEFAULT 0,
    last_updated TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
```

### Database 2: Moderation Database (moderation_data.db)

```sql
-- Content Submissions (All content processed)
CREATE TABLE content_submissions (
    content_id TEXT PRIMARY KEY,
    content_type TEXT NOT NULL,  -- 'story', 'story_comment'
    content_text TEXT NOT NULL,
    user_id TEXT NOT NULL,
    author_name TEXT,
    final_decision TEXT,  -- 'approve', 'warn', 'remove', 'suspend', 'ban'
    confidence_score REAL,
    processing_time_ms INTEGER,
    hitl_required INTEGER DEFAULT 0,
    hitl_reviewer TEXT,
    hitl_notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    metadata TEXT  -- JSON blob
);

-- Stories
CREATE TABLE stories (
    story_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    author_id TEXT NOT NULL,
    author_name TEXT,
    moderation_status TEXT,  -- 'pending', 'approved', 'removed'
    visibility TEXT,  -- 'public', 'hidden', 'deleted'
    toxicity_score REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    approved_at TEXT,
    removed_at TEXT
);

-- Comments
CREATE TABLE story_comments (
    comment_id TEXT PRIMARY KEY,
    story_id TEXT NOT NULL,
    content TEXT NOT NULL,
    author_id TEXT NOT NULL,
    author_name TEXT,
    moderation_status TEXT,
    visibility TEXT,
    toxicity_score REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (story_id) REFERENCES stories(story_id)
);

-- Agent Execution Logs
CREATE TABLE agent_executions (
    execution_id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    decision TEXT,
    confidence REAL,
    reasoning TEXT,
    execution_time_ms INTEGER,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT,
    FOREIGN KEY (content_id) REFERENCES content_submissions(content_id)
);

-- Policy Violations
CREATE TABLE policy_violations (
    violation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    violation_type TEXT NOT NULL,  -- 'hate_speech', 'harassment', 'spam', etc.
    severity TEXT,  -- 'low', 'medium', 'high', 'critical'
    detected_by TEXT,  -- 'ai_agent' or moderator name
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (content_id) REFERENCES content_submissions(content_id)
);

-- User Actions (Warnings, Suspensions, Bans)
CREATE TABLE user_actions (
    action_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    action_type TEXT NOT NULL,  -- 'warn', 'suspend', 'ban'
    reason TEXT,
    duration_days INTEGER,  -- NULL for permanent bans
    applied_by TEXT,  -- Agent or moderator name
    applied_at TEXT DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT,
    reversed INTEGER DEFAULT 0,
    reversal_reason TEXT
);

-- Appeals
CREATE TABLE appeals (
    appeal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    appeal_reason TEXT NOT NULL,
    status TEXT DEFAULT 'pending',  -- 'pending', 'upheld', 'denied'
    reviewed_by TEXT,
    review_notes TEXT,
    submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TEXT,
    FOREIGN KEY (content_id) REFERENCES content_submissions(content_id)
);

-- Manager Reflection Queue
CREATE TABLE hitl_queue (
    queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id TEXT NOT NULL,
    priority TEXT,  -- 'critical', 'high', 'medium', 'low'
    priority_score INTEGER,
    trigger_reasons TEXT,  -- JSON array
    ai_recommendation TEXT,
    status TEXT DEFAULT 'pending',  -- 'pending', 'in_progress', 'completed'
    assigned_to TEXT,
    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    FOREIGN KEY (content_id) REFERENCES content_submissions(content_id)
);
```

### Database 3: ChromaDB Vector Memory

```python
# Collections in ChromaDB

Collection: "talent_decisions"
├─ Documents: Historical moderation decisions
├─ Embeddings: 768-dimensional vectors (ChromaDB default embedding function)
├─ Metadata: {
│    decision: "approve/remove/warn",
│    confidence: 0.0-1.0,
│    topics: ["topic1", "topic2"],
│    toxicity_score: 0.0-1.0,
│    user_reputation: 0.0-1.0,
│    timestamp: "ISO8601"
│  }
└─ Used for: Finding similar past content decisions

Collection: "flagged_patterns"
├─ Documents: Patterns of flagged content
├─ Metadata: {
│    pattern_type: "hate_speech/harassment/etc",
│    severity: "low/medium/high",
│    frequency: count
│  }
└─ Used for: Pattern learning and detection

Collection: "user_violations"
├─ Documents: User violation history
├─ Metadata: {
│    user_id: "user_12345",
│    violation_type: "harassment",
│    timestamp: "ISO8601"
│  }
└─ Used for: User risk scoring
```

**Embedding Model Details:**
- **Embedding Function**: ChromaDB default (typically sentence-transformers/all-MiniLM-L6-v2)
- **Vector Dimensions**: 384 or 768 dimensions (depending on ChromaDB version)
- **Purpose**: Semantic similarity search for historical content retrieval
- **Performance**: Fast local embedding generation without API calls

---

## 📈 System Performance Metrics

### Processing Time Comparison

| Scenario | Mode | Agents | LLM Calls | Time | Cost/Request |
|----------|------|--------|-----------|------|--------------|
| Short comment (<200 chars) | Quick Decision Check | 1 | 1 | 1-2s | $0.0002 |
| Long comment (>200 chars) | Full Pipeline | 6 | 4 | 6-12s | $0.0016 |
| Story submission | Full Pipeline | 6 | 4 | 6-12s | $0.0016 |
| Manager Reflection case | Full + Human | 6 + Human | 4 | Variable | $0.0016 + Human time |
| Appeal review | Appeal Agent | 1 | 2 | 2-3s | $0.0005 |

### Throughput Estimates

- **Quick Decision Check**: ~500-1000 comments/minute
- **Full Pipeline**: ~100-200 stories/minute
- **Manager Reflection Reviews**: Depends on moderator availability
- **Appeals**: ~400-600 appeals/minute

---

## 🔐 Security & Privacy

### Authentication Flow
```
User → Login → Auth DB → Session Token → Stored in memory → Used for all API calls
```

### Authorization Levels
- **Regular Users**: Submit content, view own content, file appeals
- **Moderators**: Access Manager Reflection queue, review content, view analytics
- **Senior Moderators**: Override decisions, manage moderators
- **Admins**: Full system access, user management, configuration

### Data Privacy
- User passwords: SHA-256 hashed (stored in Auth DB)
- Session tokens: 32-byte random URL-safe tokens
- Content data: Encrypted at rest (database level)
- API communication: HTTPS only (production)

---

## 🚀 Deployment Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Load Balancer                       │
└────────────────────┬────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
┌────────▼─────────┐    ┌────────▼─────────┐
│   API Server 1   │    │   API Server 2   │
│   (FastAPI)      │    │   (FastAPI)      │
└────────┬─────────┘    └────────┬─────────┘
         │                       │
         └───────────┬───────────┘
                     │
     ┌───────────────┼─────────────┐
     │               │             │
┌────▼─────┐  ┌──────▼───┐  ┌──────▼─────┐
│ SQLite   │  │ ChromaDB │  │ OpenRouter │
│ DBs      │  │ Vector   │  │ API        │
└──────────┘  └──────────┘  └────────────┘
```

---

## ⚙️ Configuration

### Environment Variables Impact

```
# OpenRouter LLM (required)
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key_here          # Put real key in backend/.env only
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_FREE_MODEL=openrouter/free
APP_URL=http://localhost:5173
LLM_TEMPERATURE=0.2
LLM_MAX_RETRIES=3
├─> llm_provider.py: get_llm() initializes ChatOpenAI
├─> llm_retry.py: invoke_llm() with tenacity retry
└─> All 9 agents: workforce reasoning via OpenRouter

ENABLE_QUICK_DECISION_CHECK=true
├─> workflow.py: enable_quick_check parameter
├─> should_use_quick_decision_check(): Check eligibility
└─> Entry Router: Route to quick_decision_check or team_gap_analysis

QUICK_CHECK_MAX_LENGTH=300
└─> should_use_quick_decision_check(): len(note) <= 300

QUICK_CHECK_DECISION_TYPES=quick_manager_note
└─> should_use_quick_decision_check(): decision_type in eligible_types

USE_ML_MODELS=false
├─> ml_classifier.py: Optional transformer models (disabled by default)
└─> Bias Signal Detection Agent: Uses OpenRouter LLM (not ML classifiers)

CHROMA_DB_PATH=./databases/chroma_moderation_db
├─> memory.py: PersistentClient storage location
└─> Stores: talent_decisions, manager_bias_patterns, manager_decision_history
    Embeddings: ChromaDB default (sentence-transformers/all-MiniLM-L6-v2)
```

### Key Takeaways

1. **Modular Design**: Each component has a single responsibility
2. **State-Driven**: TalentDecisionState flows through all agents, accumulating data
3. **Flexible Routing**: Workflow adapts based on decision type and agent outputs
4. **Manager Reflection**: Provides safety net for high bias risk and low confidence
5. **Learning System**: Memory and learning tracker enable continuous pattern improvement
6. **Performance Options**: Quick Decision Check for short notes, Full Pipeline for gap analysis and resume screening

### Processing Paths

| Decision Type | Length | Mode | Agents | Time | Cost |
|---------------|--------|------|--------|------|------|
| Gap analysis | Any | Full | 9 agents | 30–60s | Free (openrouter/free) |
| Resume screening | Any | Full | 9 agents | 30–60s | Free (openrouter/free) |
| Manager note | ≤300 chars | Quick | 1 agent | 2–5s | Free (openrouter/free) |

### Agent Decision Flow

```
Entry → team_gap_analysis → bias_signal_detection → fairness_policy_check
       → decision_synthesis
              ↓
        Manager Reflection? (if bias risk / low confidence)
              ↓
        manager_pattern_scoring
              ↓
        decision_logging → END

Quick path: entry → quick_decision_check → END
Reconsideration: entry → decision_reconsideration → decision_logging → END
```

---

## 📊 Complete Flow Summary

### Key Metrics
- **9 AI Agents** working in orchestrated LangGraph pipeline
- **3 Databases**: Auth SQLite, Talent Decision SQLite, ChromaDB Vector Memory
- **2 AI Systems**: OpenRouter LLM (reasoning) + ChromaDB Embeddings (memory)
- **Manager Reflection triggers** for high bias risk, low confidence, and overrides
- **Free hosted LLM** via OpenRouter (`openrouter/free`) — no Gemini key required
- **~30–60 second** average processing time (full pipeline)
- **~2–5 second** average processing time (quick decision check)

### Decision Paths
1. **Recommend Upskill**: Trainable gap → agents → upskill plan + learning path
2. **Recommend Hire**: Critical gap + resumes → rubric scoring → shortlist → manager review
3. **Manager Reflection**: High bias risk → Pause → Manager reflects → Resume
4. **Reconsideration**: Candidate/employee contests → Reconsideration agent → Uphold/revise

This architecture ensures:
- ✅ Evidence-based workforce decision support (never auto-hire/reject/promote)
- ✅ Manager reflection for high bias risk decisions
- ✅ Continuous learning from logged decisions and patterns
- ✅ Resume screening with anonymization support
- ✅ Complete audit trail via Decision Logger
- ✅ Reconsideration mechanism for contested decisions
