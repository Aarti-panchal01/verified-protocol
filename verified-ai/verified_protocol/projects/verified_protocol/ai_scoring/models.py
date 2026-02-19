"""
AI Scoring Engine — Data Models
================================

Shared Pydantic models for scoring, verification, and reputation.
These models define the protocol's data layer between all modules.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────
class EvidenceMode(str, Enum):
    DEVELOPER = "developer"
    LEARNER = "learner"


class SourceType(str, Enum):
    GITHUB_REPO = "github-repo"
    GITHUB_PROFILE = "github-profile"
    CERTIFICATE = "certificate"
    PROJECT = "project"
    COURSEWORK = "coursework"
    HACKATHON = "hackathon"
    DOCUMENT = "document"


class CredibilityLevel(str, Enum):
    EXCEPTIONAL = "exceptional"  # 90–100
    STRONG = "strong"            # 70–89
    MODERATE = "moderate"        # 50–69
    DEVELOPING = "developing"    # 30–49
    MINIMAL = "minimal"          # 0–29


# ─────────────────────────────────────────────────────────────────────────────
# Scoring Models
# ─────────────────────────────────────────────────────────────────────────────
class ScoringInput(BaseModel):
    """Input payload for the AI Scoring Engine."""
    mode: EvidenceMode
    source_type: SourceType
    source_url: Optional[str] = None
    file_path: Optional[str] = None
    raw_text: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class DomainDetection(BaseModel):
    """Detected skill domain and subdomain."""
    domain: str
    subdomain: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)


class ScoringBreakdown(BaseModel):
    """Detailed breakdown of scoring factors."""
    factor: str
    weight: float
    raw_score: float
    weighted_score: float
    explanation: str


class ScoringResult(BaseModel):
    """Output of the AI Scoring Engine."""
    credibility_score: int = Field(ge=0, le=100)
    domain: str
    subdomain: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str
    breakdown: list[ScoringBreakdown] = []
    mode: EvidenceMode
    source_type: SourceType
    artifact_hash: str = ""
    source_url: Optional[str] = None
    issuer: Optional[str] = None

    @property
    def credibility_level(self) -> CredibilityLevel:
        if self.credibility_score >= 90:
            return CredibilityLevel.EXCEPTIONAL
        if self.credibility_score >= 70:
            return CredibilityLevel.STRONG
        if self.credibility_score >= 50:
            return CredibilityLevel.MODERATE
        if self.credibility_score >= 30:
            return CredibilityLevel.DEVELOPING
        return CredibilityLevel.MINIMAL


# ─────────────────────────────────────────────────────────────────────────────
# Verification Models
# ─────────────────────────────────────────────────────────────────────────────
class VerificationSignal(BaseModel):
    """Single verification signal from an evidence source."""
    signal_name: str
    value: float
    max_value: float
    normalized: float = Field(ge=0.0, le=1.0)
    detail: str


class VerificationResult(BaseModel):
    """Output of a verification pipeline step."""
    source_type: SourceType
    source_url: Optional[str] = None
    verified: bool
    overall_score: float = Field(ge=0.0, le=1.0)
    signals: list[VerificationSignal] = []
    domains_detected: list[DomainDetection] = []
    metadata: dict = Field(default_factory=dict)
    error: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# On-Chain Record Model (maps to ARC-4 struct)
# ─────────────────────────────────────────────────────────────────────────────
class SkillRecordPayload(BaseModel):
    """Payload prepared for on-chain submission.

    Maps to the existing ARC-4 SkillRecord struct:
        mode      → "{developer|learner}"
        domain    → "{domain}:{subdomain}" or just "{domain}"
        score     → credibility_score (uint64, 0–100)
        artifact_hash → SHA-256 hash of evidence bundle
        timestamp → unix epoch (uint64)

    Extended metadata (source_type, source_url, issuer) is stored
    off-chain and referenced by artifact_hash.
    """
    mode: EvidenceMode
    domain: str
    subdomain: Optional[str] = None
    credibility_score: int = Field(ge=0, le=100)
    artifact_hash: str
    source_type: SourceType
    source_url: Optional[str] = None
    issuer: Optional[str] = None
    timestamp: int

    @property
    def on_chain_mode(self) -> str:
        return self.mode.value

    @property
    def on_chain_domain(self) -> str:
        if self.subdomain:
            return f"{self.domain}:{self.subdomain}"
        return self.domain


# ─────────────────────────────────────────────────────────────────────────────
# Reputation Models
# ─────────────────────────────────────────────────────────────────────────────
class DomainScore(BaseModel):
    """Reputation score for a single domain."""
    domain: str
    score: float
    record_count: int
    latest_timestamp: int
    trend: str = "stable"  # rising, stable, declining


class ReputationProfile(BaseModel):
    """Aggregated reputation profile for a wallet."""
    wallet: str
    total_reputation: float
    credibility_level: CredibilityLevel
    domain_scores: list[DomainScore] = []
    verification_badge: bool = False
    total_records: int = 0
    trust_index: float = Field(ge=0.0, le=1.0, default=0.0)
    top_domain: Optional[str] = None
    active_since: Optional[int] = None
