import pytest
from app.services.tools.sandbox import (
    CodeASTAnalyzer,
    IsolatedPythonSandbox,
    SSRFValidator,
    isolated_sandbox,
    ssrf_validator,
)


@pytest.mark.asyncio
async def test_ast_safe_code():
    safe_code = """
import math

def calculate_fibonacci(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a

result = calculate_fibonacci(10)
print(f"Result: {result}")
"""
    report = CodeASTAnalyzer.analyze(safe_code)
    assert report.is_safe is True
    assert report.risk_level == "low"
    assert len(report.forbidden_modules) == 0


@pytest.mark.asyncio
async def test_ast_forbidden_os_subprocess():
    unsafe_code = """
import os
import subprocess

os.system("dir")
subprocess.run(["echo", "exploit"])
"""
    report = CodeASTAnalyzer.analyze(unsafe_code)
    assert report.is_safe is False
    assert report.risk_level == "critical"
    assert "os" in report.forbidden_modules
    assert "subprocess" in report.forbidden_modules


@pytest.mark.asyncio
async def test_ast_forbidden_eval_exec():
    unsafe_code = """
payload = "__import__('os').system('whoami')"
eval(payload)
"""
    report = CodeASTAnalyzer.analyze(unsafe_code)
    assert report.is_safe is False
    assert "eval" in report.forbidden_calls or "__import__" in report.forbidden_calls


@pytest.mark.asyncio
async def test_sandbox_safe_execution():
    code = "print(sum([x * 2 for x in range(10)]))"
    res = isolated_sandbox.run_code(code, timeout_seconds=5.0)
    assert res.success is True
    assert res.return_code == 0
    assert "90" in res.stdout.strip()
    assert res.execution_time_ms > 0


@pytest.mark.asyncio
async def test_sandbox_blocks_unsafe_code():
    code = "import os; print(os.name)"
    res = isolated_sandbox.run_code(code, timeout_seconds=5.0)
    assert res.success is False
    assert "Security Policy Violation" in res.error


@pytest.mark.asyncio
async def test_sandbox_timeout_handling():
    infinite_loop = "while True:\n    pass"
    res = isolated_sandbox.run_code(infinite_loop, timeout_seconds=1.0)
    assert res.success is False
    assert "Timeout" in (res.error or "") or res.return_code == -2


@pytest.mark.asyncio
async def test_ssrf_validator_blocks_private_ips():
    bad_urls = [
        "http://127.0.0.1:8000/admin",
        "http://localhost:3000/api",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.15/secrets",
        "http://192.168.1.1/router",
        "http://172.16.5.10/database",
        "ftp://example.com/file.txt",
        "file:///etc/passwd"
    ]
    for url in bad_urls:
        is_safe, reason = SSRFValidator.validate_url(url)
        assert is_safe is False, f"Expected {url} to be blocked by SSRFValidator, but was allowed. Reason: {reason}"


@pytest.mark.asyncio
async def test_ssrf_validator_allows_valid_public_domains():
    is_safe, reason = SSRFValidator.validate_url("https://en.wikipedia.org/wiki/Artificial_intelligence")
    assert is_safe is True
    assert reason == ""
