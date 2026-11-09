import ast
import ipaddress
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field


class SSRFSecurityException(Exception):
    """Raised when an outbound URL violates SSRF security boundaries."""
    pass


class CodeSafetyReport(BaseModel):
    is_safe: bool = True
    risk_level: str = "low"  # low, medium, high, critical
    forbidden_modules: List[str] = Field(default_factory=list)
    forbidden_calls: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class SandboxExecutionResult(BaseModel):
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0
    execution_time_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None
    output_files: List[str] = Field(default_factory=list)


class CodeASTAnalyzer:
    """Static AST analyzer for Python code to detect unsafe execution patterns."""

    FORBIDDEN_MODULES: Set[str] = {
        "os", "posix", "nt", "sys", "pathlib", "io", "subprocess", "socket",
        "socketserver", "ctypes", "pty", "multiprocessing", "threading",
        "signal", "fcntl", "winreg", "shutil", "tempfile_unrestricted",
        "importlib", "pickle", "urllib", "http", "requests", "httpx"
    }

    FORBIDDEN_CALLS: Set[str] = {
        "open", "eval", "exec", "__import__", "compile", "breakpoint",
        "globals", "locals", "vars", "dir", "super", "getattr", "setattr", "delattr"
    }

    FORBIDDEN_ATTRIBUTES: Set[str] = {
        "__subclasses__", "__globals__", "__code__", "__closure__",
        "__bases__", "__class__", "__builtins__"
    }

    @classmethod
    def analyze(cls, code: str) -> CodeSafetyReport:
        report = CodeSafetyReport()
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            report.is_safe = False
            report.risk_level = "high"
            report.warnings.append(f"Syntax error in code: {e}")
            return report

        for node in ast.walk(tree):
            # 1. Imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_pkg = alias.name.split(".")[0]
                    if root_pkg in cls.FORBIDDEN_MODULES:
                        report.forbidden_modules.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_pkg = node.module.split(".")[0]
                    if root_pkg in cls.FORBIDDEN_MODULES:
                        report.forbidden_modules.append(node.module)

            # 2. Function calls
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in cls.FORBIDDEN_CALLS:
                        report.forbidden_calls.append(node.func.id)

            # 3. Attribute access
            elif isinstance(node, ast.Attribute):
                if node.attr in cls.FORBIDDEN_ATTRIBUTES:
                    report.forbidden_calls.append(node.attr)

        if report.forbidden_modules or report.forbidden_calls:
            report.is_safe = False
            report.risk_level = "critical"
            if report.forbidden_modules:
                report.warnings.append(f"Forbidden modules detected: {', '.join(set(report.forbidden_modules))}")
            if report.forbidden_calls:
                report.warnings.append(f"Forbidden calls/attributes detected: {', '.join(set(report.forbidden_calls))}")

        return report


class SSRFValidator:
    """Strict SSRF validator guarding all outbound HTTP requests."""

    PRIVATE_NETWORKS = [
        ipaddress.ip_network("127.0.0.0/8"),      # Loopback
        ipaddress.ip_network("10.0.0.0/8"),       # RFC 1918 Private
        ipaddress.ip_network("172.16.0.0/12"),    # RFC 1918 Private
        ipaddress.ip_network("192.168.0.0/16"),   # RFC 1918 Private
        ipaddress.ip_network("169.254.0.0/16"),   # Link-Local (AWS/GCP/Azure metadata)
        ipaddress.ip_network("0.0.0.0/8"),        # Current network
        ipaddress.ip_network("100.64.0.0/10"),    # Carrier-grade NAT
        ipaddress.ip_network("::1/128"),          # IPv6 Loopback
        ipaddress.ip_network("fc00::/7"),         # IPv6 Unique Local
        ipaddress.ip_network("fe80::/10"),        # IPv6 Link-Local
    ]

    DISALLOWED_HOSTNAMES = {
        "localhost", "127.0.0.1", "0.0.0.0", "metadata.google.internal",
        "instance-data", "169.254.169.254"
    }

    @classmethod
    def validate_url(cls, url: str) -> Tuple[bool, str]:
        """Validates that a URL is safe from SSRF. Returns (is_safe, error_reason)."""
        try:
            parsed = urllib.parse.urlparse(url)
        except Exception as e:
            return False, f"Malformed URL: {e}"

        if parsed.scheme.lower() not in ("http", "https"):
            return False, f"Scheme '{parsed.scheme}' is not allowed. Only HTTP and HTTPS are permitted."

        if parsed.username or parsed.password:
            return False, "Embedded URL credentials are prohibited to prevent SSRF bypasses."

        hostname = parsed.hostname
        if not hostname:
            return False, "URL has no valid hostname."

        lower_host = hostname.lower().rstrip(".")
        if lower_host in cls.DISALLOWED_HOSTNAMES or lower_host.endswith((".local", ".internal", ".localhost")):
            return False, f"Access to internal hostname '{hostname}' is blocked."

        # Detect obfuscated integer / hex / octal IP representations (e.g. http://2130706433 or 0x7f000001)
        try:
            if lower_host.startswith("0x") or lower_host.isdigit():
                int_ip = int(lower_host, 16 if lower_host.startswith("0x") else 10)
                ip_obj = ipaddress.ip_address(int_ip)
                for net in cls.PRIVATE_NETWORKS:
                    if ip_obj in net or getattr(ip_obj, "ipv4_mapped", None) in net:
                        return False, f"Obfuscated private IP '{hostname}' is blocked."
        except ValueError:
            pass

        # Check if hostname directly is an IP address (including IPv4-mapped IPv6)
        try:
            ip_obj = ipaddress.ip_address(hostname)
            mapped = getattr(ip_obj, "ipv4_mapped", None)
            for net in cls.PRIVATE_NETWORKS:
                if ip_obj in net or (mapped is not None and mapped in net):
                    return False, f"Direct access to private IP '{hostname}' is blocked."
        except ValueError:
            # Hostname is a domain, resolve with strict timeout
            orig_timeout = socket.getdefaulttimeout()
            try:
                socket.setdefaulttimeout(1.5)
                addr_info = socket.getaddrinfo(hostname, None)
                for item in addr_info:
                    resolved_ip_str = item[4][0]
                    resolved_ip = ipaddress.ip_address(resolved_ip_str)
                    for net in cls.PRIVATE_NETWORKS:
                        if resolved_ip in net:
                            return False, f"Domain '{hostname}' resolves to private/internal IP {resolved_ip_str}."
            except socket.gaierror:
                # If domain cannot be resolved (offline/sandbox), allow public domain names but block internal patterns
                if any(bad in hostname.lower() for bad in ["local", "corp", "internal", "intranet"]):
                    return False, f"Unresolvable internal domain pattern '{hostname}' is blocked."
            except Exception:
                pass
            finally:
                socket.setdefaulttimeout(orig_timeout)

        return True, ""


