"""Run the local BTC evidence model in a zero-capability Windows AppContainer."""
from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid
import zipfile
from typing import Any, Callable, Mapping


APP_CONTAINER_NAME = "MarketOS.Acceleratorer.BTC.Assessor"
APP_CONTAINER_DISPLAY_NAME = "Market OS BTC Assessor"
APP_CONTAINER_DESCRIPTION = "Local CPU-only evidence assessment with no network capabilities"
MAX_CAPTURE_BYTES = 1024 * 1024
MAX_RUNTIME_INPUT_BYTES = 128 * 1024
MAX_CONTEXT_TOKENS = 8192
MAX_OUTPUT_TOKENS = 2048
MAX_STAGED_RUNTIME_BYTES = 3 * 1024**3
MAX_RUNTIME_MEMORY_BYTES = 6 * 1024**3
MAX_RUNTIME_CPU_PERCENT = 25


class AppContainerRuntimeError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        self.code = code
        self.retryable = retryable
        super().__init__(message)


class _SECURITY_CAPABILITIES(ctypes.Structure):
    _fields_ = [
        ("AppContainerSid", ctypes.c_void_p),
        ("Capabilities", ctypes.c_void_p),
        ("CapabilityCount", ctypes.c_uint32),
        ("Reserved", ctypes.c_uint32),
    ]


class _SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("nLength", ctypes.c_uint32),
        ("lpSecurityDescriptor", ctypes.c_void_p),
        ("bInheritHandle", ctypes.c_int),
    ]


class _STARTUPINFO(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_uint32), ("lpReserved", ctypes.c_wchar_p), ("lpDesktop", ctypes.c_wchar_p),
        ("lpTitle", ctypes.c_wchar_p), ("dwX", ctypes.c_uint32), ("dwY", ctypes.c_uint32),
        ("dwXSize", ctypes.c_uint32), ("dwYSize", ctypes.c_uint32), ("dwXCountChars", ctypes.c_uint32),
        ("dwYCountChars", ctypes.c_uint32), ("dwFillAttribute", ctypes.c_uint32),
        ("dwFlags", ctypes.c_uint32), ("wShowWindow", ctypes.c_uint16), ("cbReserved2", ctypes.c_uint16),
        ("lpReserved2", ctypes.POINTER(ctypes.c_ubyte)), ("hStdInput", ctypes.c_void_p),
        ("hStdOutput", ctypes.c_void_p), ("hStdError", ctypes.c_void_p),
    ]


class _STARTUPINFOEX(ctypes.Structure):
    _fields_ = [("StartupInfo", _STARTUPINFO), ("lpAttributeList", ctypes.c_void_p)]


class _PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", ctypes.c_void_p), ("hThread", ctypes.c_void_p),
        ("dwProcessId", ctypes.c_uint32), ("dwThreadId", ctypes.c_uint32),
    ]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _safe_rmtree(path: Path, parent: Path, prefix: str) -> None:
    if not path.exists():
        return
    expected_parent = parent.resolve(strict=False)
    resolved = path.resolve(strict=False)
    if resolved.parent != expected_parent or not resolved.name.startswith(prefix):
        raise AppContainerRuntimeError("runtime_integrity_failed", "refused cleanup outside the managed AppContainer directory")
    shutil.rmtree(resolved)


