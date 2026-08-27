#!/usr/bin/env python3
"""Fail-closed public-release guard for tracked files and reachable Git history.

The guard intentionally reports rule, scope, path, line, and (for history) blob
identity only. It never prints matched text, secret values, URLs, or command
output, so its output can be attached to a review without creating another
secret leak.

This draft is dependency-free and is intended to be copied to
``scripts/public_repo_guard.py`` after review.
"""

from __future__ import annotations

import argparse
import dataclasses
import fnmatch
import json
import os
import re
import stat
import subprocess
import sys
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path, PurePosixPath
from typing import BinaryIO


class GuardError(RuntimeError):
    """Operational failure. Findings use a separate, non-error exit code."""


@dataclasses.dataclass(frozen=True, order=True)
class Finding:
    """One redacted finding; matched values are deliberately absent."""

    scope: str
    rule: str
    path: str
    line: int | None = None
    object_id: str | None = None

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "scope": self.scope,
            "rule": self.rule,
            "path": self.path,
        }
        if self.line is not None:
            result["line"] = self.line
        if self.object_id is not None:
            result["object_id"] = self.object_id
        return result


def _sort_findings(findings: Iterable[Finding]) -> list[Finding]:
    return sorted(
        findings,
        key=lambda finding: (
            finding.scope,
            finding.rule,
            finding.path,
            finding.line if finding.line is not None else -1,
            finding.object_id or "",
        ),
    )


_HEX_OBJECT_ID = re.compile(r"^[0-9a-f]{40}$")

# Exact documented AWS examples. Other access-key-shaped values remain
# findings, including values in tests; tests must construct fakes at runtime.
_SAMPLE_ACCESS_KEYS = {
    "AK" + "IAIOSFODNN7EXAMPLE",
    "AS" + "IAIOSFODNN7EXAMPLE",
}
_SAMPLE_SECRET_KEYS = {
    "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
}
_SAMPLE_ACCOUNT_IDS = {
    "000000000000",
    "111111111111",
    "123456789012",
    "999999999999",
}

_EXAMPLE_SUFFIXES = (".example", ".sample", ".template")
_EXAMPLE_PATH_WORDS = {
    "example",
    "examples",
    "fixture",
    "fixtures",
    "mock",
    "mocks",
    "sample",
    "samples",
    "template",
    "templates",
    "dummy",
    "dummies",
    "placeholder",
    "placeholders",
    "test",
    "tests",
}
_PLACEHOLDER_WORDS = (
    "example",
    "sample",
    "dummy",
    "fake",
    "placeholder",
    "redacted",
    "changeme",
    "change-me",
    "replace-me",
    "your_",
    "your-",
    "your ",
    "<your",
    "<replace",
    "${",
    "xxxx",
    "****",
)

_AWS_ACCESS_KEY_RE = re.compile(r"\b(?:AKIA|ASIA|AIDA|AROA|AGPA|ANPA|ANVA)[A-Z0-9]{16}\b")
_AWS_SECRET_CONTEXT_RE = re.compile(
    r"(?ix)\b(?:aws[_-]?secret(?:[_-]?access)?[_-]?key|secret[_-]?access[_-]?key)\b"
    r"\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?"
)
_GITHUB_TOKEN_RE = re.compile(r"\b(?:gh[pousr]|github_pat)_[A-Za-z0-9_]{20,}\b")
_SLACK_TOKEN_RE = re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{20,}\b")
_GOOGLE_API_KEY_RE = re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")
_SENDGRID_TOKEN_RE = re.compile(r"\bSG\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b")
_NPM_TOKEN_RE = re.compile(r"\bnpm_[A-Za-z0-9]{30,}\b")
_NPMRC_AUTH_RE = re.compile(r"(?i)^\s*(?://[^=\s]+/:)?(?:_auth|_authToken|username|password)\s*=\s*(\S.*)$")
_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN(?: [A-Z0-9]+)* " + r"PRIVATE KEY-----|-----BEGIN PGP " + r"PRIVATE KEY BLOCK-----",
    re.IGNORECASE,
)
_DATABASE_URL_RE = re.compile(
    r"\b(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis(?:s)?|amqp(?:s)?)://"
    r"[^\s:/@]+:([^\s/@]+)@",
    re.IGNORECASE,
)
_TEST_DATABASE_PASSWORD_RE = re.compile(
    r"(?i)^(?:test|testing|fake|dummy|invalid|wrong|pass|password|postgres|example|secret)"
    r"(?:[-_][a-z0-9]+)*$"
)
_AWS_SIGNED_URL_RE = re.compile(
    r"(?i)(?:x-amz-algorithm\s*=\s*aws4-hmac-sha256.*x-amz-signature\s*=|"
    r"x-amz-signature\s*=[0-9a-f]{32,}|"
    r"awsaccesskeyid\s*=[^&\s]+.*(?:^|[&])signature\s*=[^&\s]+)"
)
_AWS_ACCOUNT_CONTEXT_RE = re.compile(
    r"(?i)(?:\barn:aws\b|amazonaws\.com|\baws[_-]?account\b|\baws\b|"
    r"(?<![A-Za-z0-9])account(?:[ _-]*(?:id|number))?\b|"
    r"\becr\b|\bec2\b|\beks\b|\biam\b|\bcloudfront\b|\broute53\b|\bs3\b|"
    r"\bssm\b|\brds\b|\bdynamodb\b|\bsts\b|\bterraform\b)"
)
_AWS_ACCOUNT_ID_RE = re.compile(r"(?<!\d)\d{12}(?!\d)")
_WINDOWS_USER_PATH_RE = re.compile(r"(?i)(?<![A-Za-z0-9])(?:[A-Za-z]:[\\/]+Users[\\/]+)([A-Za-z0-9._-]+)")
_POSIX_USER_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:home|Users)/([A-Za-z0-9._-]+)(?:/|$)")