class IsolatedPythonSandbox:
    """Executes untrusted Python code in an isolated subprocess with strict safeguards."""

    def __init__(self, sandbox_base_dir: Optional[str] = None):
        self.sandbox_base_dir = sandbox_base_dir or os.path.join(tempfile.gettempdir(), "nexora_sandbox")
        os.makedirs(self.sandbox_base_dir, exist_ok=True)

    def run_code(
        self,
        code: str,
        timeout_seconds: float = 10.0,
        stdin_data: str = ""
    ) -> SandboxExecutionResult:
        """Analyze code for safety and run in isolated subprocess with clean environment."""
        start_time = time.time()

        # 1. Static AST Security Analysis
        safety = CodeASTAnalyzer.analyze(code)
        if not safety.is_safe:
            return SandboxExecutionResult(
                stdout="",
                stderr="\n".join(safety.warnings),
                return_code=-1,
                execution_time_ms=(time.time() - start_time) * 1000,
                success=False,
                error="Security Policy Violation: Untrusted or forbidden code constructs detected."
            )

        # 2. Setup isolated execution workspace
        work_dir = tempfile.mkdtemp(dir=self.sandbox_base_dir)
        script_path = os.path.join(work_dir, "script.py")

        try:
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)

            # 3. Create stripped environment (No API keys or system secrets!)
            safe_env: Dict[str, str] = {
                "PYTHONPATH": os.path.dirname(script_path),
                "PATH": os.environ.get("PATH", ""),
                "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows"),
                "PYTHONIOENCODING": "utf-8",
                "PYTHONDONTWRITEBYTECODE": "1"
            }

            # 4. Execute restricted subprocess
            proc = subprocess.run(
                [sys.executable, "-I", "script.py"],  # -I flag isolates from user site-packages/environment
                cwd=work_dir,
                input=stdin_data,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                env=safe_env
            )

            execution_time = (time.time() - start_time) * 1000

            # Collect any output files generated
            output_files = [
                f for f in os.listdir(work_dir)
                if f != "script.py" and os.path.isfile(os.path.join(work_dir, f))
            ]

            return SandboxExecutionResult(
                stdout=proc.stdout,
                stderr=proc.stderr,
                return_code=proc.returncode,
                execution_time_ms=execution_time,
                success=(proc.returncode == 0),
                error=None if proc.returncode == 0 else proc.stderr,
                output_files=output_files
            )

        except subprocess.TimeoutExpired:
            return SandboxExecutionResult(
                stdout="",
                stderr=f"Execution timed out after {timeout_seconds} seconds.",
                return_code=-2,
                execution_time_ms=timeout_seconds * 1000,
                success=False,
                error=f"Timeout expired ({timeout_seconds}s)"
            )
        except Exception as e:
            return SandboxExecutionResult(
                stdout="",
                stderr=str(e),
                return_code=-3,
                execution_time_ms=(time.time() - start_time) * 1000,
                success=False,
                error=str(e)
            )
        finally:
            # Clean up script and temporary workspace
            try:
                import shutil
                shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                pass


# Global singleton instance
isolated_sandbox = IsolatedPythonSandbox()
ssrf_validator = SSRFValidator()
