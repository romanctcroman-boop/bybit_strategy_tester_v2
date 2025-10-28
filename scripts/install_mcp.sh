#!/bin/bash
# Unix/Linux/Mac version of MCP installation script

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║     MCP INTEGRATION SETUP                                ║"
echo "║     Perplexity AI + Capiton GitHub                       ║"
echo "╚══════════════════════════════════════════════════════════╝"

# Step 1: Check Node.js
echo ""
echo "[1/5] Checking Node.js installation..."
if ! command -v node &> /dev/null; then
    echo "✗ Node.js not found!"
    echo "Please install Node.js from: https://nodejs.org/"
    exit 1
fi
NODE_VERSION=$(node --version)
echo "✓ Node.js installed: $NODE_VERSION"

# Step 2: Check npm
echo ""
echo "[2/5] Checking npm installation..."
if ! command -v npm &> /dev/null; then
    echo "✗ npm not found!"
    exit 1
fi
NPM_VERSION=$(npm --version)
echo "✓ npm installed: $NPM_VERSION"

# Step 3: Install MCP servers
echo ""
echo "[3/5] Installing MCP servers..."
echo "  → Installing Perplexity server..."
npm install -g @modelcontextprotocol/server-perplexity-ask

echo "  → Installing Capiton GitHub server..."
npm install -g @modelcontextprotocol/server-capiton-github

echo "✓ MCP servers installed!"

# Step 4: Check .env file
echo ""
echo "[4/5] Checking environment configuration..."
if [ ! -f ".env" ]; then
    echo "  → .env file not found, creating from example..."
    cp .env.example .env
    echo "  ⚠ Please edit .env and add your API keys!"
    echo "    - PERPLEXITY_API_KEY: https://www.perplexity.ai/settings/api"
    echo "    - GITHUB_TOKEN: https://github.com/settings/tokens"
else
    echo "✓ .env file exists"
    
    # Check if keys are set
    if grep -q "PERPLEXITY_API_KEY=pplx-" .env; then
        echo "✓ PERPLEXITY_API_KEY configured"
    else
        echo "⚠ PERPLEXITY_API_KEY not configured"
    fi
    
    if grep -q "GITHUB_TOKEN=ghp_" .env; then
        echo "✓ GITHUB_TOKEN configured"
    else
        echo "⚠ GITHUB_TOKEN not configured"
    fi
fi

# Step 5: Load environment (for current shell session)
echo ""
echo "[5/5] Environment setup..."
if [ -f ".env" ]; then
    echo "✓ .env file ready (reload shell or source .env to load variables)"
fi

# Summary
echo ""
echo "============================================================"
echo "✅ MCP Integration Setup Complete!"
echo "============================================================"

echo ""
echo "Next Steps:"
echo "  1. Edit .env and add your API keys"
echo "  2. Source environment: source .env"
echo "  3. Restart VS Code to activate MCP servers"
echo "  4. Run: Ctrl+Shift+P → Tasks: Run Task → MCP: Start All Servers"

echo ""
echo "Useful Commands:"
echo "  • Test MCP servers: npm list -g | grep mcp"
echo "  • View guide: .vscode/MCP_SETUP_GUIDE.md"

echo ""
echo "🚀 Ready to automate!"
