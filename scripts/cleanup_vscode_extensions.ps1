# ============================================
# VS Code Extension Cleanup
# ============================================
# Removes extensions NOT needed for this Python/FastAPI project
# Run: .\scripts\cleanup_vscode_extensions.ps1
# To preview only: .\scripts\cleanup_vscode_extensions.ps1 -DryRun
# ============================================

param(
    [switch]$DryRun = $false
)

# Find code.cmd
$codePaths = @(
    "$env:LOCALAPPDATA\Programs\Microsoft VS Code\bin\code.cmd",
    "C:\Program Files\Microsoft VS Code\bin\code.cmd",
    "$env:LOCALAPPDATA\Programs\Microsoft VS Code Insiders\bin\code-insiders.cmd"
)
$codeCmd = $null
foreach ($p in $codePaths) {
    if (Test-Path $p) { $codeCmd = $p; break }
}
if (-not $codeCmd) {
    # Try PATH
    $codeCmd = Get-Command code -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
}
if (-not $codeCmd) {
    Write-Host "[ERROR] VS Code not found. Run manually: code --uninstall-extension <id>" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  VS Code Extension Cleanup" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
if ($DryRun) {
    Write-Host "  MODE: DRY RUN (preview only)" -ForegroundColor Yellow
}
Write-Host ""

# ─────────────────────────────────────────────
# SAFE TO REMOVE — Languages not used in project
# ─────────────────────────────────────────────
$safeToRemove = @(
    # C/C++/Embedded (no C/C++ code in project — files found are in .venv314 dependencies)
    "ms-vscode.cpptools",
    "ms-vscode.cpptools-extension-pack",
    "ms-vscode.cpptools-themes",
    "ms-vscode.cmake-tools",
    "josetr.cmake-language-support-vscode",
    "ms-vscode.makefile-tools",
    "ms-vscode.vscode-embedded-tools",
    "ms-vscode.vscode-serial-monitor",
    "marus25.cortex-debug",
    "mcu-debug.debug-tracker-vscode",
    "mcu-debug.memory-view",
    "mcu-debug.peripheral-viewer",
    "mcu-debug.rtos-views",

    # Java (no Java files in project)
    "redhat.java",
    "vscjava.vscode-java-debug",
    "vscjava.vscode-java-test",
    "oracle.oracle-java",

    # C#/.NET (no C# files in project)
    "ms-dotnettools.csdevkit",
    "ms-dotnettools.csharp",
    "ms-dotnettools.vscode-dotnet-runtime",
    "oleg-shilo.cs-script",

    # Dart (no Dart files)
    "dart-code.dart-code",

    # Go (no Go files — the one .go found is in .venv314)
    "golang.go",

    # Hack language (no .hack files)
    "pranayagarwal.vscode-hack",

    # TTK91 Finnish assembly language (!!)
    "3nd3r1.ttk91-vscode",

    # Tkinter/CustomTkinter (no GUI code in project)
    "ashhaddevlab.customtkinter-snippets",
    "nikolapaunovic.tkinter-snippets",
    "REMOVED.ttk",

    # PineScript (not used — project has its OWN strategy engine)
    "tradesdontlie.pinescript-v6-vscode",

    # Cake Build (C# build tool — not used)
    "cake-build.cake-vscode",

    # Kubernetes/Helm (no k8s manifests in project)
    "ms-kubernetes-tools.vscode-kubernetes-tools",
    "tim-koehler.helm-intellisense",

    # PDF/DOCX viewers (not needed for coding)
    "adamraichu.pdf-viewer-1.1.2",       # duplicate PDF viewer
    "tomoki1207.pdf",                      # another PDF viewer
    "shahilkumar.docxreader",
    "docx-mt5.docx",
    "muhammad-ahmad.xlsx-viewer",
    "yzane.markdown-pdf",                  # markdown to PDF export

    # Python image preview (not used)
    "076923.python-image-preview",

    # Firefox debugger (project uses Chrome/Edge)
    "firefox-devtools.vscode-firefox-debug",

    # Revature Labs (education platform — not needed)
    "revature-labs-non-prod.revature-python-labs-non-prod",
    "revaturepro.revature-python-labs",

    # Misc not needed
    "priyankark.aircodum-app",             # AI code review (have Copilot)
    "rohan-patnaik.decensored-deepseekr1-for-vscode",  # DeepSeek (have Copilot)
    "kingleo.qwen",                        # Qwen AI (have Copilot)
    "wtetsu.tempfile",                     # temp file creator
    "yy0931.mplstyle",                     # matplotlib style (no charts in IDE)
    "local-rev.local-python-rev",          # Python revision tool
    "ms-vscode.vscode-speech",             # Speech-to-text (not needed for coding)

    # Duplicate DB tools (keep only what project uses: SQLite + PostgreSQL)
    "ms-mssql.mssql",                     # MS SQL — project uses SQLite
    "ms-mssql.data-workspace-vscode",
    "ms-mssql.sql-bindings-vscode",
    "ms-mssql.sql-database-projects-vscode",
    "jerry-nixon.init-data-api-builder",   # MS data API builder
    "mtxr.sqltools",                       # duplicate of cweijan DB client

    # Jupyter (no .ipynb files in project)
    "ms-toolsai.jupyter",
    "ms-toolsai.jupyter-keymap",
    "ms-toolsai.jupyter-renderers",
    "ms-toolsai.vscode-jupyter-cell-tags",
    "ms-toolsai.vscode-jupyter-slideshow",

    # Codespaces (local development only)
    "github.codespaces",

    # Docker Labs AI (experimental — keep main docker extension)
    "docker.labs-ai-tools-vscode",

    # Deprecated Python formatters (ruff replaces all of these)
    "ms-python.autopep8",
    "ms-python.black-formatter",
    "ms-python.isort"
)

# ─────────────────────────────────────────────
# KEEP — Essential for this project
# ─────────────────────────────────────────────
# ms-python.python              — Python core
# ms-python.vscode-pylance      — Python IntelliSense
# ms-python.debugpy              — Python debugger
# ms-python.vscode-python-envs   — Env manager
# ms-python.mypy-type-checker    — Type checking
# charliermarsh.ruff             — Linting + formatting (replaces autopep8/black/isort)
# github.copilot                 — AI assistant
# github.copilot-chat            — AI chat
# github.vscode-pull-request-github — PR management
# github.vscode-github-actions   — CI/CD
# eamodio.gitlens                — Git blame/history
# donjayamanne.githistory        — Git log viewer
# ms-azuretools.vscode-docker    — Docker (Dockerfile exists)
# ms-azuretools.vscode-containers — Dev containers
# ms-vscode-remote.remote-containers — Remote containers
# ms-vscode.powershell           — PowerShell scripts
# ms-vscode.live-server          — Frontend preview
# ms-ceintl.vscode-language-pack-ru — Russian UI
# pkief.material-icon-theme      — Icons
# uloco.theme-bluloco-dark       — Theme
# usernamehw.errorlens           — Inline errors
# streetsidesoftware.code-spell-checker — Spell check
# gruntfuggly.todo-tree          — TODO tracking
# mechatroner.rainbow-csv        — CSV files
# tamasfe.even-better-toml       — pyproject.toml
# redhat.vscode-yaml             — YAML files
# dotjoshjohnson.xml             — XML files
# eriklynd.json-tools            — JSON formatting
# davidanson.vscode-markdownlint — Markdown linting
# esbenp.prettier-vscode         — JS/HTML formatting (frontend/)
# dbaeumer.vscode-eslint         — JS linting (frontend/)
# christian-kohler.npm-intellisense — npm (if frontend uses npm)
# formulahendry.code-runner      — Quick script execution
# cweijan.vscode-mysql-client2   — DB client (SQLite + Redis)
# cweijan.vscode-redis-client    — Redis client
# cweijan.dbclient-jdbc          — JDBC connector
# ms-ossdata.vscode-pgsql        — PostgreSQL (deployment target)
# ckolkman.vscode-postgres       — PostgreSQL alt
# redis.redis-for-vscode         — Redis
# cottonable.perplexity          — AI search
# kingleo.openurl                — URL opener
# donjayamanne.python-environment-manager — Env manager

Write-Host "Extensions to REMOVE: $($safeToRemove.Count)" -ForegroundColor Red
Write-Host ""

$removed = 0
$failed = 0

foreach ($ext in $safeToRemove) {
    # Check if installed (folder exists)
    $found = Get-ChildItem "$env:USERPROFILE\.vscode\extensions" -Directory -Filter "$ext-*" -ErrorAction SilentlyContinue
    if (-not $found) {
        continue  # Not installed, skip silently
    }

    if ($DryRun) {
        Write-Host "  [WOULD REMOVE] $ext" -ForegroundColor Yellow
        $removed++
    }
    else {
        Write-Host "  [REMOVING] $ext" -ForegroundColor Red -NoNewline
        & $codeCmd --uninstall-extension $ext --force 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host " OK" -ForegroundColor Green
            $removed++
        }
        else {
            Write-Host " FAILED" -ForegroundColor Red
            $failed++
        }
    }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
if ($DryRun) {
    Write-Host "  Would remove: $removed extensions" -ForegroundColor Yellow
    Write-Host "  Run without -DryRun to actually remove" -ForegroundColor Gray
}
else {
    Write-Host "  Removed: $removed extensions" -ForegroundColor Green
    if ($failed -gt 0) {
        Write-Host "  Failed: $failed" -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "  RESTART VS CODE to apply changes!" -ForegroundColor Yellow
}
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
