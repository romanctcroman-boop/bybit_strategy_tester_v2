"""
Git Secrets Scanner Service.

AI Agent Security Recommendation - Phase 4 Implementation:
- Scan repository for leaked credentials
- Detect API keys, passwords, private keys
- Support for custom patterns
- Integration with truffleHog patterns
- Pre-commit hook support
- Audit reporting
"""

import json
import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SecretType(str, Enum):
    """Types of secrets that can be detected."""

    API_KEY = "api_key"
    PASSWORD = "password"
    PRIVATE_KEY = "private_key"
    AWS_KEY = "aws_key"
    AZURE_KEY = "azure_key"
    GCP_KEY = "gcp_key"
    JWT_TOKEN = "jwt_token"
    OAUTH_TOKEN = "oauth_token"
    DATABASE_URL = "database_url"
    CONNECTION_STRING = "connection_string"
    GENERIC_SECRET = "generic_secret"
    CRYPTO_KEY = "crypto_key"
    SSH_KEY = "ssh_key"


class SeverityLevel(str, Enum):
    """Severity levels for findings."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ScanStatus(str, Enum):
    """Status of a scan."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SecretPattern:
    """Pattern for detecting secrets."""

    name: str
    pattern: str
    secret_type: SecretType
    severity: SeverityLevel
    description: str = ""
    false_positive_patterns: list[str] = field(default_factory=list)


@dataclass
class Finding:
    """A secret finding in the codebase."""

    finding_id: str
    secret_type: SecretType
    severity: SeverityLevel
    file_path: str
    line_number: int
    line_content: str  # Masked
    pattern_name: str
    commit_hash: Optional[str] = None
    author: Optional[str] = None
    commit_date: Optional[datetime] = None
    is_false_positive: bool = False
    remediation: str = ""


@dataclass
class ScanResult:
    """Result of a secrets scan."""

    scan_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: ScanStatus = ScanStatus.PENDING
    files_scanned: int = 0
    findings: list[Finding] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    scan_path: str = ""
    include_history: bool = False