_ALLOWED_USER_NAMES = {
    "default",
    "ec2-user",
    "example",
    "guest",
    "public",
    "root",
    "runner",
    "sample",
    "test",
    "tester",
    "ubuntu",
    "user",
    "username",
    "yourname",
}

_FORBIDDEN_REF_PREFIXES = (
    "refs/codex/",
    "refs/original/",
    "refs/replace/",
    "refs/t3/",
)
_FORBIDDEN_EXACT_REFS = {"refs/stash"}


def _normalise_path(path: str) -> str:
    return path.replace("\\", "/")


def _path_parts(path: str) -> list[str]:
    normalised = _normalise_path(path).lower()
    return [part for part in PurePosixPath(normalised).parts if part not in {".", "/"}]


def _is_obvious_example_path(path: str) -> bool:
    parts = _path_parts(path)
    name = parts[-1] if parts else ""
    if any(part in _EXAMPLE_PATH_WORDS for part in parts[:-1]):
        return True
    return any(name.endswith(suffix) for suffix in _EXAMPLE_SUFFIXES)


def _is_placeholder_line(line: str) -> bool:
    lowered = line.lower()
    return any(marker in lowered for marker in _PLACEHOLDER_WORDS)


def _is_safe_example_config_name(path: str) -> bool:
    name = PurePosixPath(_normalise_path(path)).name.lower()
    if name in {".env.example", ".env.sample", ".env.template"}:
        return True
    return any(name.endswith(f".tfvars{suffix}") for suffix in _EXAMPLE_SUFFIXES)


