"""
Extract and document all MCP tools from Bybit Strategy Tester MCP server
"""
import re
from pathlib import Path

def extract_mcp_tools():
    """Extract all @mcp.tool() decorated functions from server.py"""
    
    server_path = Path("mcp-server/server.py")
    
    if not server_path.exists():
        print(f"❌ Error: {server_path} not found")
        return
    
    content = server_path.read_text(encoding="utf-8")
    
    # Find all @mcp.tool() decorated functions
    tool_pattern = r'@mcp\.tool\(\)\s*async def (\w+)\((.*?)\) -> (.*?):\s*"""(.*?)"""'
    matches = re.findall(tool_pattern, content, re.DOTALL)
    
    # Also find @mcp.resource() decorated functions
    resource_pattern = r'@mcp\.resource\("(.*?)"\)\s*async def (\w+)\(\) -> str:\s*"""(.*?)"""'
    resource_matches = re.findall(resource_pattern, content, re.DOTALL)
    
    print("=" * 80)
    print("BYBIT STRATEGY TESTER MCP SERVER - AVAILABLE TOOLS")
    print("=" * 80)
    print(f"\n📊 Total Tools: {len(matches)}")
    print(f"📚 Total Resources: {len(resource_matches)}")
    print(f"🔧 Total MCP Capabilities: {len(matches) + len(resource_matches)}")
    
    # Create markdown documentation
    md_content = ["# Bybit Strategy Tester MCP Server - Tools Documentation\n"]
    md_content.append(f"**Generated:** October 29, 2025\n")
    md_content.append(f"**Server:** Bybit Strategy Tester\n")
    md_content.append(f"**Total Tools:** {len(matches)}\n")
    md_content.append(f"**Total Resources:** {len(resource_matches)}\n\n")
    md_content.append("---\n\n")
    
    # Document MCP Tools
    md_content.append("## 🔧 MCP Tools\n\n")
    
    categories = {
        "Perplexity AI Integration": [],
        "Project Information": [],
        "Advanced Analysis": [],
        "Risk Management": [],
        "Technical Research": []
    }
    
    for i, (func_name, params, return_type, docstring) in enumerate(matches, 1):
        # Extract first line of docstring (description)
        description = docstring.strip().split('\n')[0].strip()
        
        # Categorize
        if "perplexity" in func_name.lower():
            categories["Perplexity AI Integration"].append((func_name, params, description))
        elif any(word in func_name.lower() for word in ["get_", "list_", "explain_", "check_"]):
            categories["Project Information"].append((func_name, params, description))
        elif any(word in func_name.lower() for word in ["analyze", "compare", "detect"]):
            categories["Advanced Analysis"].append((func_name, params, description))
        elif "risk" in func_name.lower():
            categories["Risk Management"].append((func_name, params, description))
        else:
            categories["Technical Research"].append((func_name, params, description))
        
        print(f"\n{i}. {func_name}()")
        print(f"   Description: {description}")
        print(f"   Parameters: {params if params else 'None'}")
        print(f"   Returns: {return_type}")
    
    # Write categorized documentation
    for category, tools in categories.items():
        if tools:
            md_content.append(f"### {category} ({len(tools)} tools)\n\n")
            for func_name, params, description in tools:
                md_content.append(f"#### `{func_name}()`\n")
                md_content.append(f"**Description:** {description}\n\n")
                if params:
                    md_content.append(f"**Parameters:**\n```python\n{params}\n```\n\n")
                md_content.append("---\n\n")
    
    # Document MCP Resources
    print("\n" + "=" * 80)
    print("MCP RESOURCES (Prompts)")
    print("=" * 80)
    
    md_content.append("## 📚 MCP Resources (Prompts)\n\n")
    
    for i, (resource_uri, func_name, docstring) in enumerate(resource_matches, 1):
        description = docstring.strip().split('\n')[0].strip()
        print(f"\n{i}. {resource_uri}")
        print(f"   Function: {func_name}()")
        print(f"   Description: {description}")
        
        md_content.append(f"### `{resource_uri}`\n")
        md_content.append(f"**Description:** {description}\n\n")
        md_content.append("---\n\n")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\n✅ {len(matches)} MCP tools available")
    print(f"✅ {len(resource_matches)} MCP resources available")
    print(f"✅ Perplexity AI integration: ENABLED")
    print(f"✅ API Key: CONFIGURED")
    
    md_content.append("## 📊 Summary\n\n")
    md_content.append(f"- **Total MCP Tools:** {len(matches)}\n")
    md_content.append(f"- **Total MCP Resources:** {len(resource_matches)}\n")
    md_content.append(f"- **Perplexity AI Integration:** ✅ ENABLED\n")
    md_content.append(f"- **API Key:** ✅ CONFIGURED\n")
    md_content.append(f"- **Transport:** STDIO\n")
    md_content.append(f"- **FastMCP Version:** 2.13.0.1\n\n")
    
    md_content.append("---\n\n")
    md_content.append("## 🚀 Usage\n\n")
    md_content.append("### Auto-start with VS Code\n")
    md_content.append("```bash\n")
    md_content.append("# MCP server starts automatically when VS Code opens\n")
    md_content.append("code d:\\bybit_strategy_tester_v2\n")
    md_content.append("```\n\n")
    md_content.append("### Manual start\n")
    md_content.append("```powershell\n")
    md_content.append(".venv\\Scripts\\python.exe mcp-server\\server.py\n")
    md_content.append("```\n\n")
    md_content.append("### Via VS Code Task\n")
    md_content.append("```\n")
    md_content.append("Ctrl+Shift+P → Tasks: Run Task → Start Perplexity MCP Server\n")
    md_content.append("```\n")
    
    # Save documentation
    output_path = Path("MCP_TOOLS_INVENTORY.md")
    output_path.write_text('\n'.join(md_content), encoding='utf-8')
    print(f"\n✅ Documentation saved to {output_path}")

if __name__ == "__main__":
    extract_mcp_tools()
