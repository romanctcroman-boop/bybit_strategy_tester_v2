#!/usr/bin/env python3
"""
🔍 Agent Configuration Verification Script

Verifies that all agent autonomy configuration files are in place.
Run after setting up agent configuration to ensure everything is correct.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
AGENT_DIR = PROJECT_ROOT / ".agent"

# Required configuration files
REQUIRED_FILES = {
    "Global Rules": PROJECT_ROOT / "AGENTS.MD",
    "Claude Config": AGENT_DIR / "Claude.md",
    "Gemini Config": AGENT_DIR / "Gemini.md",
    "Memory First Rule": AGENT_DIR / "rules" / "memory-first.md",
    "Autonomy Guidelines": AGENT_DIR / "rules" / "autonomy-guidelines.md",
    "Innovation Mode": AGENT_DIR / "rules" / "innovation-mode.md",
    "Session Handoff": AGENT_DIR / "rules" / "session-handoff.md",
    "Auto Documenter": AGENT_DIR / "skills" / "skills" / "auto-documenter" / "SKILL.md",
    "Trading Autonomy": AGENT_DIR / "skills" / "skills" / "trading-autonomy" / "SKILL.md",
    "Architecture Doc": AGENT_DIR / "docs" / "ARCHITECTURE.md",
    "Decisions Doc": AGENT_DIR / "docs" / "DECISIONS.md",
    "Changelog": AGENT_DIR / "docs" / "CHANGELOG.md",
    "API Doc": AGENT_DIR / "docs" / "API.md",
    "Models Doc": AGENT_DIR / "docs" / "MODELS.md",
    "Context Summary": AGENT_DIR / "memory" / "CONTEXT.md",
    "TODO List": AGENT_DIR / "memory" / "TODO.md",
}

# Required directories
REQUIRED_DIRS = {
    "Agent Directory": AGENT_DIR,
    "Rules Directory": AGENT_DIR / "rules",
    "Skills Directory": AGENT_DIR / "skills" / "skills",
    "Docs Directory": AGENT_DIR / "docs",
    "Memory Directory": AGENT_DIR / "memory",
    "Experiments Directory": AGENT_DIR / "experiments",
    "Reports Directory": AGENT_DIR / "reports",
}


def verify_configuration():
    """Verify all agent configuration files and directories."""
    print("=" * 60)
    print("🔍 AGENT CONFIGURATION VERIFICATION")
    print("=" * 60)

    all_ok = True

    # Check directories
    print("\n📁 Directories:")
    for name, path in REQUIRED_DIRS.items():
        if path.exists():
            print(f"   ✅ {name}")
        else:
            print(f"   ❌ {name}: {path}")
            all_ok = False

    # Check files
    print("\n📄 Configuration Files:")
    for name, path in REQUIRED_FILES.items():
        if path.exists():
            size = path.stat().st_size
            print(f"   ✅ {name} ({size} bytes)")
        else:
            print(f"   ❌ {name}: {path}")
            all_ok = False

    # Count skills
    print("\n🎯 Agent Skills:")
    skills_dir = AGENT_DIR / "skills" / "skills"
    if skills_dir.exists():
        skill_count = sum(1 for d in skills_dir.iterdir() if d.is_dir())
        print(f"   ✅ {skill_count} skills installed")
    else:
        print("   ❌ Skills directory not found")
        all_ok = False

    # Summary
    print("\n" + "=" * 60)
    if all_ok:
        print("✅ ALL CONFIGURATION VERIFIED - Agent ready for maximum autonomy!")
    else:
        print("⚠️ SOME CONFIGURATION MISSING - Review above errors")
    print("=" * 60)

    return all_ok


if __name__ == "__main__":
    success = verify_configuration()
    sys.exit(0 if success else 1)