# Default patterns for detecting secrets
DEFAULT_PATTERNS: list[SecretPattern] = [
    # API Keys
    SecretPattern(
        name="Generic API Key",
        pattern=r'(?i)(api[_-]?key|apikey)["\s:=]+["\']?([a-zA-Z0-9_\-]{20,})["\']?',
        secret_type=SecretType.API_KEY,
        severity=SeverityLevel.HIGH,
        description="Generic API key pattern",
        false_positive_patterns=[r"example", r"test", r"fake", r"dummy", r"xxx"],
    ),
    SecretPattern(
        name="AWS Access Key",
        pattern=r"(?<![A-Z0-9])[A-Z0-9]{20}(?![A-Z0-9])",
        secret_type=SecretType.AWS_KEY,
        severity=SeverityLevel.CRITICAL,
        description="AWS Access Key ID",
    ),
    SecretPattern(
        name="AWS Secret Key",
        pattern=r'(?i)aws[_-]?secret[_-]?access[_-]?key["\s:=]+["\']?([a-zA-Z0-9/+=]{40})["\']?',
        secret_type=SecretType.AWS_KEY,
        severity=SeverityLevel.CRITICAL,
        description="AWS Secret Access Key",
    ),
    SecretPattern(
        name="Azure Subscription Key",
        pattern=r"(?i)azure[_-]?subscription[_-]?key[\"\\s:=]+[\"\']?([a-zA-Z0-9]{32})[\"\']?",
        secret_type=SecretType.AZURE_KEY,
        severity=SeverityLevel.CRITICAL,
        description="Azure Subscription Key",
    ),
    SecretPattern(
        name="GCP API Key",
        pattern=r"AIza[0-9A-Za-z_-]{35}",
        secret_type=SecretType.GCP_KEY,
        severity=SeverityLevel.CRITICAL,
        description="Google Cloud Platform API Key",
    ),
    # Tokens
    SecretPattern(
        name="JWT Token",
        pattern=r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*",
        secret_type=SecretType.JWT_TOKEN,
        severity=SeverityLevel.HIGH,
        description="JSON Web Token",
    ),
    SecretPattern(
        name="GitHub Token",
        pattern=r"gh[pousr]_[a-zA-Z0-9]{36,}",
        secret_type=SecretType.OAUTH_TOKEN,
        severity=SeverityLevel.CRITICAL,
        description="GitHub Personal Access Token",
    ),
    SecretPattern(
        name="Slack Token",
        pattern=r"xox[baprs]-[0-9]{10,13}-[a-zA-Z0-9-]+",
        secret_type=SecretType.OAUTH_TOKEN,
        severity=SeverityLevel.HIGH,
        description="Slack Token",
    ),
    # Private Keys
    SecretPattern(
        name="RSA Private Key",
        pattern=r"-----BEGIN RSA PRIVATE KEY-----",
        secret_type=SecretType.PRIVATE_KEY,
        severity=SeverityLevel.CRITICAL,
        description="RSA Private Key header",
    ),
    SecretPattern(
        name="SSH Private Key",
        pattern=r"-----BEGIN (OPENSSH|DSA|EC|PGP) PRIVATE KEY-----",
        secret_type=SecretType.SSH_KEY,
        severity=SeverityLevel.CRITICAL,
        description="SSH/DSA/EC Private Key header",
    ),
    SecretPattern(
        name="PEM Certificate",
        pattern=r"-----BEGIN CERTIFICATE-----",
        secret_type=SecretType.PRIVATE_KEY,
        severity=SeverityLevel.MEDIUM,
        description="PEM Certificate (check for private key)",
    ),
    # Passwords
    SecretPattern(
        name="Password Assignment",
        pattern=r'(?i)(password|passwd|pwd)["\s:=]+["\']?([^\s"\']{8,})["\']?',
        secret_type=SecretType.PASSWORD,
        severity=SeverityLevel.HIGH,
        description="Hardcoded password",
        false_positive_patterns=[
            r"password123",
            r"\$\{",
            r"os\.environ",
            r"getenv",
        ],
    ),
    SecretPattern(
        name="Database URL",
        pattern=r"(?i)(postgres|mysql|mongodb|redis)://[^:]+:[^@]+@[^/]+",
        secret_type=SecretType.DATABASE_URL,
        severity=SeverityLevel.CRITICAL,
        description="Database connection URL with credentials",
    ),
    # Crypto
    SecretPattern(
        name="Bybit API Key",
        pattern=r"(?i)bybit[_-]?api[_-]?key[\"\\s:=]+[\"\']?([a-zA-Z0-9]{18,})[\"\']?",
        secret_type=SecretType.API_KEY,
        severity=SeverityLevel.CRITICAL,
        description="Bybit exchange API key",
    ),
    SecretPattern(
        name="Bybit Secret",
        pattern=r"(?i)bybit[_-]?api[_-]?secret[\"\\s:=]+[\"\']?([a-zA-Z0-9]{32,})[\"\']?",
        secret_type=SecretType.API_KEY,
        severity=SeverityLevel.CRITICAL,
        description="Bybit exchange API secret",
    ),
    SecretPattern(
        name="DeepSeek API Key",
        pattern=r"(?i)deepseek[_-]?api[_-]?key[\"\\s:=]+[\"\']?([a-zA-Z0-9_-]{30,})[\"\']?",
        secret_type=SecretType.API_KEY,
        severity=SeverityLevel.HIGH,
        description="DeepSeek API key",
    ),
    SecretPattern(
        name="OpenAI API Key",
        pattern=r"sk-[a-zA-Z0-9]{48}",
        secret_type=SecretType.API_KEY,
        severity=SeverityLevel.CRITICAL,
        description="OpenAI API key",
    ),
    SecretPattern(
        name="Anthropic API Key",
        pattern=r"sk-ant-[a-zA-Z0-9_-]{90,}",
        secret_type=SecretType.API_KEY,
        severity=SeverityLevel.CRITICAL,
        description="Anthropic Claude API key",
    ),
    SecretPattern(
        name="Generic Secret",
        pattern=r'(?i)(secret|token|auth)[_-]?key["\s:=]+["\']?([a-zA-Z0-9_\-]{16,})["\']?',
        secret_type=SecretType.GENERIC_SECRET,
        severity=SeverityLevel.MEDIUM,
        description="Generic secret/token pattern",
        false_positive_patterns=[r"example", r"placeholder"],
    ),
    # === DeepSeek Recommendations: Enhanced Secret Scanner ===
    # AWS STS Tokens
    SecretPattern(
        name="AWS STS Session Token",
        pattern=r"(?i)aws[_-]?session[_-]?token[\"\\s:=]+[\"\']?([a-zA-Z0-9/+=]{100,})[\"\']?",
        secret_type=SecretType.AWS_KEY,
        severity=SeverityLevel.CRITICAL,
        description="AWS Security Token Service session token",
    ),
    SecretPattern(
        name="AWS STS Credentials Block",
        pattern=r"(?i)(AccessKeyId|SecretAccessKey|SessionToken)[\"\\s:=]+[\"\']?([a-zA-Z0-9/+=]{16,})[\"\']?",
        secret_type=SecretType.AWS_KEY,
        severity=SeverityLevel.CRITICAL,
        description="AWS STS credentials in JSON/YAML format",
    ),
    # Docker Registry Credentials
    SecretPattern(
        name="Docker Auth Config",
        pattern=r'"auth"\s*:\s*"([a-zA-Z0-9+/=]{20,})"',
        secret_type=SecretType.GENERIC_SECRET,
        severity=SeverityLevel.CRITICAL,
        description="Docker registry authentication (base64)",
    ),
    SecretPattern(
        name="Docker Hub Token",
        pattern=r"dckr_pat_[a-zA-Z0-9_-]{40,}",
        secret_type=SecretType.OAUTH_TOKEN,
        severity=SeverityLevel.CRITICAL,
        description="Docker Hub Personal Access Token",
    ),
    SecretPattern(
        name="Docker Registry URL with Creds",
        pattern=r"docker\.io/[^:]+:[^@]+@",
        secret_type=SecretType.DATABASE_URL,
        severity=SeverityLevel.CRITICAL,
        description="Docker registry URL with embedded credentials",
    ),
    # CI/CD Pipeline Tokens
    SecretPattern(
        name="GitLab CI Token",
        pattern=r"glpat-[a-zA-Z0-9_-]{20,}",
        secret_type=SecretType.OAUTH_TOKEN,
        severity=SeverityLevel.CRITICAL,
        description="GitLab Personal Access Token",
    ),
    SecretPattern(
        name="GitLab Runner Token",
        pattern=r"GR1348941[a-zA-Z0-9_-]{20,}",
        secret_type=SecretType.OAUTH_TOKEN,
        severity=SeverityLevel.CRITICAL,
        description="GitLab Runner Registration Token",
    ),
    SecretPattern(
        name="Jenkins Token",
        pattern=r"(?i)jenkins[_-]?token[\"\\s:=]+[\"\']?([a-f0-9]{32,})[\"\']?",
        secret_type=SecretType.OAUTH_TOKEN,
        severity=SeverityLevel.HIGH,
        description="Jenkins API Token",
    ),
    SecretPattern(
        name="CircleCI Token",
        pattern=r"(?i)circle[_-]?ci[_-]?token[\"\\s:=]+[\"\']?([a-f0-9]{40})[\"\']?",
        secret_type=SecretType.OAUTH_TOKEN,
        severity=SeverityLevel.HIGH,
        description="CircleCI API Token",
    ),
    SecretPattern(
        name="Travis CI Token",
        pattern=r"(?i)travis[_-]?token[\"\\s:=]+[\"\']?([a-zA-Z0-9_-]{20,})[\"\']?",
        secret_type=SecretType.OAUTH_TOKEN,
        severity=SeverityLevel.HIGH,
        description="Travis CI API Token",
    ),
    SecretPattern(
        name="GitHub Actions Secret",
        pattern=r"\$\{\{\s*secrets\.[A-Z_]+\s*\}\}",
        secret_type=SecretType.GENERIC_SECRET,
        severity=SeverityLevel.INFO,
        description="GitHub Actions secret reference (for audit)",
    ),
    # Database Connection Strings with Special Chars
    SecretPattern(
        name="SQL Server Connection String",
        pattern=r"(?i)(Server|Data Source)=[^;]+;.*(Password|Pwd)=[^;]+",
        secret_type=SecretType.CONNECTION_STRING,
        severity=SeverityLevel.CRITICAL,
        description="SQL Server connection string with password",
    ),
    SecretPattern(
        name="PostgreSQL Connection String",
        pattern=r"postgresql://[^:]+:[^@]+@[^/]+/[^\s\"']+",
        secret_type=SecretType.DATABASE_URL,
        severity=SeverityLevel.CRITICAL,
        description="PostgreSQL connection URL with credentials",
    ),
    SecretPattern(
        name="MongoDB Atlas URI",
        pattern=r"mongodb\+srv://[^:]+:[^@]+@[^/]+\.[^/]+",
        secret_type=SecretType.DATABASE_URL,
        severity=SeverityLevel.CRITICAL,
        description="MongoDB Atlas connection string",
    ),
    SecretPattern(
        name="Redis Auth URL",
        pattern=r"redis://:[^@]+@[^:/]+",
        secret_type=SecretType.DATABASE_URL,
        severity=SeverityLevel.HIGH,
        description="Redis connection with password",
    ),
    # Additional Cloud Providers
    SecretPattern(
        name="Heroku API Key",
        pattern=r"(?i)heroku[_-]?api[_-]?key[\"\\s:=]+[\"\']?([a-f0-9-]{36})[\"\']?",
        secret_type=SecretType.API_KEY,
        severity=SeverityLevel.HIGH,
        description="Heroku API Key (UUID format)",
    ),
    SecretPattern(
        name="DigitalOcean Token",
        pattern=r"dop_v1_[a-f0-9]{64}",
        secret_type=SecretType.OAUTH_TOKEN,
        severity=SeverityLevel.CRITICAL,
        description="DigitalOcean Personal Access Token",
    ),
    SecretPattern(
        name="Stripe API Key",
        pattern=r"sk_live_[a-zA-Z0-9]{24,}",
        secret_type=SecretType.API_KEY,
        severity=SeverityLevel.CRITICAL,
        description="Stripe Live Secret Key",
    ),
    SecretPattern(
        name="Twilio Auth Token",
        pattern=r"(?i)twilio[_-]?auth[_-]?token[\"\\s:=]+[\"\']?([a-f0-9]{32})[\"\']?",
        secret_type=SecretType.API_KEY,
        severity=SeverityLevel.HIGH,
        description="Twilio Authentication Token",
    ),
    SecretPattern(
        name="SendGrid API Key",
        pattern=r"SG\.[a-zA-Z0-9_-]{22}\.[a-zA-Z0-9_-]{43}",
        secret_type=SecretType.API_KEY,
        severity=SeverityLevel.HIGH,
        description="SendGrid API Key",
    ),
    # Crypto & Blockchain
    SecretPattern(
        name="Ethereum Private Key",
        pattern=r"(?i)(eth[_-]?)?private[_-]?key[\"\\s:=]+[\"\']?(0x)?[a-fA-F0-9]{64}[\"\']?",
        secret_type=SecretType.CRYPTO_KEY,
        severity=SeverityLevel.CRITICAL,
        description="Ethereum/EVM private key",
    ),
    SecretPattern(
        name="Bitcoin WIF Key",
        pattern=r"[5KL][1-9A-HJ-NP-Za-km-z]{50,51}",
        secret_type=SecretType.CRYPTO_KEY,
        severity=SeverityLevel.CRITICAL,
        description="Bitcoin Wallet Import Format private key",
    ),
    SecretPattern(
        name="Mnemonic Seed Phrase",
        pattern=r"(?i)(mnemonic|seed[_-]?phrase)[\"\\s:=]+[\"\']?([a-z]+\s+){11,23}[a-z]+[\"\']?",
        secret_type=SecretType.CRYPTO_KEY,
        severity=SeverityLevel.CRITICAL,
        description="BIP39 mnemonic seed phrase",
    ),
    # Encryption Keys
    SecretPattern(
        name="Base64 Encoded Key (32+ bytes)",
        pattern=r"(?i)(encryption[_-]?key|master[_-]?key|secret[_-]?key)[\"\\s:=]+[\"\']?([a-zA-Z0-9+/]{43,}=*)[\"\']?",
        secret_type=SecretType.CRYPTO_KEY,
        severity=SeverityLevel.CRITICAL,
        description="Base64 encoded encryption key",
    ),
    SecretPattern(
        name="Fernet Key",
        pattern=r"[a-zA-Z0-9_-]{43}=",
        secret_type=SecretType.CRYPTO_KEY,
        severity=SeverityLevel.HIGH,
        description="Fernet encryption key (Python cryptography)",
        false_positive_patterns=[r"example", r"test", r"placeholder"],
    ),
]


