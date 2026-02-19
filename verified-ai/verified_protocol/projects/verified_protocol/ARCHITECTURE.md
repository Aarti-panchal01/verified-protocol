# Verified Protocol — Architecture & Operations Guide

## Decentralized Skill Reputation Layer for AI-Verified Talent

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       FRONTEND (React/Vite)                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │  Submit   │ │Dashboard │ │ Verifier │ │ Explorer │          │
│  │ (AI Flow) │ │(Wallet)  │ │(Recruiter)│ │(Browse)  │          │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘          │
└───────┼─────────────┼───────────┼─────────────┼─────────────────┘
        │             │           │             │
        ▼             ▼           ▼             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     BACKEND API (FastAPI)                        │
│                                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ Scoring  │ │Submission│ │Retrieval │ │Reputation│          │
│  │ Router   │ │ Router   │ │ Router   │ │ Router   │          │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘          │
│       │             │           │             │                  │
│  ┌────▼─────┐  ┌────▼─────┐   │        ┌────▼─────┐          │
│  │AI Scoring│  │ On-Chain │   │        │Reputation│          │
│  │ Engine   │  │ Submit   │   │        │ Engine   │          │
│  └────┬─────┘  └────┬─────┘   │        └────┬─────┘          │
│       │             │           │             │                  │
│  ┌────▼─────────────▼───────────▼─────────────▼──────┐         │
│  │              Algorand Client (algokit-utils)       │         │
│  └────────────────────────┬──────────────────────────┘         │
└───────────────────────────┼──────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              ALGORAND TESTNET (Smart Contract)                   │
│                                                                  │
│  App ID: 755779875                                               │
│  Storage: Box per wallet (ARC-4 SkillRecord structs)            │
│  Methods: submit_skill_record, get_skill_records,               │
│           get_record_count                                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## System Modules

### 1. AI Scoring Engine (`ai_scoring/`)
- **engine.py** — Main orchestrator: routes evidence → analyzers → ScoringResult
- **github_analyzer.py** — GitHub REST API analysis (commits, languages, community, docs, recency)
- **certificate_analyzer.py** — Document analysis (integrity, issuer, content signals)
- **project_analyzer.py** — Directory analysis (structure, tech stack, originality)
- **rules.py** — Centralized scoring weights, thresholds, domain mappings
- **models.py** — Shared Pydantic models (ScoringResult, VerificationResult, ReputationProfile, etc.)

### 2. Verification Engine (`verification_engine/`)
- **github_verifier.py** — Repo existence, fork detection, commit consistency, activity
- **certificate_verifier.py** — File integrity, type validation, name plausibility
- **project_verifier.py** — Structure verification, originality, hash integrity

### 3. Reputation Engine (`reputation_engine/`)
- **engine.py** — Aggregation with exponential time-decay (180-day half-life), per-domain scoring, trust index computation (5 factors), verification badge eligibility

### 4. Backend API (`backend/`)
- **main.py** — FastAPI app with CORS, rate limiting, request timing middleware
- **config.py** — Singleton Algorand clients, ARC-4 decoder, shared helpers
- **routers/scoring.py** — POST /analyze/{repo,certificate,project}
- **routers/verification.py** — POST /verify-evidence/{repo,certificate,project}
- **routers/submission.py** — POST /submit (on-chain with MBR + retry)
- **routers/retrieval.py** — GET /wallet/{wallet}, GET /timeline/{wallet}
- **routers/reputation.py** — GET /reputation/{wallet}, GET /verify/{wallet}

### 5. Frontend (`frontend/`)
- **Submit Page** — Developer/Learner mode, source type selector, AI analysis preview, on-chain submission
- **Dashboard Page** — Reputation radar, domain bar chart, trust index, record timeline
- **Verifier Page** — Recruiter view, verification hero, blockchain proof, trust scoring
- **Explorer Page** — Talent discovery, wallet search, domain-filtered results

### 6. Smart Contract (Algorand, already deployed)
- ARC-4 SkillRecord struct: `(mode, domain, score, artifact_hash, timestamp)`
- Box storage per wallet
- Methods: `submit_skill_record`, `get_skill_records`, `get_record_count`

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API info & endpoint index |
| GET | `/health` | Health check |
| POST | `/analyze/repo` | Analyze GitHub repo → credibility score |
| POST | `/analyze/certificate` | Analyze certificate → credibility score |
| POST | `/analyze/project` | Analyze project → credibility score |
| POST | `/verify-evidence/repo` | Verify GitHub repo authenticity |
| POST | `/verify-evidence/certificate` | Verify certificate integrity |
| POST | `/verify-evidence/project` | Verify project originality |
| POST | `/submit` | Submit skill record on-chain |
| GET | `/wallet/{wallet}` | Fetch decoded wallet records |
| GET | `/timeline/{wallet}` | Chronological timeline |
| GET | `/reputation/{wallet}` | Full reputation profile |
| GET | `/verify/{wallet}` | Wallet verification + reputation |

---

## Production Run Instructions

### Prerequisites
- Python 3.12+
- Node.js 18+
- Poetry
- AlgoKit CLI
- `.env` file with `ALGOD_SERVER`, `ALGOD_PORT`, `ALGOD_TOKEN`, `DEPLOYER_MNEMONIC`

### Backend
```bash
cd projects/verified_protocol
poetry install
poetry run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend (Development)
```bash
cd projects/verified_protocol/frontend
npm install
npm run dev
```

### Frontend (Production Build)
```bash
cd projects/verified_protocol/frontend
npm run build
# Serve dist/ with any static server
```

### CLI Tools
```bash
# Submit a record
poetry run python interact.py submit python 85

# Submit with artifact
poetry run python interact.py submit python 85 --artifact ./evidence.pdf

# Read records
poetry run python read_records.py <WALLET_ADDRESS> --pretty

# Verify a wallet
poetry run python interact.py verify
```

---

## Environment Configuration

```env
# .env (DO NOT commit)
ALGOD_SERVER=https://testnet-api.algonode.cloud
ALGOD_PORT=443
ALGOD_TOKEN=
DEPLOYER_MNEMONIC=<your 25-word mnemonic>

# Optional
GITHUB_TOKEN=<github personal access token for higher API limits>
```

---

## Dev Workflow

1. **Modify contract** → `algokit compile` → `algokit deploy`
2. **Add scoring rules** → Edit `ai_scoring/rules.py`
3. **Extend analyzers** → Add to `ai_scoring/` or `verification_engine/`
4. **Add API endpoints** → Create or edit routers in `backend/routers/`
5. **Update frontend** → Edit pages in `frontend/src/pages/`
6. **Test** → `poetry run python -m pytest tests/`
7. **Build frontend** → `npm run build`

---

## Security Measures

- **Rate limiting**: 60 requests/minute per IP (in-memory)
- **Request timing**: All requests logged with processing time
- **CORS**: Configurable allowed origins
- **Retry logic**: 3 retries with 4s delay for all Algorand transactions
- **Validity windows**: 1000 rounds for network stability
- **MBR funding**: Automatic 0.5 ALGO funding before Box operations
- **.env protection**: Sensitive data excluded from version control
