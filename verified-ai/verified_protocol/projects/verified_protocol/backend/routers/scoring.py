"""
Backend Router — Scoring & Analysis
=====================================

POST /analyze/repo        — Analyze a GitHub repo
POST /analyze/certificate — Analyze an uploaded certificate
POST /analyze/project     — Analyze a project directory
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ai_scoring.engine import ScoringEngine
from ai_scoring.models import EvidenceMode, ScoringResult, SourceType, ScoringInput

logger = logging.getLogger("backend.scoring")
router = APIRouter(prefix="/analyze", tags=["Scoring"])

engine = ScoringEngine()


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response Models
# ─────────────────────────────────────────────────────────────────────────────
class RepoAnalysisRequest(BaseModel):
    repo_url: str = Field(..., description="GitHub repository URL")
    mode: EvidenceMode = EvidenceMode.DEVELOPER


class CertificateAnalysisRequest(BaseModel):
    file_path: str = Field(..., description="Path to certificate file")
    mode: EvidenceMode = EvidenceMode.LEARNER


class ProjectAnalysisRequest(BaseModel):
    project_path: str = Field(..., description="Path to project directory")
    mode: EvidenceMode = EvidenceMode.DEVELOPER


class AnalysisResponse(BaseModel):
    credibility_score: int
    domain: str
    subdomain: Optional[str] = None
    confidence: float
    explanation: str
    artifact_hash: str
    mode: str
    source_type: str
    breakdown: list[dict] = []


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/repo", response_model=AnalysisResponse)
async def analyze_repo(req: RepoAnalysisRequest):
    """Analyze a GitHub repository and return credibility score."""
    try:
        result = await engine.score(ScoringInput(
            mode=req.mode,
            source_type=SourceType.GITHUB_REPO,
            source_url=req.repo_url,
        ))
        return _to_response(result)
    except Exception as exc:
        logger.error("Repo analysis failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/certificate", response_model=AnalysisResponse)
async def analyze_certificate(req: CertificateAnalysisRequest):
    """Analyze a certificate file and return credibility score."""
    try:
        result = await engine.score(ScoringInput(
            mode=req.mode,
            source_type=SourceType.CERTIFICATE,
            file_path=req.file_path,
        ))
        return _to_response(result)
    except Exception as exc:
        logger.error("Certificate analysis failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/project", response_model=AnalysisResponse)
async def analyze_project(req: ProjectAnalysisRequest):
    """Analyze a local project and return credibility score."""
    try:
        result = await engine.score(ScoringInput(
            mode=req.mode,
            source_type=SourceType.PROJECT,
            file_path=req.project_path,
        ))
        return _to_response(result)
    except Exception as exc:
        logger.error("Project analysis failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail=str(exc))


def _to_response(result: ScoringResult) -> AnalysisResponse:
    return AnalysisResponse(
        credibility_score=result.credibility_score,
        domain=result.domain,
        subdomain=result.subdomain,
        confidence=result.confidence,
        explanation=result.explanation,
        artifact_hash=result.artifact_hash,
        mode=result.mode.value,
        source_type=result.source_type.value,
        breakdown=[b.model_dump() for b in result.breakdown],
    )
