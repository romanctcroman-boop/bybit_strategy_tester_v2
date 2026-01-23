"""
Security Audit Script - Check for sensitive data leaks
======================================================
Checks:
1. API keys in git history
2. .env file permissions
3. Hardcoded secrets in code
4. Sensitive files in git
"""

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

# Patterns for sensitive data
SENSITIVE_PATTERNS = [
    (r'api[_-]?key\s*=\s*["\']([a-zA-Z0-9_\-]{20,})["\']', "API Key"),
    (r'secret[_-]?key\s*=\s*["\']([a-zA-Z0-9_\-]{20,})["\']', "Secret Key"),
    (r'password\s*=\s*["\']([^"\']{8,})["\']', "Password"),
    (r'token\s*=\s*["\']([a-zA-Z0-9_\-]{20,})["\']', "Token"),
    (r"Bearer\s+([a-zA-Z0-9_\-\.]{20,})", "Bearer Token"),
]


def check_env_permissions():
    """Check .env file permissions"""
    print("\n" + "=" * 80)
    print("1. Checking .env file permissions")
    print("=" * 80)

    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        print("⚠️  .env file not found")
        return False

    try:
        # Check Windows ACL
        result = subprocess.run(
            ["icacls", str(env_file)], capture_output=True, text=True, shell=True
        )

        print(f"\n.env permissions:\n{result.stdout}")

        # Check if too permissive
        if "Everyone" in result.stdout or "Users" in result.stdout:
            print("❌ WARNING: .env file has too permissive permissions!")
            print(
                '   Recommended: icacls .env /inheritance:r /grant:r "$($env:USERNAME):(R,W)"'
            )
            return False
        else:
            print("✅ .env permissions look restricted")
            return True

    except Exception as e:
        print(f"❌ Error checking permissions: {e}")
        return False


def scan_git_history():
    """Scan git history for sensitive data"""
    print("\n" + "=" * 80)
    print("2. Scanning git history for sensitive data")
    print("=" * 80)

    try:
        # Get all git history
        result = subprocess.run(
            [
                "git",
                "log",
                "--all",
                "--pretty=format:%H %s",
                "--",
                "*.py",
                "*.env*",
                "*.json",
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )

        commits = result.stdout.strip().split("\n")
        print(f"\n📊 Scanning {len(commits)} commits...")

        issues_found = []

        # Sample first 50 commits
        for commit_line in commits[:50]:
            if not commit_line:
                continue

            commit_hash = commit_line.split()[0]

            # Check commit diff
            diff_result = subprocess.run(
                ["git", "show", commit_hash],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
            )

            # Check for patterns
            for pattern, name in SENSITIVE_PATTERNS:
                matches = re.findall(pattern, diff_result.stdout, re.IGNORECASE)
                if matches:
                    issues_found.append(
                        {"commit": commit_hash[:7], "type": name, "count": len(matches)}
                    )

        if issues_found:
            print(f"\n❌ Found {len(issues_found)} potential issues:")
            for issue in issues_found[:10]:  # Show first 10
                print(
                    f"   - {issue['type']} in commit {issue['commit']} ({issue['count']} matches)"
                )
            return False
        else:
            print("✅ No obvious secrets found in recent git history")
            return True

    except Exception as e:
        print(f"❌ Error scanning git: {e}")
        return False


def scan_current_code():
    """Scan current codebase for hardcoded secrets"""
    print("\n" + "=" * 80)
    print("3. Scanning current codebase for hardcoded secrets")
    print("=" * 80)

    issues_found = []
    files_scanned = 0

    # Scan Python files
    for py_file in PROJECT_ROOT.rglob("*.py"):
        # Skip virtual environments and cache
        if any(
            skip in str(py_file) for skip in [".venv", "__pycache__", "node_modules"]
        ):
            continue

        try:
            content = py_file.read_text(encoding="utf-8")
            files_scanned += 1

            for pattern, name in SENSITIVE_PATTERNS:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    # Filter out obvious test/example values
                    real_matches = [
                        m
                        for m in matches
                        if not any(
                            test in m.lower()
                            for test in ["test", "example", "dummy", "xxx", "***"]
                        )
                    ]

                    if real_matches:
                        issues_found.append(
                            {
                                "file": str(py_file.relative_to(PROJECT_ROOT)),
                                "type": name,
                                "count": len(real_matches),
                            }
                        )
        except Exception:
            pass

    print(f"\n📊 Scanned {files_scanned} Python files")

    if issues_found:
        print(f"\n⚠️  Found {len(issues_found)} potential hardcoded secrets:")
        for issue in issues_found[:10]:
            print(f"   - {issue['type']} in {issue['file']} ({issue['count']} matches)")
        return False
    else:
        print("✅ No obvious hardcoded secrets found")
        return True


def check_sensitive_files():
    """Check for sensitive files that shouldn't be in git"""
    print("\n" + "=" * 80)
    print("4. Checking for sensitive files in git")
    print("=" * 80)

    sensitive_files = [
        ".env",
        ".env.local",
        "*.pem",
        "*.key",
        "*.crt",
        "id_rsa",
        "id_dsa",
        "*.pfx",
    ]

    try:
        result = subprocess.run(
            ["git", "ls-files"], capture_output=True, text=True, cwd=PROJECT_ROOT
        )

        tracked_files = result.stdout.strip().split("\n")
        issues = []

        for pattern in sensitive_files:
            for file in tracked_files:
                if pattern.startswith("*"):
                    if file.endswith(pattern[1:]):
                        issues.append(file)
                else:
                    if pattern in file:
                        issues.append(file)

        if issues:
            print(f"\n⚠️  Found {len(issues)} sensitive files tracked in git:")
            for file in issues[:10]:
                print(f"   - {file}")
            print("\n   Consider adding to .gitignore and removing from history")
            return False
        else:
            print("✅ No obvious sensitive files in git")
            return True

    except Exception as e:
        print(f"❌ Error checking files: {e}")
        return False


def generate_report():
    """Generate security audit report"""
    print("\n" + "=" * 80)
    print("📄 Generating Security Audit Report")
    print("=" * 80)

    results = {
        "timestamp": datetime.now().isoformat(),
        "checks": {
            "env_permissions": check_env_permissions(),
            "git_history": scan_git_history(),
            "current_code": scan_current_code(),
            "sensitive_files": check_sensitive_files(),
        },
    }

    # Save report
    report_file = (
        PROJECT_ROOT / f"security_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # Summary
    print("\n" + "=" * 80)
    print("📊 SECURITY AUDIT SUMMARY")
    print("=" * 80)

    passed = sum(1 for v in results["checks"].values() if v)
    total = len(results["checks"])

    print(f"\nChecks passed: {passed}/{total}")
    print(f"Report saved: {report_file.name}")

    if passed < total:
        print("\n⚠️  ACTION REQUIRED: Some security checks failed!")
        print("    Review the report and fix issues before production deployment.")
    else:
        print("\n✅ All security checks passed!")

    return results


if __name__ == "__main__":
    print("=" * 80)
    print("🔒 SECURITY AUDIT - bybit_strategy_tester_v2")
    print("=" * 80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = generate_report()

    # Exit code
    exit(0 if all(results["checks"].values()) else 1)
