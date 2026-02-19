"""
AI Scoring Engine — Scoring Rules & Heuristics
================================================

Production scoring rules used by the AI engine.
All weights, thresholds, and domain mappings are defined here.
No magic numbers elsewhere.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# Domain Detection — Language / Tech → Domain Mapping
# ─────────────────────────────────────────────────────────────────────────────
LANGUAGE_DOMAIN_MAP: dict[str, str] = {
    # Programming Languages
    "python": "python",
    "javascript": "javascript",
    "typescript": "javascript",
    "java": "java",
    "kotlin": "java",
    "c#": "dotnet",
    "c++": "systems",
    "c": "systems",
    "rust": "rust",
    "go": "golang",
    "ruby": "ruby",
    "php": "php",
    "swift": "ios",
    "objective-c": "ios",
    "dart": "flutter",
    "solidity": "blockchain",
    "vyper": "blockchain",
    "teal": "algorand",
    "pyteal": "algorand",
    "move": "blockchain",
    "haskell": "functional",
    "elixir": "elixir",
    "scala": "jvm",
    "r": "data-science",
    "julia": "scientific",
    "shell": "devops",
    "dockerfile": "devops",
    "hcl": "devops",
    "nix": "devops",
}

SUBDOMAIN_SIGNALS: dict[str, list[str]] = {
    # Files/dirs that hint at subdomain
    "web-frontend": [
        "react", "vue", "angular", "next", "nuxt", "svelte",
        "tailwind", "webpack", "vite", "babel", "postcss",
    ],
    "web-backend": [
        "express", "fastapi", "flask", "django", "spring",
        "nestjs", "rails", "gin", "fiber", "actix",
    ],
    "machine-learning": [
        "tensorflow", "pytorch", "keras", "scikit", "sklearn",
        "transformers", "huggingface", "model", "training",
        "dataset", "notebook", "jupyter",
    ],
    "devops": [
        "docker", "kubernetes", "k8s", "terraform", "ansible",
        "ci", "cd", "pipeline", "github-actions", "jenkins",
    ],
    "blockchain": [
        "contract", "solidity", "web3", "ethers", "algorand",
        "algokit", "beaker", "pyteal", "teal", "hardhat",
        "foundry", "truffle",
    ],
    "mobile": [
        "android", "ios", "react-native", "flutter", "expo",
        "swift", "kotlin",
    ],
    "data-engineering": [
        "spark", "airflow", "kafka", "etl", "pipeline",
        "dbt", "bigquery", "redshift", "snowflake",
    ],
    "security": [
        "auth", "oauth", "jwt", "crypto", "encryption",
        "penetration", "vulnerability", "security",
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# GitHub Scoring Weights
# ─────────────────────────────────────────────────────────────────────────────
class GitHubWeights:
    """Scoring weights for GitHub repository analysis."""

    # Factor weights (must sum to 1.0)
    COMMIT_ACTIVITY = 0.20
    CODE_VOLUME = 0.15
    LANGUAGE_DIVERSITY = 0.10
    COMMUNITY_SIGNALS = 0.15
    DOCUMENTATION = 0.10
    RECENCY = 0.15
    REPO_MATURITY = 0.10
    CODE_QUALITY_SIGNALS = 0.05

    # Thresholds
    COMMIT_HIGH = 200
    COMMIT_MID = 50
    COMMIT_LOW = 10

    STARS_HIGH = 100
    STARS_MID = 10

    FORKS_HIGH = 50
    FORKS_MID = 5

    FILE_COUNT_HIGH = 100
    FILE_COUNT_MID = 20

    # Recency (days since last commit)
    RECENCY_EXCELLENT = 30      # < 30 days = excellent
    RECENCY_GOOD = 90           # < 90 days = good
    RECENCY_ACCEPTABLE = 365    # < 1 year = acceptable

    # Repo age (days)
    MATURITY_ESTABLISHED = 365
    MATURITY_GROWING = 90
    MATURITY_NEW = 30


class CertificateWeights:
    """Scoring weights for certificate / document analysis."""

    DOCUMENT_INTEGRITY = 0.30
    CONTENT_SIGNALS = 0.25
    METADATA_QUALITY = 0.20
    FILE_QUALITY = 0.15
    ISSUER_RECOGNITION = 0.10


class ProjectWeights:
    """Scoring weights for project analysis."""

    STRUCTURE = 0.25
    DOCUMENTATION = 0.20
    CODE_QUALITY = 0.20
    COMPLETENESS = 0.15
    TECH_STACK = 0.10
    ORIGINALITY = 0.10


# ─────────────────────────────────────────────────────────────────────────────
# Documentation Signals
# ─────────────────────────────────────────────────────────────────────────────
DOC_FILES = {
    "readme.md", "readme.rst", "readme.txt", "readme",
    "contributing.md", "contributing.rst",
    "changelog.md", "changelog.rst", "changes.md",
    "license", "license.md", "license.txt",
    "code_of_conduct.md",
    "security.md",
    "docs",
}

CI_FILES = {
    ".github/workflows",
    ".gitlab-ci.yml",
    ".travis.yml",
    "jenkinsfile",
    ".circleci",
    "azure-pipelines.yml",
}

CONFIG_FILES = {
    "pyproject.toml", "setup.py", "setup.cfg",
    "package.json", "tsconfig.json",
    "cargo.toml",
    "go.mod",
    "gemfile",
    "pom.xml", "build.gradle",
    "makefile", "cmake",
    "docker-compose.yml", "dockerfile",
    ".env.example", ".editorconfig",
}

TEST_DIRS = {
    "tests", "test", "spec", "specs",
    "__tests__", "e2e", "integration_tests",
}


# ─────────────────────────────────────────────────────────────────────────────
# Credibility Level Thresholds
# ─────────────────────────────────────────────────────────────────────────────
def credibility_label(score: int) -> str:
    """Return human-readable credibility label."""
    if score >= 90:
        return "Exceptional"
    if score >= 70:
        return "Strong"
    if score >= 50:
        return "Moderate"
    if score >= 30:
        return "Developing"
    return "Minimal"
