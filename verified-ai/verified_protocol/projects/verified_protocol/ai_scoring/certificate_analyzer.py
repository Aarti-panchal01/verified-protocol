"""
AI Scoring Engine — Certificate / Document Analyzer
=====================================================

Analyzes uploaded certificates, transcripts, and documents to produce
credibility signals without relying on paid OCR or AI APIs.

Signals:
    • File integrity (SHA-256 hash)
    • File metadata (size, type, name patterns)
    • Content signals from filename analysis
    • Issuer recognition heuristics
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from pathlib import Path
from typing import Any

from ai_scoring.models import DomainDetection, VerificationSignal
from ai_scoring.rules import CertificateWeights, LANGUAGE_DOMAIN_MAP

logger = logging.getLogger("ai_scoring.certificate")


# ─────────────────────────────────────────────────────────────────────────────
# Known Issuers (extensible)
# ─────────────────────────────────────────────────────────────────────────────
KNOWN_ISSUERS = {
    "coursera": 0.85,
    "udemy": 0.60,
    "edx": 0.80,
    "udacity": 0.75,
    "google": 0.90,
    "aws": 0.90,
    "microsoft": 0.88,
    "meta": 0.85,
    "ibm": 0.82,
    "oracle": 0.80,
    "linkedin": 0.65,
    "hackerrank": 0.60,
    "leetcode": 0.55,
    "freecodecamp": 0.50,
    "codecademy": 0.45,
    "kaggle": 0.70,
    "deeplearning.ai": 0.85,
    "stanford": 0.95,
    "mit": 0.95,
    "harvard": 0.95,
    "berkeley": 0.92,
    "nptel": 0.70,
    "pes university": 0.65,
}

VALID_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg",
    ".doc", ".docx", ".txt",
    ".webp", ".svg",
}


class CertificateAnalyzer:
    """Analyzes certificate / document files for credibility signals."""

    def __init__(self) -> None:
        self.weights = CertificateWeights()

    async def analyze(self, file_path: str) -> dict[str, Any]:
        """Analyze a certificate file and return signals.

        Returns dict with:
            signals: list[VerificationSignal]
            domains: list[DomainDetection]
            metadata: dict
            overall_score: float (0.0–1.0)
        """
        path = Path(file_path)

        if not path.exists():
            return self._error_result(f"File not found: {file_path}")

        if not path.is_file():
            return self._error_result(f"Not a file: {file_path}")

        signals: list[VerificationSignal] = []
        metadata: dict[str, Any] = {}

        # ── 1. Document Integrity ─────────────────────────────────────
        file_hash = self._compute_hash(path)
        file_size = path.stat().st_size
        ext = path.suffix.lower()

        is_valid_type = ext in VALID_EXTENSIONS
        integrity_score = 1.0 if (is_valid_type and file_size > 1024) else 0.3

        signals.append(VerificationSignal(
            signal_name="document_integrity",
            value=1 if is_valid_type else 0,
            max_value=1,
            normalized=integrity_score,
            detail=f"SHA-256: {file_hash[:16]}… | Type: {ext} | Size: {file_size:,} bytes",
        ))

        metadata["sha256"] = file_hash
        metadata["file_size"] = file_size
        metadata["extension"] = ext
        metadata["filename"] = path.name

        # ── 2. Content Signals (from filename) ────────────────────────
        name_lower = path.stem.lower().replace("_", " ").replace("-", " ")
        content_signals = self._analyze_filename(name_lower)
        content_score = min(1.0, content_signals["keyword_hits"] / 3)

        signals.append(VerificationSignal(
            signal_name="content_signals",
            value=content_signals["keyword_hits"],
            max_value=5,
            normalized=content_score,
            detail=f"Keywords: {', '.join(content_signals['keywords_found']) or 'none'}",
        ))

        # ── 3. Metadata Quality ───────────────────────────────────────
        has_meaningful_name = len(path.stem) > 5 and not path.stem.startswith("IMG")
        has_proper_ext = is_valid_type
        has_reasonable_size = 5_000 < file_size < 50_000_000  # 5KB–50MB

        meta_bits = sum([has_meaningful_name, has_proper_ext, has_reasonable_size])
        meta_score = meta_bits / 3

        signals.append(VerificationSignal(
            signal_name="metadata_quality",
            value=meta_bits,
            max_value=3,
            normalized=meta_score,
            detail=f"Name: {has_meaningful_name}, Type: {has_proper_ext}, Size: {has_reasonable_size}",
        ))

        # ── 4. File Quality ───────────────────────────────────────────
        if ext == ".pdf":
            quality_score = 0.9
        elif ext in {".png", ".jpg", ".jpeg", ".webp"}:
            quality_score = 0.7
        elif ext in {".doc", ".docx"}:
            quality_score = 0.8
        else:
            quality_score = 0.4

        signals.append(VerificationSignal(
            signal_name="file_quality",
            value=quality_score,
            max_value=1.0,
            normalized=quality_score,
            detail=f"File format: {ext} — quality tier: {'high' if quality_score >= 0.8 else 'standard'}",
        ))

        # ── 5. Issuer Recognition ─────────────────────────────────────
        issuer, issuer_confidence = self._detect_issuer(name_lower)
        metadata["detected_issuer"] = issuer

        signals.append(VerificationSignal(
            signal_name="issuer_recognition",
            value=issuer_confidence,
            max_value=1.0,
            normalized=issuer_confidence,
            detail=f"Issuer: {issuer or 'unknown'}",
        ))

        # ── Weighted overall ──────────────────────────────────────────
        weight_map = {
            "document_integrity": self.weights.DOCUMENT_INTEGRITY,
            "content_signals": self.weights.CONTENT_SIGNALS,
            "metadata_quality": self.weights.METADATA_QUALITY,
            "file_quality": self.weights.FILE_QUALITY,
            "issuer_recognition": self.weights.ISSUER_RECOGNITION,
        }

        overall = sum(
            s.normalized * weight_map.get(s.signal_name, 0)
            for s in signals
        )

        # ── Domain detection ──────────────────────────────────────────
        domains = self._detect_domains(name_lower, content_signals.get("keywords_found", []))

        return {
            "signals": signals,
            "domains": domains,
            "metadata": metadata,
            "overall_score": round(overall, 4),
        }

    @staticmethod
    def _compute_hash(path: Path) -> str:
        sha = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha.update(chunk)
        return sha.hexdigest()

    @staticmethod
    def _analyze_filename(name: str) -> dict[str, Any]:
        """Extract content signals from filename."""
        keywords = [
            "certificate", "certification", "diploma", "degree",
            "completion", "achievement", "course", "coursework",
            "badge", "credential", "transcript", "license",
            "award", "hackathon", "bootcamp", "training",
            "professional", "verified", "accredited",
        ]
        found = [kw for kw in keywords if kw in name]
        return {"keyword_hits": len(found), "keywords_found": found}

    @staticmethod
    def _detect_issuer(name: str) -> tuple[str | None, float]:
        """Detect issuer from filename."""
        for issuer, confidence in KNOWN_ISSUERS.items():
            if issuer.lower() in name:
                return issuer.title(), confidence
        return None, 0.2  # Unknown issuer baseline

    @staticmethod
    def _detect_domains(name: str, keywords: list[str]) -> list[DomainDetection]:
        """Detect domains from filename content."""
        domains: dict[str, float] = {}

        for lang, domain in LANGUAGE_DOMAIN_MAP.items():
            if lang in name:
                domains[domain] = max(domains.get(domain, 0), 0.7)

        tech_keywords = {
            "machine learning": ("machine-learning", 0.8),
            "deep learning": ("machine-learning", 0.8),
            "data science": ("data-science", 0.8),
            "web development": ("web-frontend", 0.7),
            "frontend": ("web-frontend", 0.7),
            "backend": ("web-backend", 0.7),
            "cloud": ("devops", 0.6),
            "devops": ("devops", 0.7),
            "blockchain": ("blockchain", 0.8),
            "security": ("security", 0.7),
            "mobile": ("mobile", 0.7),
        }

        for keyword, (domain, conf) in tech_keywords.items():
            if keyword in name:
                domains[domain] = max(domains.get(domain, 0), conf)

        return [
            DomainDetection(domain=d, confidence=round(c, 3))
            for d, c in sorted(domains.items(), key=lambda x: -x[1])
        ][:3]

    @staticmethod
    def _error_result(msg: str) -> dict[str, Any]:
        return {
            "signals": [],
            "domains": [],
            "metadata": {"error": msg},
            "overall_score": 0.0,
        }