# Files to exclude from scanning
DEFAULT_EXCLUDE_PATTERNS = [
    r"\.git/",
    r"\.venv/",
    r"venv/",
    r"node_modules/",
    r"__pycache__/",
    r"\.pyc$",
    r"\.pyo$",
    r"\.egg-info/",
    r"dist/",
    r"build/",
    r"\.tox/",
    r"\.pytest_cache/",
    r"\.mypy_cache/",
    r"\.coverage",
    r"htmlcov/",
    r"\.idea/",
    r"\.vscode/",
    r"\.lock$",
    r"package-lock\.json$",
    r"yarn\.lock$",
    r"requirements.*\.txt$",  # Usually don't contain secrets
    r"\.md$",  # Documentation
    r"\.rst$",
    r"LICENSE",
    r"\.svg$",
    r"\.png$",
    r"\.jpg$",
    r"\.gif$",
    r"\.ico$",
    r"\.woff",
    r"\.ttf$",
    r"\.eot$",
]


class GitSecretsScanner:
    """
    Git Secrets Scanner Service.

    Scans repositories for leaked credentials and secrets.
    """

    _instance: Optional["GitSecretsScanner"] = None

    def __init__(self):
        self._patterns: list[SecretPattern] = list(DEFAULT_PATTERNS)
        self._exclude_patterns: list[str] = list(DEFAULT_EXCLUDE_PATTERNS)
        self._false_positives: set[str] = set()
        self._scan_history: list[ScanResult] = []
        self._scan_count = 0

    @classmethod
    def get_instance(cls) -> "GitSecretsScanner":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def add_pattern(self, pattern: SecretPattern) -> None:
        """Add a custom pattern."""
        self._patterns.append(pattern)
        logger.info(f"Added pattern: {pattern.name}")

    def remove_pattern(self, pattern_name: str) -> bool:
        """Remove a pattern by name."""
        for i, p in enumerate(self._patterns):
            if p.name == pattern_name:
                del self._patterns[i]
                logger.info(f"Removed pattern: {pattern_name}")
                return True
        return False

    def add_exclude_pattern(self, pattern: str) -> None:
        """Add a file exclusion pattern."""
        self._exclude_patterns.append(pattern)

    def mark_false_positive(self, finding_id: str) -> None:
        """Mark a finding as false positive."""
        self._false_positives.add(finding_id)

    def _should_exclude_file(self, file_path: str) -> bool:
        """Check if file should be excluded."""
        for pattern in self._exclude_patterns:
            if re.search(pattern, file_path):
                return True
        return False

    def _is_false_positive(self, line: str, pattern: SecretPattern) -> bool:
        """Check if a match is likely a false positive."""
        line_lower = line.lower()

        for fp_pattern in pattern.false_positive_patterns:
            if re.search(fp_pattern, line_lower):
                return True

        # Common false positive indicators
        fp_indicators = [
            "example",
            "test",
            "fake",
            "dummy",
            "placeholder",
            "your_",
            "xxx",
            "....",
            "****",
            "${",  # Environment variable
            "os.environ",
            "getenv",
            "config.",
            "settings.",
        ]

        for indicator in fp_indicators:
            if indicator in line_lower:
                return True

        return False

    def _mask_secret(self, line: str, secret_match: str) -> str:
        """Mask the secret in the line."""
        if len(secret_match) <= 8:
            masked = "****"
        else:
            masked = (
                secret_match[:4] + "*" * (len(secret_match) - 8) + secret_match[-4:]
            )
        return line.replace(secret_match, masked)

    def _get_remediation(self, secret_type: SecretType) -> str:
        """Get remediation advice for a secret type."""
        remediation = {
            SecretType.API_KEY: "Rotate the API key immediately and store in environment variable or KMS",
            SecretType.PASSWORD: "Change the password and use environment variables or secrets manager",
            SecretType.PRIVATE_KEY: "Revoke the key, generate a new one, and store securely",
            SecretType.AWS_KEY: "Rotate AWS credentials via IAM console and use AWS Secrets Manager",
            SecretType.AZURE_KEY: "Rotate via Azure portal and use Azure Key Vault",
            SecretType.GCP_KEY: "Revoke via GCP Console and use Secret Manager",
            SecretType.JWT_TOKEN: "Invalidate token and implement proper token rotation",
            SecretType.OAUTH_TOKEN: "Revoke token and regenerate through provider",
            SecretType.DATABASE_URL: "Change database password and use connection pooler with env vars",
            SecretType.CONNECTION_STRING: "Update credentials and use secure configuration",
            SecretType.GENERIC_SECRET: "Review and rotate if necessary, use secrets manager",
            SecretType.CRYPTO_KEY: "Rotate encryption key and re-encrypt data",
            SecretType.SSH_KEY: "Remove from authorized_keys, regenerate, and store securely",
        }
        return remediation.get(
            secret_type, "Review the finding and rotate credentials if necessary"
        )

    def scan_file(self, file_path: Path) -> list[Finding]:
        """Scan a single file for secrets."""
        findings = []

        if not file_path.exists() or not file_path.is_file():
            return findings

        if self._should_exclude_file(str(file_path)):
            return findings

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                for pattern in self._patterns:
                    matches = re.finditer(pattern.pattern, line)
                    for match in matches:
                        secret_value = match.group(0)

                        if self._is_false_positive(line, pattern):
                            continue

                        finding_id = f"{file_path}:{line_num}:{pattern.name}"

                        if finding_id in self._false_positives:
                            continue

                        finding = Finding(
                            finding_id=finding_id,
                            secret_type=pattern.secret_type,
                            severity=pattern.severity,
                            file_path=str(file_path),
                            line_number=line_num,
                            line_content=self._mask_secret(
                                line.strip()[:200], secret_value[:20]
                            ),
                            pattern_name=pattern.name,
                            remediation=self._get_remediation(pattern.secret_type),
                        )
                        findings.append(finding)

        except Exception as e:
            logger.warning(f"Error scanning {file_path}: {e}")

        return findings

    def scan_directory(
        self,
        directory: Path,
        recursive: bool = True,
    ) -> ScanResult:
        """Scan a directory for secrets."""
        self._scan_count += 1
        scan_id = f"scan-{self._scan_count}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        result = ScanResult(
            scan_id=scan_id,
            start_time=datetime.now(),
            status=ScanStatus.RUNNING,
            scan_path=str(directory),
        )

        try:
            files = []
            if recursive:
                for root, _, filenames in os.walk(directory):
                    for filename in filenames:
                        files.append(Path(root) / filename)
            else:
                files = [f for f in directory.iterdir() if f.is_file()]

            for file_path in files:
                if self._should_exclude_file(str(file_path)):
                    continue

                result.files_scanned += 1
                findings = self.scan_file(file_path)
                result.findings.extend(findings)

            result.status = ScanStatus.COMPLETED
            result.end_time = datetime.now()

        except Exception as e:
            result.status = ScanStatus.FAILED
            result.errors.append(str(e))
            result.end_time = datetime.now()
            logger.error(f"Scan failed: {e}")

        self._scan_history.append(result)
        return result

    def scan_git_history(
        self,
        repo_path: Path,
        max_commits: int = 100,
    ) -> ScanResult:
        """Scan git history for secrets."""
        self._scan_count += 1
        scan_id = f"history-scan-{self._scan_count}"

        result = ScanResult(
            scan_id=scan_id,
            start_time=datetime.now(),
            status=ScanStatus.RUNNING,
            scan_path=str(repo_path),
            include_history=True,
        )

        try:
            # Get commits
            git_log = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_path),
                    "log",
                    f"-{max_commits}",
                    "--pretty=format:%H|%an|%ai",
                ],
                capture_output=True,
                text=True,
            )

            if git_log.returncode != 0:
                result.status = ScanStatus.FAILED
                result.errors.append(f"Git log failed: {git_log.stderr}")
                result.end_time = datetime.now()
                return result

            commits = git_log.stdout.strip().split("\n")

            for commit_line in commits:
                if not commit_line:
                    continue

                parts = commit_line.split("|")
                if len(parts) < 3:
                    continue

                commit_hash = parts[0]
                author = parts[1]
                commit_date_str = parts[2]

                try:
                    commit_date = datetime.fromisoformat(commit_date_str.split()[0])
                except (ValueError, IndexError):
                    commit_date = None

                # Get diff for commit
                diff_result = subprocess.run(
                    [
                        "git",
                        "-C",
                        str(repo_path),
                        "show",
                        commit_hash,
                        "--pretty=format:",
                        "--name-only",
                    ],
                    capture_output=True,
                    text=True,
                )

                if diff_result.returncode != 0:
                    continue

                files_changed = diff_result.stdout.strip().split("\n")

                for file_path in files_changed:
                    if not file_path or self._should_exclude_file(file_path):
                        continue

                    # Get file content at this commit
                    show_result = subprocess.run(
                        [
                            "git",
                            "-C",
                            str(repo_path),
                            "show",
                            f"{commit_hash}:{file_path}",
                        ],
                        capture_output=True,
                        text=True,
                    )

                    if show_result.returncode != 0:
                        continue

                    result.files_scanned += 1
                    content = show_result.stdout

                    for line_num, line in enumerate(content.split("\n"), 1):
                        for pattern in self._patterns:
                            matches = re.finditer(pattern.pattern, line)
                            for match in matches:
                                secret_value = match.group(0)

                                if self._is_false_positive(line, pattern):
                                    continue

                                finding_id = f"{commit_hash}:{file_path}:{line_num}:{pattern.name}"

                                if finding_id in self._false_positives:
                                    continue

                                finding = Finding(
                                    finding_id=finding_id,
                                    secret_type=pattern.secret_type,
                                    severity=pattern.severity,
                                    file_path=file_path,
                                    line_number=line_num,
                                    line_content=self._mask_secret(
                                        line.strip()[:200], secret_value[:20]
                                    ),
                                    pattern_name=pattern.name,
                                    commit_hash=commit_hash,
                                    author=author,
                                    commit_date=commit_date,
                                    remediation=self._get_remediation(
                                        pattern.secret_type
                                    ),
                                )
                                result.findings.append(finding)

            result.status = ScanStatus.COMPLETED
            result.end_time = datetime.now()

        except FileNotFoundError:
            result.status = ScanStatus.FAILED
            result.errors.append("Git not found. Install git to scan history.")
            result.end_time = datetime.now()
        except Exception as e:
            result.status = ScanStatus.FAILED
            result.errors.append(str(e))
            result.end_time = datetime.now()
            logger.error(f"History scan failed: {e}")

        self._scan_history.append(result)
        return result

    def get_scan_history(self, limit: int = 10) -> list[ScanResult]:
        """Get recent scan history."""
        return self._scan_history[-limit:]

    def get_scan_by_id(self, scan_id: str) -> Optional[ScanResult]:
        """Get a specific scan by ID."""
        for scan in self._scan_history:
            if scan.scan_id == scan_id:
                return scan
        return None

    def get_statistics(self) -> dict:
        """Get scanning statistics."""
        total_findings = sum(len(s.findings) for s in self._scan_history)
        total_files = sum(s.files_scanned for s in self._scan_history)

        severity_counts = {level.value: 0 for level in SeverityLevel}
        type_counts = {st.value: 0 for st in SecretType}

        for scan in self._scan_history:
            for finding in scan.findings:
                severity_counts[finding.severity.value] += 1
                type_counts[finding.secret_type.value] += 1

        return {
            "total_scans": len(self._scan_history),
            "total_files_scanned": total_files,
            "total_findings": total_findings,
            "false_positives_marked": len(self._false_positives),
            "findings_by_severity": severity_counts,
            "findings_by_type": type_counts,
            "patterns_count": len(self._patterns),
        }

    def generate_report(
        self,
        scan_result: ScanResult,
        format_type: str = "json",
    ) -> str:
        """Generate a report from scan results."""
        if format_type == "json":
            return json.dumps(
                {
                    "scan_id": scan_result.scan_id,
                    "start_time": scan_result.start_time.isoformat(),
                    "end_time": scan_result.end_time.isoformat()
                    if scan_result.end_time
                    else None,
                    "status": scan_result.status.value,
                    "scan_path": scan_result.scan_path,
                    "files_scanned": scan_result.files_scanned,
                    "findings_count": len(scan_result.findings),
                    "findings": [
                        {
                            "finding_id": f.finding_id,
                            "secret_type": f.secret_type.value,
                            "severity": f.severity.value,
                            "file_path": f.file_path,
                            "line_number": f.line_number,
                            "line_content": f.line_content,
                            "pattern_name": f.pattern_name,
                            "commit_hash": f.commit_hash,
                            "author": f.author,
                            "remediation": f.remediation,
                        }
                        for f in scan_result.findings
                    ],
                    "errors": scan_result.errors,
                },
                indent=2,
            )

        elif format_type == "markdown":
            lines = [
                f"# Secret Scan Report: {scan_result.scan_id}",
                "",
                f"**Start Time:** {scan_result.start_time.isoformat()}",
                f"**End Time:** {scan_result.end_time.isoformat() if scan_result.end_time else 'N/A'}",
                f"**Status:** {scan_result.status.value}",
                f"**Path:** {scan_result.scan_path}",
                f"**Files Scanned:** {scan_result.files_scanned}",
                f"**Findings:** {len(scan_result.findings)}",
                "",
            ]

            if scan_result.findings:
                lines.append("## Findings")
                lines.append("")

                for finding in scan_result.findings:
                    lines.extend(
                        [
                            f"### {finding.severity.value.upper()}: {finding.pattern_name}",
                            "",
                            f"- **File:** `{finding.file_path}`",
                            f"- **Line:** {finding.line_number}",
                            f"- **Type:** {finding.secret_type.value}",
                            f"- **Content:** `{finding.line_content}`",
                            f"- **Remediation:** {finding.remediation}",
                            "",
                        ]
                    )

            if scan_result.errors:
                lines.append("## Errors")
                lines.append("")
                for error in scan_result.errors:
                    lines.append(f"- {error}")

            return "\n".join(lines)

        else:
            raise ValueError(f"Unknown format: {format_type}")

    def get_patterns(self) -> list[SecretPattern]:
        """Get all configured patterns."""
        return list(self._patterns)


# Singleton accessor
def get_secrets_scanner() -> GitSecretsScanner:
    """Get secrets scanner instance."""
    return GitSecretsScanner.get_instance()
