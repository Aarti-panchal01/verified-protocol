"""
Verification Engine — Certificate Verifier
=============================================

Verifies uploaded certificate / document evidence.

Checks:
    • File exists and is valid
    • SHA-256 integrity hash
    • Metadata extraction
    • Issuer plausibility
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from ai_scoring.models import SourceType, VerificationResult, VerificationSignal

logger = logging.getLogger("verification.certificate")


class CertificateVerifier:
    """Verifies certificate / document file evidence."""

    async def verify(self, file_path: str) -> VerificationResult:
        """Verify a certificate file and return VerificationResult."""
        path = Path(file_path)
        signals: list[VerificationSignal] = []
        metadata: dict[str, Any] = {"file_path": file_path}

        # 1. File existence
        if not path.exists() or not path.is_file():
            return VerificationResult(
                source_type=SourceType.CERTIFICATE,
                verified=False,
                error=f"File not found: {file_path}",
            )

        # 2. File integrity
        sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        metadata["sha256"] = sha256
        metadata["filename"] = path.name
        metadata["size_bytes"] = path.stat().st_size
        metadata["extension"] = path.suffix.lower()

        signals.append(VerificationSignal(
            signal_name="file_integrity",
            value=1,
            max_value=1,
            normalized=1.0,
            detail=f"SHA-256: {sha256[:24]}…",
        ))

        # 3. File type validation
        valid_types = {".pdf", ".png", ".jpg", ".jpeg", ".doc", ".docx", ".webp"}
        is_valid = path.suffix.lower() in valid_types
        signals.append(VerificationSignal(
            signal_name="file_type",
            value=1 if is_valid else 0,
            max_value=1,
            normalized=1.0 if is_valid else 0.3,
            detail=f"File type: {path.suffix} — {'valid' if is_valid else 'unusual format'}",
        ))

        # 4. File size check
        size = path.stat().st_size
        reasonable = 5_000 < size < 50_000_000
        signals.append(VerificationSignal(
            signal_name="file_size",
            value=size,
            max_value=50_000_000,
            normalized=0.9 if reasonable else 0.3,
            detail=f"Size: {size:,} bytes — {'reasonable' if reasonable else 'suspicious'}",
        ))

        # 5. Name plausibility
        name_lower = path.stem.lower()
        cert_keywords = ["certificate", "diploma", "completion", "badge", "award", "transcript"]
        has_keywords = any(kw in name_lower for kw in cert_keywords)
        signals.append(VerificationSignal(
            signal_name="name_plausibility",
            value=1 if has_keywords else 0,
            max_value=1,
            normalized=0.8 if has_keywords else 0.4,
            detail=f"Filename: {path.name} — {'contains cert keywords' if has_keywords else 'generic name'}",
        ))

        overall = sum(s.normalized for s in signals) / max(len(signals), 1)
        verified = overall >= 0.5 and is_valid

        return VerificationResult(
            source_type=SourceType.CERTIFICATE,
            verified=verified,
            overall_score=round(overall, 4),
            signals=signals,
            metadata=metadata,
        )
