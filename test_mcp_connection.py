#!/usr/bin/env python3
"""
🔍 MCP Server Connection Test
Проверяет, что MCP сервер запущен и отвечает на запросы
"""

import sys
import os
import json
import subprocess
from pathlib import Path

def test_mcp_server():
    """Test MCP server через stdio"""
    print("=" * 80)
    print("🔍 ТЕСТ ПОДКЛЮЧЕНИЯ К MCP СЕРВЕРУ")
    print("=" * 80)
    
    # Path to server
    venv_python = Path(__file__).parent / ".venv" / "Scripts" / "python.exe"
    server_py = Path(__file__).parent / "mcp-server" / "server.py"
    
    print(f"\n📂 Python: {venv_python}")
    print(f"📂 Server: {server_py}")
    
    if not venv_python.exists():
        print(f"❌ Python не найден: {venv_python}")
        return False
    
    if not server_py.exists():
        print(f"❌ Server не найден: {server_py}")
        return False
    
    print("\n✅ Файлы найдены")
    
    # Test 1: Initialize request
    print("\n" + "=" * 80)
    print("📤 TEST 1: Initialize Request")
    print("=" * 80)
    
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {"listChanged": True},
                "sampling": {}
            },
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        }
    }
    
    try:
        # Start server process
        print("🚀 Запускаем MCP сервер...")
        
        proc = subprocess.Popen(
            [str(venv_python), str(server_py)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "MCP_STDIO_MODE": "1"}
        )
        
        # Send initialize
        request_str = json.dumps(init_request) + "\n"
        print(f"📨 Отправляем: initialize request")
        
        proc.stdin.write(request_str)
        proc.stdin.flush()
        
        # Read response (with timeout)
        import select
        import time
        
        print("⏳ Ожидаем ответа (5 секунд)...")
        
        start_time = time.time()
        response_line = None
        
        while time.time() - start_time < 5:
            if proc.poll() is not None:
                print(f"❌ Процесс завершился с кодом: {proc.returncode}")
                stderr = proc.stderr.read()
                if stderr:
                    print(f"STDERR: {stderr}")
                return False
            
            # Try to read stdout
            try:
                # Use readline with timeout
                proc.stdout.flush()
                line = proc.stdout.readline()
                
                if line:
                    response_line = line.strip()
                    break
                    
            except Exception as e:
                print(f"⚠️  Read error: {e}")
            
            time.sleep(0.1)
        
        # Terminate process
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
        
        if not response_line:
            print("❌ Нет ответа от сервера")
            return False
        
        print(f"📥 Получен ответ ({len(response_line)} символов)")
        
        # Parse response
        try:
            response = json.loads(response_line)
            print("✅ JSON валиден")
            
            # Check response structure
            if "result" in response:
                result = response["result"]
                print("\n📊 Server Information:")
                print(f"   Protocol: {result.get('protocolVersion', 'N/A')}")
                
                server_info = result.get('serverInfo', {})
                print(f"   Name: {server_info.get('name', 'N/A')}")
                print(f"   Version: {server_info.get('version', 'N/A')}")
                
                capabilities = result.get('capabilities', {})
                print(f"\n🎯 Capabilities:")
                print(f"   Tools: {capabilities.get('tools', False)}")
                print(f"   Resources: {capabilities.get('resources', False)}")
                print(f"   Prompts: {capabilities.get('prompts', False)}")
                
                return True
            else:
                print(f"⚠️  Unexpected response: {response}")
                return False
                
        except json.JSONDecodeError as e:
            print(f"❌ Невалидный JSON: {e}")
            print(f"Response: {response_line[:200]}...")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_logs():
    """Check recent logs"""
    print("\n" + "=" * 80)
    print("📋 ПОСЛЕДНИЕ ЛОГИ")
    print("=" * 80)
    
    log_file = Path(__file__).parent / "logs" / "mcp-server-startup.log"
    
    if not log_file.exists():
        print("⚠️  Лог файл не найден")
        return
    
    # Read last 10 lines
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            recent_lines = lines[-10:] if len(lines) > 10 else lines
            
            for line in recent_lines:
                print(line.rstrip())
                
    except Exception as e:
        print(f"❌ Ошибка чтения лога: {e}")

def main():
    print("\n🚀 MCP Server Connection Test\n")
    
    # Check logs first
    check_logs()
    
    # Test connection
    success = test_mcp_server()
    
    print("\n" + "=" * 80)
    print("📊 ИТОГ")
    print("=" * 80)
    
    if success:
        print("✅ MCP Сервер работает корректно!")
        print("\n🎯 Следующие шаги:")
        print("   1. Откройте MCP_TEST.md")
        print("   2. Попросите Copilot выполнить тесты")
        print("   3. Проверьте результаты")
        return 0
    else:
        print("❌ Проблемы с подключением к MCP серверу")
        print("\n🔧 Возможные решения:")
        print("   1. Перезапустите VS Code")
        print("   2. Ctrl+Shift+P > 'MCP: Restart Server'")
        print("   3. Проверьте .vscode/mcp.json")
        return 1

if __name__ == "__main__":
    sys.exit(main())
