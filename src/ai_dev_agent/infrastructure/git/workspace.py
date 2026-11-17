import base64
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit
from uuid import uuid4

from ai_dev_agent.infrastructure.logging.workflow_trace import redact_trace_text

_SKIP_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "vendor",
    "target",
    "dist",
    "build",
}
_SKIP_SUFFIXES = {".lock", ".pem", ".key", ".p12", ".pfx"}
_SENSITIVE_NAME_MARKERS = ("credential", "secret", "token", "id_rsa", "id_ed25519")
_MAX_FILE_SIZE = 32_000
_MAX_CONTEXT_CHARS = 100_000
_MAX_FILES = 80


class RepositoryPatchError(ValueError):
    pass


def _github_repository_parts(repository_url: str) -> tuple[str, str, str]:
    parsed = urlsplit(repository_url.strip())
    parts = parsed.path.strip("/").split("/")
    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or len(parts) != 2
    ):
        raise ValueError("Repository URL must be an HTTPS GitHub owner/repository URL")

    owner, repository = parts
    repository = repository.removesuffix(".git")
    if (
        owner in {".", ".."}
        or repository in {".", ".."}
        or not re.fullmatch(r"[A-Za-z0-9_.-]+", owner)
        or not re.fullmatch(r"[A-Za-z0-9_.-]+", repository)
    ):
        raise ValueError("Repository URL contains an invalid owner or repository name")
    return owner, repository, f"https://github.com/{owner}/{repository}.git"


def clone_github_repository(repository_url: str, github_token: str | None = None) -> Path:
    owner, repository, clone_url = _github_repository_parts(repository_url)
    repository_root = Path(__file__).resolve().parents[4] / "repos" / "cloned-projects"
    repository_root.mkdir(parents=True, exist_ok=True)
    clone_path = repository_root / f"{owner}-{repository}-{uuid4().hex[:8]}"

    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    if github_token:
        credential = base64.b64encode(f"x-access-token:{github_token}".encode()).decode()
        environment["GIT_CONFIG_COUNT"] = "1"
        environment["GIT_CONFIG_KEY_0"] = "http.https://github.com/.extraheader"
        environment["GIT_CONFIG_VALUE_0"] = f"AUTHORIZATION: basic {credential}"

    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", clone_url, str(clone_path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError) as error:
        if clone_path.exists():
            shutil.rmtree(clone_path)
        raise RuntimeError(
            "Unable to clone the GitHub repository. Check the URL, access, and GITHUB_TOKEN."
        ) from error
    return clone_path


def repository_context(repository_path: Path) -> str:
    root = repository_path.resolve()
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=True,
        capture_output=True,
        timeout=15,
    )
    paths = result.stdout.decode("utf-8", errors="replace").split("\0")
    sections: list[str] = []
    total_chars = 0

    for relative_path in paths:
        if not relative_path or len(sections) >= _MAX_FILES:
            break
        path = PurePosixPath(relative_path)
        if (
            path.is_absolute()
            or "\\" in relative_path
            or any(part in _SKIP_DIRECTORIES for part in path.parts)
            or path.name.lower().startswith(".env")
            or any(marker in path.name.lower() for marker in _SENSITIVE_NAME_MARKERS)
            or path.suffix.lower() in _SKIP_SUFFIXES
        ):
            continue

        file_path = root.joinpath(*path.parts)
        if not file_path.resolve().is_relative_to(root):
            continue
        try:
            if file_path.stat().st_size > _MAX_FILE_SIZE:
                continue
            content = file_path.read_bytes()
        except OSError:
            continue
        if b"\0" in content:
            continue

        text = content.decode("utf-8", errors="replace")
        remaining = _MAX_CONTEXT_CHARS - total_chars
        if remaining <= 0:
            break
        text = text[:remaining]
        sections.append(f"### {relative_path}\n{text}")
        total_chars += len(text)

    if not sections:
        return "No small, tracked text files were available for repository analysis."
    return "\n\n".join(sections)


def apply_unified_diff(repository_path: Path, unified_diff: str) -> list[str]:
    if not unified_diff.strip():
        return []

    root = repository_path.resolve()
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".patch",
        delete=False,
    ) as patch_file:
        patch_file.write(unified_diff)
        patch_path = Path(patch_file.name)

    try:
        numstat = subprocess.run(
            ["git", "-C", str(root), "apply", "--recount", "--numstat", str(patch_path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        changed_paths = [line.split("\t", 2)[2] for line in numstat.stdout.splitlines()]
        if not changed_paths:
            raise ValueError("Generated patch did not identify any changed files")

        for relative_path in changed_paths:
            path = PurePosixPath(relative_path)
            if (
                path.is_absolute()
                or "\\" in relative_path
                or any(":" in part for part in path.parts)
                or not path.parts
                or any(part in {"..", ".git"} for part in path.parts)
                or path.name.lower().startswith(".env")
                or any(marker in path.name.lower() for marker in _SENSITIVE_NAME_MARKERS)
                or path.suffix.lower() in _SKIP_SUFFIXES
            ):
                raise ValueError("Generated patch contains an unsafe repository path")
            target = root.joinpath(*path.parts)
            if not target.parent.resolve().is_relative_to(root):
                raise ValueError("Generated patch resolves outside the repository")
            if target.exists() and not target.resolve().is_relative_to(root):
                raise ValueError("Generated patch follows a path outside the repository")

        subprocess.run(
            ["git", "-C", str(root), "apply", "--recount", "--check", str(patch_path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        subprocess.run(
            ["git", "-C", str(root), "apply", "--recount", str(patch_path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return changed_paths
    except subprocess.CalledProcessError as error:
        detail = error.stderr or error.stdout or "Git rejected the patch without details."
        detail = redact_trace_text(detail.strip())[:500]
        raise RepositoryPatchError(f"Git rejected the generated diff: {detail}") from error
    finally:
        patch_path.unlink(missing_ok=True)