import json
import sys
import time

try:
    import requests
except Exception as e:
    print("requests not installed:", e)
    sys.exit(2)

URL = "http://127.0.0.1:8000/mcp"

headers = {
    "Content-Type": "application/json",
    # FastMCP Streamable HTTP expects clients to accept both JSON and SSE
    "Accept": "application/json, text/event-stream",
    # Optional MCP header; harmless if ignored
    "mcp-protocol-version": "2025-06-18",
}

def post(payload):
    try:
        r = requests.post(URL, headers=headers, data=json.dumps(payload), timeout=5)
        return r.status_code, r.text
    except Exception as e:
        return None, f"ERROR: {e}"

if __name__ == "__main__":
    # 1) Ping-like: tools/list
    list_payload = {"jsonrpc": "2.0", "id": "1", "method": "tools/list", "params": {}}

    print("POST tools/list →", URL)
    status, text = post(list_payload)
    print("Status:", status)
    print("Body:", text[:1000])

    # 2) If a tool exists, try a no-op call (will likely error if names differ, but useful for smoke)
    # This is optional and only runs if tools/list succeeded.
    if status == 200:
        try:
            data = json.loads(text)
            tools = data.get("result", {}).get("tools", []) if isinstance(data, dict) else []
            if tools:
                tool_name = tools[0].get("name")
                call_payload = {
                    "jsonrpc": "2.0",
                    "id": "2",
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": {}}
                }
                print(f"\nPOST tools/call({tool_name}) →", URL)
                status2, text2 = post(call_payload)
                print("Status:", status2)
                print("Body:", text2[:1000])
        except Exception as e:
            print("Note: Could not parse tools list:", e)
