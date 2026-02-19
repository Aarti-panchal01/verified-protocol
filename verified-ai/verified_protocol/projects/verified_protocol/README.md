# Verified Protocol

**Decentralized Skill Reputation Layer for AI-Verified Talent on Algorand.**

> **Status**: Testnet Beta (Phase H)
> **App ID**: `755779875` (Testnet)

## Overview

Verified Protocol is a decentralized infrastructure for validating developer and learner skills. It combines **AI-powered evidence scoring** with **on-chain attestation** to create an immutable, portable skill passport.

### Core Features

- **AI Scoring Engine**: Analyzes GitHub repos, certificates, and projects to generate credibility scores (0-100) and detailed explanations.
- **On-Chain Reputation**: Stores skill records in per-wallet Box storage on Algorand, enabling a permanent, user-owned reputation history.
- **Verification Pipeline**: Validates integrity, ownership, and originality of submitted evidence.
- **Reputation Engine**: Aggregates records into domain-level scores, computes trust indices, and assigns credibility tiers.

---

## Architecture

The system consists of a Python FastAPI backend, a React/Vite frontend, and an Algorand smart contract.

> **See [ARCHITECTURE.md](./ARCHITECTURE.md) for full system diagrams, module breakdowns, and API reference.**

### Directory Structure

- `ai_scoring/` — AI models and rules for evidence analysis.
- `verification_engine/` — Logic for verifying evidence authenticity.
- `reputation_engine/` — Aggregation logic for wallet profiles.
- `backend/` — FastAPI application and routers.
- `frontend/` — React/Vite web application (Level 10 User Interface).
- `smart_contracts/` — Algorand smart contract (ARC-4).

---

## Quick Start

### Prerequisites
- Python 3.12+ (managed via Poetry)
- Node.js 18+
- AlgoKit CLI

### 1. Setup Backend
```bash
poetry install
```

### 2. Configure Environment
Create a `.env` file in this directory (see `ARCHITECTURE.md` for details):
```env
ALGOD_SERVER=https://testnet-api.algonode.cloud
ALGOD_PORT=443
ALGOD_TOKEN=
DEPLOYER_MNEMONIC=<your_25_word_mnemonic>
```

### 3. Run Backend
```bash
poetry run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```
API will be available at [http://localhost:8000](http://localhost:8000).

### 4. Run Frontend
```bash
cd frontend
npm install
npm run dev
```
Web app will be available at [http://localhost:5173](http://localhost:5173).

---

## Usage

1. **Submit Evidence**: Go to the web app, choose "Developer" or "Learner" mode, and paste a GitHub URL or upload a certificate.
2. **View Analysis**: The AI engine scores your evidence and shows a breakdown.
3. **Submit On-Chain**: Click "Submit" to write the record to your Algorand wallet's box storage.
4. **Explorer**: Use the Explorer page to search for any wallet and view their verified skill timeline and reputation score.

---

## CLI Tools

You can also interact with the protocol via CLI:

```bash
# Submit a record manually
poetry run python interact.py submit python 85

# Verify a wallet
poetry run python interact.py verify
```

---

## License

MIT