class WindowsAppContainerCliRuntime:
    """Stage pinned CPU artifacts in AppContainer data and run one bounded CLI process per request."""

    def __init__(
        self,
        installation_root: str | Path,
        server_path: str | Path,
        model_spec: Mapping[str, Any],
        runtime_spec: Mapping[str, Any],
        *,
        lock_sha256: str,
        resource_job_factory: Callable[[Any], Any],
    ) -> None:
        self.installation_root = Path(installation_root).resolve()
        self.engine_source = Path(server_path).resolve().parent
        self.model_spec = dict(model_spec)
        self.runtime_spec = dict(runtime_spec)
        self.lock_sha256 = lock_sha256
        self.resource_job_factory = resource_job_factory
        self.archive_path = self.installation_root / "downloads" / str(runtime_spec.get("archive", ""))
        self.model_source = self.installation_root / "models" / str(model_spec.get("file", ""))
        self.target = str(runtime_spec.get("target") or "windows-x64-cuda-13.5")
        self.runtime_version = f"llama.cpp-{runtime_spec.get('release', 'unknown')}"
        self.cli_path: Path | None = None
        self.model_path: Path | None = None
        self.package_root: Path | None = None
        self.request_root: Path | None = None
        self._app_data: Path | None = None
        self._sid: ctypes.c_void_p | None = None
        self._expected_hashes: dict[str, str] = {}
        self._staged_bytes = 0
        self._ready = False
        self._last_process_limits_enforced = False

    def _require_windows(self) -> None:
        if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
            raise AppContainerRuntimeError("unsupported_runtime_target", "Windows AppContainer inference requires Windows x64")

    def _resolve_profile(self) -> tuple[Path, ctypes.c_void_p]:
        self._require_windows()
        userenv = ctypes.WinDLL("userenv", use_last_error=True)
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        ole32 = ctypes.WinDLL("ole32", use_last_error=True)
        userenv.CreateAppContainerProfile.argtypes = [
            ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_void_p,
            ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p),
        ]
        userenv.CreateAppContainerProfile.restype = ctypes.c_long
        userenv.DeriveAppContainerSidFromAppContainerName.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p)]
        userenv.DeriveAppContainerSidFromAppContainerName.restype = ctypes.c_long
        userenv.GetAppContainerFolderPath.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p)]
        userenv.GetAppContainerFolderPath.restype = ctypes.c_long
        advapi32.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        advapi32.ConvertSidToStringSidW.restype = ctypes.c_int
        advapi32.FreeSid.argtypes = [ctypes.c_void_p]
        advapi32.FreeSid.restype = ctypes.c_void_p
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
        ole32.CoTaskMemFree.restype = None

        sid = ctypes.c_void_p()
        hr = int(userenv.CreateAppContainerProfile(
            APP_CONTAINER_NAME, APP_CONTAINER_DISPLAY_NAME, APP_CONTAINER_DESCRIPTION,
            None, 0, ctypes.byref(sid),
        ))
        if hr & 0xFFFFFFFF == 0x800700B7:  # HRESULT_FROM_WIN32(ERROR_ALREADY_EXISTS)
            hr = int(userenv.DeriveAppContainerSidFromAppContainerName(APP_CONTAINER_NAME, ctypes.byref(sid)))
        if hr != 0 or not sid:
            raise AppContainerRuntimeError("network_isolation_unverified", f"could not resolve the zero-capability AppContainer profile (HRESULT 0x{hr & 0xFFFFFFFF:08x})")

        sid_text_ptr = ctypes.c_void_p()
        data_path_ptr = ctypes.c_void_p()
        try:
            if not advapi32.ConvertSidToStringSidW(sid, ctypes.byref(sid_text_ptr)):
                raise AppContainerRuntimeError("network_isolation_unverified", "could not convert the AppContainer SID")
            sid_text = ctypes.wstring_at(sid_text_ptr)
            hr = int(userenv.GetAppContainerFolderPath(sid_text, ctypes.byref(data_path_ptr)))
            if hr != 0 or not data_path_ptr:
                raise AppContainerRuntimeError("network_isolation_unverified", f"could not resolve AppContainer data storage (HRESULT 0x{hr & 0xFFFFFFFF:08x})")
            app_data = Path(ctypes.wstring_at(data_path_ptr)).resolve()
        except BaseException:
            advapi32.FreeSid(sid)
            raise
        finally:
            if sid_text_ptr:
                kernel32.LocalFree(sid_text_ptr)
            if data_path_ptr:
                ole32.CoTaskMemFree(data_path_ptr)
        self._sid = sid
        self._app_data = app_data
        return app_data, sid

    def _source_expected_hashes(self) -> dict[str, str]:
        archive = self.archive_path
        if not archive.is_file() or archive.stat().st_size != self.runtime_spec.get("size_bytes") or _sha256_file(archive) != self.runtime_spec.get("sha256"):
            raise AppContainerRuntimeError("runtime_integrity_failed", "pinned llama.cpp archive failed its locked size or SHA-256 check")
        model_file = str(self.model_spec.get("file", ""))
        model_size = self.model_spec.get("size_bytes")
        if Path(model_file).name != model_file or not self.model_source.is_file() or self.model_source.stat().st_size != model_size:
            raise AppContainerRuntimeError("runtime_integrity_failed", "pinned model path is invalid or missing")

        expected: dict[str, str] = {}
        staged_bytes = int(model_size)
        try:
            with zipfile.ZipFile(archive) as bundle:
                for entry in bundle.infolist():
                    name = entry.filename
                    filename = Path(name).name
                    if filename != name or filename in {".", ".."}:
                        continue
                    lowered = filename.lower()
                    if filename != "llama-cli.exe" and not (lowered.endswith(".dll") and not any(part in lowered for part in ("cuda", "cublas", "cudart"))):
                        continue
                    staged_bytes += entry.file_size
                    if staged_bytes > MAX_STAGED_RUNTIME_BYTES:
                        raise AppContainerRuntimeError("resource_limit", "pinned AppContainer runtime exceeds the staging byte limit")
                    digest = hashlib.sha256()
                    with bundle.open(entry) as stream:
                        while block := stream.read(1024 * 1024):
                            digest.update(block)
                    value = digest.hexdigest()
                    installed = self.engine_source / filename
                    if not installed.is_file() or _sha256_file(installed) != value:
                        raise AppContainerRuntimeError("runtime_integrity_failed", f"installed llama.cpp file differs from its pinned archive: {filename}")
                    expected[f"engine/{filename}"] = value
        except (OSError, zipfile.BadZipFile) as exc:
            raise AppContainerRuntimeError("runtime_integrity_failed", "pinned llama.cpp archive could not be inspected") from exc
        if "engine/llama-cli.exe" not in expected:
            raise AppContainerRuntimeError("dependency_unavailable", "pinned llama.cpp archive does not include llama-cli.exe")
        expected[f"models/{model_file}"] = str(self.model_spec.get("sha256", ""))
        self._staged_bytes = staged_bytes
        return expected

    def _copy_artifacts(self, stage: Path, expected: Mapping[str, str]) -> None:
        stage_engine = stage / "engine"
        stage_models = stage / "models"
        stage_engine.mkdir(parents=True)
        stage_models.mkdir()
        try:
            with zipfile.ZipFile(self.archive_path) as bundle:
                copied_archive_bytes = 0
                for entry in bundle.infolist():
                    relative = f"engine/{Path(entry.filename).name}"
                    if relative not in expected:
                        continue
                    target = stage / relative
                    digest = hashlib.sha256()
                    with bundle.open(entry) as source, target.open("wb") as output:
                        while block := source.read(1024 * 1024):
                            copied_archive_bytes += len(block)
                            if copied_archive_bytes > self._staged_bytes - self.model_spec["size_bytes"]:
                                raise AppContainerRuntimeError("resource_limit", "runtime archive expanded beyond its locked staging bound")
                            digest.update(block)
                            output.write(block)
                    if digest.hexdigest() != expected[relative]:
                        raise AppContainerRuntimeError("runtime_integrity_failed", "staged llama.cpp file hash mismatch")
        except (OSError, zipfile.BadZipFile) as exc:
            raise AppContainerRuntimeError("runtime_integrity_failed", "pinned llama.cpp runtime could not be staged") from exc

        model_name = str(self.model_spec["file"])
        model_target = stage / "models" / model_name
        digest = hashlib.sha256()
        try:
            with self.model_source.open("rb") as source, model_target.open("wb") as output:
                copied_bytes = 0
                while block := source.read(1024 * 1024):
                    copied_bytes += len(block)
                    if copied_bytes > self.model_spec["size_bytes"]:
                        raise AppContainerRuntimeError("resource_limit", "model source grew beyond its locked staging size")
                    digest.update(block)
                    output.write(block)
                if copied_bytes != self.model_spec["size_bytes"]:
                    raise AppContainerRuntimeError("runtime_integrity_failed", "model source changed size while being staged")
        except OSError as exc:
            raise AppContainerRuntimeError("dependency_unavailable", "pinned model could not be copied into AppContainer data") from exc
        if model_target.stat().st_size != self.model_spec.get("size_bytes") or digest.hexdigest() != self.model_spec.get("sha256"):
            raise AppContainerRuntimeError("runtime_integrity_failed", "staged Qwen model failed its locked size or SHA-256 check")

        manifest = {
            "schema": "market-os.btc-assessor-appcontainer-runtime.v1",
            "profile": APP_CONTAINER_NAME,
            "target": self.target,
            "lock_sha256": self.lock_sha256,
            "llama_archive_sha256": self.runtime_spec["sha256"],
            "model_sha256": self.model_spec["sha256"],
            "files": dict(expected),
        }
        (stage / "runtime-manifest.json").write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")), encoding="utf-8")

    def _verify_package(self, expected: Mapping[str, str]) -> None:
        if self.package_root is None:
            raise AppContainerRuntimeError("dependency_unavailable", "AppContainer runtime package is not prepared")
        manifest_path = self.package_root / "runtime-manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise AppContainerRuntimeError("runtime_integrity_failed", "AppContainer runtime manifest is missing or invalid") from exc
        expected_manifest = {
            "schema": "market-os.btc-assessor-appcontainer-runtime.v1",
            "profile": APP_CONTAINER_NAME,
            "target": self.target,
            "lock_sha256": self.lock_sha256,
            "llama_archive_sha256": self.runtime_spec["sha256"],
            "model_sha256": self.model_spec["sha256"],
            "files": dict(expected),
        }
        if manifest != expected_manifest:
            raise AppContainerRuntimeError("runtime_integrity_failed", "AppContainer runtime manifest does not match the tracked lock")
        actual_files = {
            path.relative_to(self.package_root).as_posix()
            for root in (self.package_root / "engine", self.package_root / "models")
            for path in root.rglob("*")
            if path.is_file()
        }
        if actual_files != set(expected):
            raise AppContainerRuntimeError("runtime_integrity_failed", "AppContainer runtime package contains an unexpected or missing file")
        for relative, digest in expected.items():
            path = (self.package_root / relative).resolve()
            if not path.is_relative_to(self.package_root.resolve()) or not path.is_file() or _sha256_file(path) != digest:
                raise AppContainerRuntimeError("runtime_integrity_failed", "AppContainer runtime file failed its pinned SHA-256 check")
        self.cli_path = self.package_root / "engine" / "llama-cli.exe"
        self.model_path = self.package_root / "models" / str(self.model_spec["file"])
        self.request_root = self.package_root / "requests"
        self.request_root.mkdir(exist_ok=True)
        if self.request_root.resolve().parent != self.package_root.resolve():
            raise AppContainerRuntimeError("runtime_integrity_failed", "AppContainer request storage escaped the runtime package")

    def _prepare_package(self, app_data: Path, expected: Mapping[str, str]) -> None:
        package = app_data / "market-os-btc-runtime-v1"
        if package.exists():
            self.package_root = package.resolve()
            if self.package_root.parent != app_data.resolve():
                raise AppContainerRuntimeError("runtime_integrity_failed", "AppContainer package path escaped its profile data directory")
            self._verify_package(expected)
            return

        stage = app_data / f".market-os-btc-stage-{uuid.uuid4().hex}"
        try:
            self._copy_artifacts(stage, expected)
            try:
                stage.rename(package)
            except OSError:
                if not package.exists():
                    raise
            self.package_root = package.resolve()
            self._verify_package(expected)
        finally:
            if stage.exists():
                _safe_rmtree(stage, app_data, ".market-os-btc-stage-")

    def prepare(self) -> dict[str, Any]:
        if self._ready:
            return self.network_isolation()
        try:
            app_data, _sid = self._resolve_profile()
            app_data.mkdir(parents=True, exist_ok=True)
            expected = self._source_expected_hashes()
            self._expected_hashes = expected
            package = app_data / "market-os-btc-runtime-v1"
            if not package.exists() and shutil.disk_usage(app_data).free < self._staged_bytes + 64 * 1024**2:
                raise AppContainerRuntimeError("resource_limit", "insufficient free space for bounded AppContainer runtime staging")
            self._prepare_package(app_data, expected)
            if self.cli_path is None:
                raise AppContainerRuntimeError("dependency_unavailable", "staged llama-cli is unavailable")
            result = self._run(self.cli_path, ["--version"], timeout_seconds=15)
            if result["exit_code"] != 0 or f"build {str(self.runtime_spec.get('release', '')).lstrip('b')}" not in (result["stdout"] + result["stderr"]).lower():
                raise AppContainerRuntimeError("runtime_integrity_failed", "AppContainer llama-cli version did not match the pinned runtime")
        except BaseException:
            self.stop()
            raise
        self._ready = True
        return self.network_isolation()

    def complete(self, messages: list[dict[str, str]], schema: dict[str, Any], *, timeout_seconds: float) -> tuple[dict[str, Any], int]:
        if not math.isfinite(timeout_seconds) or not 1 <= timeout_seconds <= 300:
            raise ValueError("timeout_seconds must be between 1 and 300")
        if not self._ready:
            self.prepare()
        self._verify_package(self._expected_hashes)
        if self.cli_path is None or self.model_path is None or self.request_root is None:
            raise AppContainerRuntimeError("dependency_unavailable", "AppContainer runtime paths are unavailable")
        if (
            not isinstance(messages, list)
            or len(messages) != 2
            or not isinstance(messages[0], dict)
            or not isinstance(messages[1], dict)
            or messages[0].get("role") != "system"
            or messages[1].get("role") != "user"
            or not isinstance(messages[0].get("content"), str)
            or not isinstance(messages[1].get("content"), str)
            or not isinstance(schema, dict)
        ):
            raise AppContainerRuntimeError("invalid_response", "local completion requires one system and one user message")

        request_id = uuid.uuid4().hex
        system_path = self.request_root / f"request-{request_id}.system.txt"
        user_path = self.request_root / f"request-{request_id}.user.txt"
        try:
            schema_text = json.dumps(schema, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise AppContainerRuntimeError("invalid_response", "local completion schema is not valid JSON") from exc
        system_text = messages[0]["content"] + "\n\nReturn JSON matching this exact schema:\n" + schema_text
        user_text = messages[1]["content"]
        try:
            input_bytes = len(system_text.encode("utf-8")) + len(user_text.encode("utf-8"))
        except UnicodeError as exc:
            raise AppContainerRuntimeError("invalid_response", "local completion prompt is not valid UTF-8") from exc
        if input_bytes > MAX_RUNTIME_INPUT_BYTES:
            raise AppContainerRuntimeError("resource_limit", "local completion prompt exceeded its byte bound")
        try:
            with system_path.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(system_text)
            with user_path.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(user_text)
            args = [
                "--model", str(self.model_path), "--device", "none", "--gpu-layers", "0",
                "--threads", "8", "--threads-batch", "8", "--ctx-size", str(MAX_CONTEXT_TOKENS),
                "--predict", str(MAX_OUTPUT_TOKENS), "--single-turn", "--simple-io", "--no-display-prompt",
                "--color", "off", "--log-disable", "--temp", "0", "--seed", "0",
                "--system-prompt-file", str(system_path), "--file", str(user_path),
            ]
            started = time.monotonic()
            result = self._run(self.cli_path, args, timeout_seconds=timeout_seconds)
            latency_ms = max(0, round((time.monotonic() - started) * 1000))
            if result["exit_code"] != 0:
                raise AppContainerRuntimeError("local_runtime_failed", "pinned AppContainer llama-cli returned a nonzero exit code", retryable=True)
            generated = self._extract_completion(result["stdout"], user_text)
            return {"choices": [{"message": {"content": generated}}]}, latency_ms
        except OSError as exc:
            raise AppContainerRuntimeError("local_runtime_failed", "AppContainer request files could not be read or written", retryable=True) from exc
        finally:
            for path in (system_path, user_path):
                if path.exists():
                    resolved = path.resolve()
                    if resolved.parent != self.request_root.resolve():
                        raise AppContainerRuntimeError("runtime_integrity_failed", "refused request cleanup outside AppContainer request storage")
                    try:
                        path.unlink()
                    except OSError as exc:
                        raise AppContainerRuntimeError("local_runtime_failed", "AppContainer request file could not be removed") from exc

    @staticmethod
    def _extract_completion(stdout: str, user_text: str) -> str:
        output = stdout.replace("\r\n", "\n")
        marker = "> " + user_text
        marker_at = output.rfind(marker)
        if marker_at < 0:
            raise AppContainerRuntimeError("invalid_response", "llama-cli output did not contain its exact prompt marker")
        start = marker_at + len(marker)
        if output[start:start + 1] == "\n":
            start += 1
        end = output.rfind("[ Prompt:")
        if end < start:
            raise AppContainerRuntimeError("invalid_response", "llama-cli output did not contain its completion summary")
        content = output[start:end].strip()
        if not content or content.startswith("Error:"):
            raise AppContainerRuntimeError("invalid_response", "llama-cli did not produce a usable completion")
        return content

    def _resolve_native_apis(self) -> tuple[Any, Any, Any, Any]:
        self._require_windows()
        if self._sid is None:
            raise AppContainerRuntimeError("network_isolation_unverified", "AppContainer profile SID is unavailable")
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel32.InitializeProcThreadAttributeList.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(ctypes.c_size_t)]
        kernel32.InitializeProcThreadAttributeList.restype = ctypes.c_int
        kernel32.UpdateProcThreadAttribute.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)]
        kernel32.UpdateProcThreadAttribute.restype = ctypes.c_int
        kernel32.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
        kernel32.DeleteProcThreadAttributeList.restype = None
        kernel32.CreateProcessW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_void_p, ctypes.POINTER(_PROCESS_INFORMATION)]
        kernel32.CreateProcessW.restype = ctypes.c_int
        kernel32.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
        kernel32.CreateFileW.restype = ctypes.c_void_p
        kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel32.WaitForSingleObject.restype = ctypes.c_uint32
        kernel32.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        kernel32.GetExitCodeProcess.restype = ctypes.c_int
        kernel32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel32.TerminateProcess.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int
        kernel32.CreatePipe.argtypes = [
            ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(_SECURITY_ATTRIBUTES), ctypes.c_uint32,
        ]
        kernel32.CreatePipe.restype = ctypes.c_int
        kernel32.SetHandleInformation.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32]
        kernel32.SetHandleInformation.restype = ctypes.c_int
        kernel32.PeekNamedPipe.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32),
        ]
        kernel32.PeekNamedPipe.restype = ctypes.c_int
        kernel32.ReadFile.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p,
        ]
        kernel32.ReadFile.restype = ctypes.c_int
        advapi32.OpenProcessToken.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)]
        advapi32.OpenProcessToken.restype = ctypes.c_int
        advapi32.GetTokenInformation.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
        advapi32.GetTokenInformation.restype = ctypes.c_int
        return kernel32, advapi32, _SECURITY_CAPABILITIES, _SECURITY_ATTRIBUTES

    @staticmethod
    def _token_value(advapi32: Any, token: ctypes.c_void_p, info_class: int) -> int:
        size = ctypes.c_uint32()
        advapi32.GetTokenInformation(token, info_class, None, 0, ctypes.byref(size))
        if not size.value or size.value > 1024 * 1024:
            raise AppContainerRuntimeError("network_isolation_unverified", "AppContainer token information could not be sized")
        buffer = ctypes.create_string_buffer(size.value)
        if not advapi32.GetTokenInformation(token, info_class, buffer, size.value, ctypes.byref(size)):
            raise AppContainerRuntimeError("network_isolation_unverified", "AppContainer token information could not be read")
        return ctypes.cast(buffer, ctypes.POINTER(ctypes.c_uint32)).contents.value

    def _run(self, executable: Path, args: list[str], *, timeout_seconds: float) -> dict[str, Any]:
        if self.request_root is None or not executable.is_file():
            raise AppContainerRuntimeError("dependency_unavailable", "AppContainer executable or request storage is unavailable")
        if not math.isfinite(timeout_seconds) or not 1 <= timeout_seconds <= 300:
            raise ValueError("timeout_seconds must be between 1 and 300")
        self.request_root.mkdir(parents=True, exist_ok=True)
        kernel32, advapi32, _caps_type, security_attributes_type = self._resolve_native_apis()
        invalid_handle = ctypes.c_void_p(-1).value
        handles: list[ctypes.c_void_p] = []
        process_info = _PROCESS_INFORMATION()
        attr_ptr = ctypes.c_void_p()
        resource_job = None
        process_created = False
        process_finished = False
        outputs = [bytearray(), bytearray()]
        output_eof = [False, False]
        try:
            security_attributes = security_attributes_type(ctypes.sizeof(security_attributes_type), None, True)
            stdout_read = ctypes.c_void_p()
            stdout_write = ctypes.c_void_p()
            if not kernel32.CreatePipe(ctypes.byref(stdout_read), ctypes.byref(stdout_write), ctypes.byref(security_attributes), 0):
                raise AppContainerRuntimeError("local_runtime_failed", "could not create bounded AppContainer output pipe")
            handles.extend((stdout_read, stdout_write))
            if not kernel32.SetHandleInformation(stdout_read, 0x1, 0):
                raise AppContainerRuntimeError("local_runtime_failed", "could not restrict the AppContainer output pipe handle")
            stderr_read = ctypes.c_void_p()
            stderr_write = ctypes.c_void_p()
            if not kernel32.CreatePipe(ctypes.byref(stderr_read), ctypes.byref(stderr_write), ctypes.byref(security_attributes), 0):
                raise AppContainerRuntimeError("local_runtime_failed", "could not create bounded AppContainer error pipe")
            handles.extend((stderr_read, stderr_write))
            if not kernel32.SetHandleInformation(stderr_read, 0x1, 0):
                raise AppContainerRuntimeError("local_runtime_failed", "could not restrict the AppContainer error pipe handle")
            stdin_handle = ctypes.c_void_p(kernel32.CreateFileW("NUL", 0x80000000, 0x3, ctypes.byref(security_attributes), 3, 0x80, None))
            if not stdin_handle.value or stdin_handle.value == invalid_handle:
                raise AppContainerRuntimeError("local_runtime_failed", "could not prepare bounded AppContainer process handles")
            handles.append(stdin_handle)
            child_handles = (stdout_write, stderr_write, stdin_handle)
            for handle in child_handles:
                if not handle.value or handle.value == invalid_handle:
                    raise AppContainerRuntimeError("local_runtime_failed", "could not prepare bounded AppContainer process handles")

            attr_size = ctypes.c_size_t()
            kernel32.InitializeProcThreadAttributeList(None, 2, 0, ctypes.byref(attr_size))
            if not attr_size.value or attr_size.value > 65536:
                raise AppContainerRuntimeError("local_runtime_failed", "could not size the AppContainer process attributes")
            attr_buffer = ctypes.create_string_buffer(attr_size.value)
            attr_ptr = ctypes.cast(attr_buffer, ctypes.c_void_p)
            if not kernel32.InitializeProcThreadAttributeList(attr_ptr, 2, 0, ctypes.byref(attr_size)):
                raise AppContainerRuntimeError("local_runtime_failed", "could not initialize the AppContainer process attributes")
            caps = _SECURITY_CAPABILITIES(self._sid, None, 0, 0)
            if not kernel32.UpdateProcThreadAttribute(attr_ptr, 0, 0x00020009, ctypes.byref(caps), ctypes.sizeof(caps), None, None):
                raise AppContainerRuntimeError("network_isolation_unverified", "could not set zero-capability AppContainer process attributes")
            handle_array = (ctypes.c_void_p * 3)(*(handle.value for handle in child_handles))
            if not kernel32.UpdateProcThreadAttribute(attr_ptr, 0, 0x00020002, ctypes.cast(handle_array, ctypes.c_void_p), ctypes.sizeof(handle_array), None, None):
                raise AppContainerRuntimeError("local_runtime_failed", "could not restrict inherited AppContainer handles")

            startup = _STARTUPINFOEX()
            startup.StartupInfo.cb = ctypes.sizeof(_STARTUPINFOEX)
            startup.StartupInfo.dwFlags = 0x00000100  # STARTF_USESTDHANDLES
            startup.StartupInfo.hStdInput = stdin_handle
            startup.StartupInfo.hStdOutput = stdout_write
            startup.StartupInfo.hStdError = stderr_write
            startup.lpAttributeList = attr_ptr
            environment = {
                "SystemRoot": os.environ.get("SystemRoot", r"C:\Windows"),
                "WINDIR": os.environ.get("SystemRoot", r"C:\Windows"),
                "PATH": os.pathsep.join((str(executable.parent), str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"))),
                "LOCALAPPDATA": str(self._app_data),
                "TEMP": str(self.request_root),
                "TMP": str(self.request_root),
                "HF_HUB_OFFLINE": "1",
                "HF_DATASETS_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "HF_HUB_DISABLE_TELEMETRY": "1",
            }
            env_text = "\0".join(f"{key}={value}" for key, value in sorted(environment.items(), key=lambda item: item[0].casefold())) + "\0\0"
            env_block = ctypes.create_unicode_buffer(env_text)
            command = ctypes.create_unicode_buffer(subprocess.list2cmdline([str(executable), *args]))
            flags = 0x00000004 | 0x00080000 | 0x00000400 | 0x08000000
            if not kernel32.CreateProcessW(str(executable), command, None, None, True, flags, ctypes.cast(env_block, ctypes.c_void_p), str(executable.parent), ctypes.byref(startup), ctypes.byref(process_info)):
                raise AppContainerRuntimeError("local_runtime_failed", "Windows could not launch the pinned AppContainer inference process", retryable=True)
            process_created = True
            for handle in child_handles:
                kernel32.CloseHandle(handle)
            handles = [stdout_read, stderr_read]
            if attr_ptr:
                kernel32.DeleteProcThreadAttributeList(attr_ptr)
                attr_ptr = ctypes.c_void_p()

            token = ctypes.c_void_p()
            if not advapi32.OpenProcessToken(process_info.hProcess, 0x0008, ctypes.byref(token)):
                raise AppContainerRuntimeError("network_isolation_unverified", "could not inspect the inference process token")
            try:
                is_appcontainer = self._token_value(advapi32, token, 29)
                capability_count = self._token_value(advapi32, token, 30)
            finally:
                kernel32.CloseHandle(token)
            if is_appcontainer != 1 or capability_count != 0:
                raise AppContainerRuntimeError("network_isolation_unverified", "inference process token is not a zero-capability AppContainer")

            from types import SimpleNamespace

            try:
                resource_job = self.resource_job_factory(SimpleNamespace(pid=int(process_info.dwProcessId)))
            except BaseException as exc:
                kernel32.TerminateProcess(process_info.hProcess, 125)
                kernel32.WaitForSingleObject(process_info.hProcess, 5000)
                raise AppContainerRuntimeError("resource_limit", "Windows could not enforce CPU and memory caps before inference") from exc
            deadline = time.monotonic() + timeout_seconds
            while True:
                read_output = False
                for index, output_handle in enumerate((stdout_read, stderr_read)):
                    if output_eof[index]:
                        continue
                    available = ctypes.c_uint32()
                    if not kernel32.PeekNamedPipe(output_handle, None, 0, None, ctypes.byref(available), None):
                        if ctypes.get_last_error() == 109:  # ERROR_BROKEN_PIPE
                            output_eof[index] = True
                            continue
                        raise AppContainerRuntimeError("local_runtime_failed", "could not inspect bounded AppContainer output")
                    if not available.value:
                        continue
                    captured_bytes = len(outputs[0]) + len(outputs[1])
                    read_size = min(available.value, 64 * 1024, MAX_CAPTURE_BYTES - captured_bytes + 1)
                    buffer = ctypes.create_string_buffer(read_size)
                    read_count = ctypes.c_uint32()
                    if not kernel32.ReadFile(output_handle, buffer, read_size, ctypes.byref(read_count), None):
                        if ctypes.get_last_error() == 109:
                            output_eof[index] = True
                            continue
                        raise AppContainerRuntimeError("local_runtime_failed", "could not read bounded AppContainer output")
                    if not read_count.value:
                        raise AppContainerRuntimeError("local_runtime_failed", "AppContainer output pipe returned no bytes while data was available")
                    outputs[index].extend(buffer.raw[:read_count.value])
                    if len(outputs[0]) + len(outputs[1]) > MAX_CAPTURE_BYTES:
                        raise AppContainerRuntimeError("resource_limit", "AppContainer inference output exceeded its byte limit")
                    read_output = True
                if read_output:
                    continue

                wait_result = kernel32.WaitForSingleObject(process_info.hProcess, 0)
                if wait_result == 0:
                    if process_finished:
                        break
                    process_finished = True
                    continue
                if wait_result != 0x00000102:
                    raise AppContainerRuntimeError("local_runtime_failed", "could not observe the AppContainer inference process exit", retryable=True)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AppContainerRuntimeError("response_late", "AppContainer inference exceeded its bounded deadline")
                time.sleep(min(0.02, remaining))
            exit_code = ctypes.c_uint32()
            if not kernel32.GetExitCodeProcess(process_info.hProcess, ctypes.byref(exit_code)):
                raise AppContainerRuntimeError("local_runtime_failed", "could not read the AppContainer inference exit code", retryable=True)
            self._last_process_limits_enforced = True
            return {
                "exit_code": int(exit_code.value),
                "stdout": outputs[0].decode("utf-8", errors="replace"),
                "stderr": outputs[1].decode("utf-8", errors="replace"),
                "is_appcontainer": True,
                "capability_count": 0,
                "resource_limits_enforced": True,
            }
        finally:
            if process_created and not process_finished:
                kernel32.TerminateProcess(process_info.hProcess, 125)
                kernel32.WaitForSingleObject(process_info.hProcess, 5000)
            if resource_job is not None:
                resource_job.close()
            if attr_ptr:
                kernel32.DeleteProcThreadAttributeList(attr_ptr)
            if process_created:
                for handle in (process_info.hThread, process_info.hProcess):
                    if handle:
                        kernel32.CloseHandle(handle)
            for handle in handles:
                if handle:
                    kernel32.CloseHandle(handle)

    def network_isolation(self) -> dict[str, Any]:
        return {
            "status": "enforced" if self._ready or self._last_process_limits_enforced else "unverified",
            "supervisor": "Windows AppContainer",
            "verification": "TokenIsAppContainer and zero token capabilities; no network probe",
            "checked_executables": ["llama-cli"],
            "network_capability_count": 0,
            "outbound_probe_performed": False,
        }

    def health(self) -> dict[str, Any]:
        resource_status = "enforced" if self._last_process_limits_enforced or self._ready else "not_running"
        return {
            "provider": "local_qwen_evidence_assessor",
            "status": "healthy" if self._ready and resource_status == "enforced" else "unavailable",
            "runtime": self.runtime_version,
            "model": f"{self.model_spec.get('revision')}:{self.model_spec.get('file')}",
            "model_sha256": self.model_spec.get("sha256"),
            "execution_device": "CPU",
            "resource_limits": {
                "status": resource_status,
                "supervisor": "Windows Job Object",
                "cpu_hard_cap_percent": MAX_RUNTIME_CPU_PERCENT,
                "process_commit_limit_bytes": MAX_RUNTIME_MEMORY_BYTES,
                "job_commit_limit_bytes": MAX_RUNTIME_MEMORY_BYTES,
                "working_set_limit_bytes": None,
                "cuda_limit_kind": "not_applicable",
            },
            "network_isolation": self.network_isolation(),
        }

    def stop(self) -> None:
        self._ready = False
        if self._sid:
            advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
            advapi32.FreeSid.argtypes = [ctypes.c_void_p]
            advapi32.FreeSid.restype = ctypes.c_void_p
            advapi32.FreeSid(self._sid)
            self._sid = None
