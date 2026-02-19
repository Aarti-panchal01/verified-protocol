"""
Backend Router — Verification
===============================

POST /verify/repo        — Verify a GitHub repo
POST /verify/certificate — Verify a certificate file
POST /verify/project     — Verify a project directory
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from verification_engine.github_verifier import GitHubVerifier
from verification_engine.certificate_verifier import CertificateVerifier
from verification_engine.project_verifier import ProjectVerifier

logger = logging.getLogger("backend.verification")
router = APIRouter(prefix="/verify-evidence", tags=["Verification"])

github_v = GitHubVerifier()
cert_v = CertificateVerifier()
project_v = ProjectVerifier()


class RepoVerifyRequest(BaseModel):
    repo_url: str
    wallet: Optional[str] = None


class FileVerifyRequest(BaseModel):
    file_path: str


class ProjectVerifyRequest(BaseModel):
    project_path: str


class VerificationResponse(BaseModel):
    verified: bool
    overall_score: float
    source_type: str
    signals: list[dict] = []
    domains: list[dict] = []
    metadata: dict = {}
    error: Optional[str] = None


@router.post("/repo", response_model=VerificationResponse)
async def verify_repo(req: RepoVerifyRequest):
    """Verify a GitHub repository."""
    try:
        result = await github_v.verify(req.repo_url, req.wallet)
        return VerificationResponse(
            verified=result.verified,
            overall_score=result.overall_score,
            source_type=result.source_type.value,
            signals=[s.model_dump() for s in result.signals],
            domains=[d.model_dump() for d in result.domains_detected],
            metadata=result.metadata,
            error=result.error,
        )
    except Exception as exc:
        logger.error("Repo verification failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/certificate", response_model=VerificationResponse)
async def verify_certificate(req: FileVerifyRequest):
    """Verify a certificate file."""
    try:
        result = await cert_v.verify(req.file_path)
        return VerificationResponse(
            verified=result.verified,
            overall_score=result.overall_score,
            source_type=result.source_type.value,
            signals=[s.model_dump() for s in result.signals],
            domains=[d.model_dump() for d in result.domains_detected],
            metadata=result.metadata,
            error=result.error,
        )
    except Exception as exc:
        logger.error("Certificate verification failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/project", response_model=VerificationResponse)
async def verify_project(req: ProjectVerifyRequest):
    """Verify a local project directory."""
    try:
        result = await project_v.verify(req.project_path)
        return VerificationResponse(
            verified=result.verified,
            overall_score=result.overall_score,
            source_type=result.source_type.value,
            signals=[s.model_dump() for s in result.signals],
            domains=[d.model_dump() for d in result.domains_detected],
            metadata=result.metadata,
            error=result.error,
        )
    except Exception as exc:
        logger.error("Project verification failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail=str(exc))
