"""
Week 1, Day 2: Seccomp Profile Tests
Tests for Docker sandbox syscall filtering and security
"""

import pytest
import asyncio
from pathlib import Path
import sys

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.sandbox.docker_sandbox import DockerSandbox


class TestSeccompProfile:
    """Test suite for seccomp syscall filtering"""
    
    @pytest.fixture
    async def sandbox(self):
        """Create sandbox instance"""
        sandbox = DockerSandbox(
            image="python:3.11-slim",
            timeout=10,
            network_disabled=True
        )
        yield sandbox
        sandbox.cleanup()
    
    @pytest.mark.asyncio
    async def test_normal_code_execution(self, sandbox):
        """Test that normal Python code works with seccomp"""
        code = """
print("Hello from secure sandbox!")
import sys
print(f"Python: {sys.version}")
x = [i**2 for i in range(10)]
print(f"Squares: {x}")
"""
        result = await sandbox.execute_code(code, language='python')
        
        assert result['success'], f"Normal code should work: {result['error']}"
        assert "Hello from secure sandbox!" in result['output']
        assert "Squares:" in result['output']
    
    @pytest.mark.asyncio
    async def test_blocked_reboot_syscall(self, sandbox):
        """Test that reboot syscall is blocked"""
        code = """
import os
import ctypes

# Try to call reboot (should be blocked by seccomp)
try:
    libc = ctypes.CDLL('libc.so.6')
    result = libc.reboot(0x1234567)  # Invalid magic, but should be blocked before
    print(f"SECURITY BREACH: reboot returned {result}")
except Exception as e:
    print(f"Blocked (expected): {type(e).__name__}: {e}")
"""
        result = await sandbox.execute_code(code, language='python')
        
        # Should either fail or show "Blocked"
        assert "SECURITY BREACH" not in result['output'], "Reboot syscall should be blocked!"
        assert result['success'] or "Blocked" in result['output']
    
    @pytest.mark.asyncio
    async def test_blocked_kernel_module_load(self, sandbox):
        """Test that kernel module loading is blocked"""
        code = """
import subprocess

# Try to load kernel module (should be blocked)
try:
    result = subprocess.run(['insmod', '/nonexistent.ko'], capture_output=True, timeout=2)
    if result.returncode == 0:
        print("SECURITY BREACH: insmod succeeded!")
    else:
        print(f"Blocked (expected): insmod returned {result.returncode}")
except Exception as e:
    print(f"Blocked (expected): {type(e).__name__}")
"""
        result = await sandbox.execute_code(code, language='python')
        
        assert "SECURITY BREACH" not in result['output'], "Kernel module loading should be blocked!"
    
    @pytest.mark.asyncio
    async def test_blocked_mount_syscall(self, sandbox):
        """Test that mount syscall is blocked"""
        code = """
import ctypes

# Try to mount filesystem (should be blocked)
try:
    libc = ctypes.CDLL('libc.so.6')
    result = libc.mount(b'/dev/null', b'/mnt', b'ext4', 0, None)
    print(f"SECURITY BREACH: mount returned {result}")
except Exception as e:
    print(f"Blocked (expected): {type(e).__name__}: {e}")
"""
        result = await sandbox.execute_code(code, language='python')
        
        assert "SECURITY BREACH" not in result['output'], "Mount syscall should be blocked!"
    
    @pytest.mark.asyncio
    async def test_file_operations_allowed(self, sandbox):
        """Test that normal file operations work"""
        code = """
import tempfile
import os

# Create temporary file (should work)
with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
    f.write("Test data")
    temp_path = f.name

# Read it back
with open(temp_path, 'r') as f:
    data = f.read()
    print(f"Read: {data}")

# Clean up
os.unlink(temp_path)
print("File operations: OK")
"""
        result = await sandbox.execute_code(code, language='python')
        
        assert result['success'], f"File operations should work: {result['error']}"
        assert "Read: Test data" in result['output']
        assert "File operations: OK" in result['output']
    
    @pytest.mark.asyncio
    async def test_network_operations_blocked(self, sandbox):
        """Test that network operations are blocked (network_disabled=True)"""
        code = """
import socket

# Try to create socket (might work)
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    # Try to connect (should fail - network disabled)
    sock.settimeout(2)
    sock.connect(('google.com', 80))
    print("SECURITY BREACH: Network connection succeeded!")
except socket.error as e:
    print(f"Blocked (expected): {type(e).__name__}: {e}")
except Exception as e:
    print(f"Blocked (expected): {type(e).__name__}")
"""
        result = await sandbox.execute_code(code, language='python')
        
        assert "SECURITY BREACH" not in result['output'], "Network should be blocked!"
        assert "Blocked" in result['output']
    
    @pytest.mark.asyncio
    async def test_process_creation_limited(self, sandbox):
        """Test that process creation is limited by pids_limit"""
        code = """
import subprocess
import sys

# Try to create many processes (should hit pids_limit)
processes = []
max_processes = 150  # Sandbox has pids_limit=100

try:
    for i in range(max_processes):
        p = subprocess.Popen(['sleep', '10'])
        processes.append(p)
    
    print(f"SECURITY BREACH: Created {len(processes)} processes!")
except Exception as e:
    print(f"Limited (expected): Created {len(processes)} processes before hitting limit")
    print(f"Error: {type(e).__name__}: {e}")
finally:
    # Cleanup
    for p in processes:
        p.terminate()
"""
        result = await sandbox.execute_code(code, language='python')
        
        # Should hit process limit
        assert "Limited" in result['output'] or not result['success']
    
    @pytest.mark.asyncio
    async def test_memory_limit_enforced(self, sandbox):
        """Test that memory limit is enforced"""
        code = """
import sys

# Try to allocate more memory than limit (512MB)
try:
    # Allocate 1GB (should fail)
    big_list = [0] * (1024 * 1024 * 1024 // 8)  # 1GB of integers
    print(f"SECURITY BREACH: Allocated {sys.getsizeof(big_list) / 1024**3:.2f} GB")
except MemoryError:
    print("Limited (expected): MemoryError caught")
except Exception as e:
    print(f"Limited (expected): {type(e).__name__}")
"""
        result = await sandbox.execute_code(code, language='python')
        
        assert "SECURITY BREACH" not in result['output'], "Memory limit should be enforced!"
    
    @pytest.mark.asyncio
    async def test_cpu_limit_enforced(self, sandbox):
        """Test that CPU limit is enforced (performance degradation expected)"""
        code = """
import time

# CPU-intensive task
start = time.time()
total = 0
for i in range(10_000_000):
    total += i ** 2

elapsed = time.time() - start
print(f"Computed {total} in {elapsed:.2f}s (CPU limited to 1.0 cores)")
"""
        result = await sandbox.execute_code(code, language='python')
        
        assert result['success'], f"CPU task should complete: {result['error']}"
        # With CPU limit, should take noticeable time
        assert result['duration'] > 0.5, "CPU limit should slow down execution"
    
    @pytest.mark.asyncio
    async def test_timeout_enforced(self, sandbox):
        """Test that execution timeout is enforced"""
        code = """
import time

# Sleep longer than timeout (10s)
print("Sleeping...")
time.sleep(15)
print("SECURITY BREACH: Timeout not enforced!")
"""
        result = await sandbox.execute_code(code, language='python')
        
        assert result['timeout_exceeded'], "Timeout should be enforced!"
        assert not result['success']
        assert "timeout" in result['error'].lower()


