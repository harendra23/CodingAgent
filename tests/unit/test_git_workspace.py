import subprocess

import pytest

from ai_dev_agent.infrastructure.git.workspace import (
    RepositoryPatchError,
    apply_unified_diff,
    repository_context,
)


def init_repository(path) -> None:
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    (path / "src").mkdir()
    (path / "src" / "app.py").write_text("VALUE = 'old'\n", encoding="utf-8")
    (path / ".env").write_text("TOKEN=do-not-read\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True, capture_output=True)


def test_repository_context_excludes_environment_files(tmp_path) -> None:
    init_repository(tmp_path)

    context = repository_context(tmp_path)

    assert "src/app.py" in context
    assert "VALUE = 'old'" in context
    assert ".env" not in context
    assert "do-not-read" not in context


def test_generated_diff_updates_existing_and_adds_new_files(tmp_path) -> None:
    init_repository(tmp_path)
    patch = """diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -1 +1 @@
-VALUE = 'old'
+VALUE = 'new'
diff --git a/src/new.py b/src/new.py
new file mode 100644
--- /dev/null
+++ b/src/new.py
@@ -0,0 +1 @@
+NEW_FEATURE = True
"""

    changed = apply_unified_diff(tmp_path, patch)

    assert changed == ["src/app.py", "src/new.py"]
    assert (tmp_path / "src" / "app.py").read_text(encoding="utf-8") == "VALUE = 'new'\n"
    assert (tmp_path / "src" / "new.py").read_text(encoding="utf-8") == "NEW_FEATURE = True\n"


def test_generated_diff_rejects_parent_directory_path(tmp_path) -> None:
    init_repository(tmp_path)
    patch = """diff --git a/../outside.txt b/../outside.txt
new file mode 100644
--- /dev/null
+++ b/../outside.txt
@@ -0,0 +1 @@
+not safe
"""

    with pytest.raises(ValueError, match="unsafe repository path"):
        apply_unified_diff(tmp_path, patch)


def test_generated_diff_includes_git_context_mismatch_diagnostic(tmp_path) -> None:
    init_repository(tmp_path)
    patch = """diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -4 +4 @@
-VALUE = 'missing-value'
+VALUE = 'new-value'
"""

    with pytest.raises(RepositoryPatchError, match="Git rejected the generated diff"):
        apply_unified_diff(tmp_path, patch)


def test_generated_diff_recounts_incorrect_hunk_line_counts(tmp_path) -> None:
    init_repository(tmp_path)
    patch = """diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -1,2 +1,2 @@
-VALUE = 'old'
+VALUE = 'recounted'
"""

    changed = apply_unified_diff(tmp_path, patch)

    assert changed == ["src/app.py"]
    assert (tmp_path / "src" / "app.py").read_text(encoding="utf-8") == "VALUE = 'recounted'\n"