def _sensitive_filename_rule(path: str) -> str | None:
    """Return filename rule without inspecting content."""

    normalised = _normalise_path(path)
    name = PurePosixPath(normalised).name.lower()
    if _is_safe_example_config_name(normalised):
        return None

    # The root config contains only non-secret package-manager behavior. Its
    # content is still checked below for auth assignments and token patterns.
    if normalised == ".npmrc":
        return None
    if name in {".env", ".netrc", ".npmrc", ".pypirc", "credentials", "aws_credentials", "aws-credentials"}:
        return "forbidden-sensitive-filename"
    if name.startswith(".env."):
        return "forbidden-sensitive-filename"
    if name.startswith("credentials.") or name in {"credentials.json", "credentials.yml", "credentials.yaml"}:
        return "forbidden-sensitive-filename"
    if any(fnmatch.fnmatch(name, pattern) for pattern in ("*.tfstate", "*.tfstate.*", "*.tfvars")):
        return "forbidden-sensitive-filename"
    if any(name.endswith(extension) for extension in (".pem", ".key", ".p12", ".pfx", ".jks", ".keystore", ".ppk")):
        return "forbidden-sensitive-filename"
    private_key_prefixes = ("id_rsa", "id_dsa", "id_ecdsa", "id_ed25519")
    if any(name == prefix or name.startswith(f"{prefix}.") for prefix in private_key_prefixes):
        return "forbidden-sensitive-filename"
    if name.endswith((".log", ".out", ".dump")):
        return "forbidden-sensitive-filename"

    # Deployment transcripts often use Markdown/TXT names, so extension-only
    # checks miss exactly the AWS logs this guard is meant to catch.
    if "log" in name and any(word in name for word in ("aws", "deploy", "teardown", "terraform", "cloudfront", "eks")):
        return "forbidden-sensitive-filename"
    return None


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _looks_binary(data: bytes) -> bool:
    sample = data[:8192]
    if b"\x00" in sample:
        return True
    if not sample:
        return False
    control_count = sum(byte < 9 or 13 < byte < 32 for byte in sample)
    return control_count > max(8, len(sample) // 20)


def _safe_example_access_key(value: str) -> bool:
    return value in _SAMPLE_ACCESS_KEYS


def _safe_example_secret(value: str) -> bool:
    return value in _SAMPLE_SECRET_KEYS


def _safe_account_id(value: str, line: str, path: str) -> bool:
    if value in _SAMPLE_ACCOUNT_IDS:
        return True
    return _is_placeholder_line(line)


def _safe_database_password(value: str, line: str, path: str) -> bool:
    if _is_placeholder_line(value) or _is_placeholder_line(line):
        return True
    return _is_obvious_example_path(path) and bool(_TEST_DATABASE_PASSWORD_RE.fullmatch(value))


def _safe_user_name(value: str, line: str, path: str) -> bool:
    return value.lower() in _ALLOWED_USER_NAMES or _is_placeholder_line(line)


def scan_text(text: str, path: str, scope: str, object_id: str | None = None) -> list[Finding]:
    """Scan text while returning metadata only, never matched values."""

    findings: set[Finding] = set()
    lines = text.splitlines()
    for line_number, line in enumerate(lines, 1):
        for match in _AWS_ACCESS_KEY_RE.finditer(line):
            if not _safe_example_access_key(match.group(0)):
                findings.add(Finding(scope, "aws-access-key-id", path, line_number, object_id))

        for match in _AWS_SECRET_CONTEXT_RE.finditer(line):
            if not _safe_example_secret(match.group(1)) and not _is_placeholder_line(line):
                findings.add(Finding(scope, "aws-secret-access-key", path, line_number, object_id))

        for pattern, rule in (
            (_GITHUB_TOKEN_RE, "github-token"),
            (_SLACK_TOKEN_RE, "slack-token"),
            (_GOOGLE_API_KEY_RE, "google-api-key"),
            (_SENDGRID_TOKEN_RE, "sendgrid-token"),
            (_NPM_TOKEN_RE, "npm-token"),
        ):
            if pattern.search(line) and not _is_placeholder_line(line):
                findings.add(Finding(scope, rule, path, line_number, object_id))

        is_npmrc = PurePosixPath(_normalise_path(path)).name.lower() == ".npmrc"
        npmrc_auth = _NPMRC_AUTH_RE.search(line) if is_npmrc else None
        if npmrc_auth and not _is_placeholder_line(npmrc_auth.group(1)):
            findings.add(Finding(scope, "npm-auth-config", path, line_number, object_id))

        for match in _DATABASE_URL_RE.finditer(line):
            if not _safe_database_password(match.group(1), line, path):
                findings.add(Finding(scope, "database-url-credential", path, line_number, object_id))

        if _AWS_SIGNED_URL_RE.search(line) and not _is_placeholder_line(line):
            findings.add(Finding(scope, "signed-url", path, line_number, object_id))

        if _AWS_ACCOUNT_CONTEXT_RE.search(line):
            for match in _AWS_ACCOUNT_ID_RE.finditer(line):
                if not _safe_account_id(match.group(0), line, path):
                    findings.add(Finding(scope, "aws-account-id", path, line_number, object_id))

        for match in _WINDOWS_USER_PATH_RE.finditer(line):
            if not _safe_user_name(match.group(1), line, path):
                findings.add(Finding(scope, "local-user-path", path, line_number, object_id))
        for match in _POSIX_USER_PATH_RE.finditer(line):
            if not _safe_user_name(match.group(1), line, path):
                findings.add(Finding(scope, "local-user-path", path, line_number, object_id))

    for match in _PRIVATE_KEY_RE.finditer(text):
        findings.add(Finding(scope, "private-key", path, _line_number(text, match.start()), object_id))

    return _sort_findings(findings)


def scan_bytes(data: bytes, path: str, scope: str, object_id: str | None = None) -> list[Finding]:
    if _looks_binary(data):
        return []
    return scan_text(data.decode("utf-8", errors="replace"), path, scope, object_id)


def _git_argv(root: Path, args: Sequence[str]) -> list[str]:
    # safe.directory avoids requiring a global Git configuration change when a
    # mounted checkout is owned by another local account.
    return ["git", "-c", f"safe.directory={root.as_posix()}", *args]


def _git_bytes(root: Path, args: Sequence[str]) -> bytes:
    try:
        completed = subprocess.run(
            _git_argv(root, args),
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise GuardError("required Git operation failed") from exc
    return completed.stdout


def _tracked_paths(root: Path) -> list[str]:
    raw = _git_bytes(root, ["ls-files", "-z"])
    paths: list[str] = []
    for item in raw.split(b"\0"):
        if item:
            paths.append(_normalise_path(os.fsdecode(item)))
    return paths


def _read_working_file(root: Path, relative_path: str) -> bytes | None:
    """Read only tracked regular files; never follow a tracked symlink."""

    candidate = root.joinpath(*relative_path.split("/"))
    try:
        root_resolved = root.resolve()
        candidate_resolved = candidate.resolve(strict=False)
        candidate_resolved.relative_to(root_resolved)
        metadata = os.lstat(candidate)
    except (OSError, ValueError):
        return None
    if stat.S_ISLNK(metadata.st_mode):
        try:
            return os.readlink(candidate).encode("utf-8", errors="replace")
        except OSError:
            return None
    if not stat.S_ISREG(metadata.st_mode):
        return None
    try:
        return candidate.read_bytes()
    except OSError:
        return None


def scan_tree(root: Path) -> list[Finding]:
    findings: set[Finding] = set()
    for path in _tracked_paths(root):
        filename_rule = _sensitive_filename_rule(path)
        if filename_rule:
            findings.add(Finding("tree", filename_rule, path))
        data = _read_working_file(root, path)
        if data is not None:
            findings.update(scan_bytes(data, path, "tree"))
    return _sort_findings(findings)


def _history_blob_paths(root: Path) -> dict[str, set[str]]:
    raw = _git_bytes(root, ["rev-list", "--objects", "--all"])
    result: dict[str, set[str]] = {}
    for line in raw.splitlines():
        parts = line.split(maxsplit=1)
        if not parts or not _HEX_OBJECT_ID.fullmatch(parts[0].decode("ascii", errors="ignore")):
            continue
        if len(parts) == 1:
            continue
        object_id = parts[0].decode("ascii")
        path = _normalise_path(os.fsdecode(parts[1]))
        result.setdefault(object_id, set()).add(path)
    return result


def _history_paths(root: Path) -> set[str]:
    raw = _git_bytes(root, ["log", "--all", "--format=", "--name-only", "-z"])
    paths: set[str] = set()
    for item in raw.split(b"\0"):
        path = _normalise_path(os.fsdecode(item).strip("\r\n"))
        if path:
            paths.add(path)
    return paths


def _git_database_findings(root: Path) -> list[Finding]:
    findings: set[Finding] = set()
    refs = _git_bytes(root, ["for-each-ref", "--format=%(refname)"]).decode("utf-8", errors="replace")
    for ref in refs.splitlines():
        if ref in _FORBIDDEN_EXACT_REFS or ref.startswith(_FORBIDDEN_REF_PREFIXES):
            findings.add(Finding("history", "private-git-ref", ref))

    fsck = _git_bytes(root, ["fsck", "--full", "--no-reflogs", "--unreachable", "--no-progress"])
    for line in fsck.decode("ascii", errors="replace").splitlines():
        fields = line.split()
        object_id = next((field for field in fields if _HEX_OBJECT_ID.fullmatch(field)), None)
        if fields and fields[0] in {"unreachable", "dangling"}:
            findings.add(Finding("history", "unreachable-git-object", "<git-object-database>", object_id=object_id))
    return _sort_findings(findings)


def _commit_metadata_findings(root: Path) -> list[Finding]:
    raw = _git_bytes(root, ["log", "--all", "--format=%H%x00%B%x00%an <%ae>%n%cn <%ce>%x00"])
    fields = raw.split(b"\0")
    findings: set[Finding] = set()
    for index in range(0, len(fields) - 2, 3):
        object_id = fields[index].decode("ascii", errors="ignore").strip()
        if not _HEX_OBJECT_ID.fullmatch(object_id):
            continue
        message = fields[index + 1].decode("utf-8", errors="replace")
        identity = fields[index + 2].decode("utf-8", errors="replace")
        findings.update(scan_text(message, "<commit-message>", "history", object_id))
        findings.update(scan_text(identity, "<commit-identity>", "history", object_id))
    return _sort_findings(findings)


def _batch_blob_types(root: Path, object_ids: Iterable[str]) -> set[str]:
    ids = list(object_ids)
    if not ids:
        return set()
    try:
        completed = subprocess.run(
            _git_argv(root, ["cat-file", "--batch-check"]),
            cwd=root,
            input=("\n".join(ids) + "\n").encode("ascii"),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise GuardError("required Git object inspection failed") from exc
    blobs: set[str] = set()
    for line in completed.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[1] == b"blob":
            blobs.add(fields[0].decode("ascii"))
    return blobs


def _read_exact(stream: BinaryIO, size: int) -> bytes:
    # BufferedReader.read is typed as Any on supported Python versions; this
    # local helper keeps the runtime check explicit and fails closed on short
    # Git output.
    read = stream.read
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = read(remaining)
        if not chunk:
            raise GuardError("Git returned truncated object data")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _iter_blob_data(root: Path, object_ids: Iterable[str]) -> Iterator[tuple[str, bytes]]:
    ids = list(object_ids)
    if not ids:
        return
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            _git_argv(root, ["cat-file", "--batch"]),
            cwd=root,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        if process.stdin is None or process.stdout is None:
            raise GuardError("Git object stream unavailable")
        for object_id in ids:
            process.stdin.write(object_id.encode("ascii") + b"\n")
            process.stdin.flush()
            header = process.stdout.readline()
            fields = header.split()
            if len(fields) != 3 or fields[1] != b"blob":
                raise GuardError("Git returned unexpected object type")
            size = int(fields[2])
            data = _read_exact(process.stdout, size)
            if process.stdout.read(1) != b"\n":
                raise GuardError("Git returned malformed object data")
            yield object_id, data
        process.stdin.close()
        if process.wait(timeout=30) != 0:
            raise GuardError("Git object stream failed")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise GuardError("required Git object stream failed") from exc
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
                process.wait()
            if process.stdin is not None and not process.stdin.closed:
                process.stdin.close()
            if process.stdout is not None and not process.stdout.closed:
                process.stdout.close()


def scan_history(root: Path) -> list[Finding]:
    paths_by_object = _history_blob_paths(root)
    blob_ids = _batch_blob_types(root, paths_by_object)
    findings: set[Finding] = set(_git_database_findings(root))
    findings.update(_commit_metadata_findings(root))

    for path in _history_paths(root):
        filename_rule = _sensitive_filename_rule(path)
        if filename_rule:
            findings.add(Finding("history", filename_rule, path))

    for object_id, paths in paths_by_object.items():
        if object_id not in blob_ids:
            continue
        for path in paths:
            filename_rule = _sensitive_filename_rule(path)
            if filename_rule:
                findings.add(Finding("history", filename_rule, path, object_id=object_id))

    for object_id, data in _iter_blob_data(root, blob_ids):
        for path in paths_by_object.get(object_id, {"<unmapped-blob>"}):
            findings.update(scan_bytes(data, path, "history", object_id))
    return _sort_findings(findings)


def run_guard(root: Path, mode: str) -> list[Finding]:
    if mode == "tree":
        return scan_tree(root)
    if mode == "history":
        return scan_history(root)
    findings = scan_tree(root)
    findings.extend(scan_history(root))
    return _sort_findings(set(findings))


def _render_human(findings: Sequence[Finding]) -> str:
    if not findings:
        return "PUBLIC_REPO_GUARD_PASS"
    lines = ["PUBLIC_REPO_GUARD_FAIL"]
    for finding in findings:
        location = finding.path
        if finding.line is not None:
            location += f":{finding.line}"
        if finding.object_id is not None:
            location += f" [blob {finding.object_id}]"
        lines.append(f"{finding.scope} {finding.rule} {location}")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan tracked files and reachable Git history for public-release secrets."
    )
    parser.add_argument("mode", nargs="?", choices=("tree", "history", "all"), default="all")
    parser.add_argument("--root", type=Path, default=Path("."), help="repository root (default: current directory)")
    parser.add_argument("--json", action="store_true", dest="as_json", help="emit redacted machine-readable findings")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        root = args.root.resolve()
        findings = run_guard(root, args.mode)
    except GuardError as exc:
        print(f"PUBLIC_REPO_GUARD_ERROR: {exc}", file=sys.stderr)
        return 2

    if args.as_json:
        print(json.dumps({"ok": not findings, "findings": [finding.as_dict() for finding in findings]}, sort_keys=True))
    else:
        print(_render_human(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