@pytest.mark.asyncio
async def test_seccomp_profile_exists():
    """Test that seccomp profiles exist"""
    sandbox_dir = Path(__file__).parent.parent / 'backend' / 'sandbox'
    
    default_profile = sandbox_dir / 'seccomp-profile.json'
    strict_profile = sandbox_dir / 'seccomp-profile-strict.json'
    
    assert default_profile.exists(), "Default seccomp profile missing!"
    assert strict_profile.exists(), "Strict seccomp profile missing!"
    
    # Verify JSON is valid
    import json
    with open(default_profile) as f:
        default_data = json.load(f)
    
    with open(strict_profile) as f:
        strict_data = json.load(f)
    
    # Check structure
    assert 'defaultAction' in default_data
    assert 'syscalls' in default_data
    assert 'defaultAction' in strict_data
    assert 'syscalls' in strict_data
    
    print(f"✅ Default profile: {len(default_data['syscalls'])} syscall groups")
    print(f"✅ Strict profile: {len(strict_data['syscalls'])} syscall groups")


if __name__ == "__main__":
    print("=" * 80)
    print("WEEK 1, DAY 2: Seccomp Profile Security Tests")
    print("=" * 80)
    
    # Run tests
    pytest.main([__file__, "-v", "--tb=short", "--asyncio-mode=auto"])
