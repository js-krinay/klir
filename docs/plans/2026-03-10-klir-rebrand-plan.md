# klir Rebrand Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rename the project from `ductor` to `klir` across the entire codebase, reset version to 0.1.0, update CI to use `uv build`/`uv publish`, and prepare for PyPI release.

**Architecture:** This is a pure rename — no logic changes. The work is mechanical: rename the package directory, do ordered global find-replace passes, update build config, update docs, verify with tests and build. Order matters because some replacements are substrings of others (e.g., `ductor_bot` must be replaced before bare `ductor`).

**Tech Stack:** Python 3.11+, hatchling (build backend), uv (build/publish frontend), ruff, mypy, pytest

---

### Task 1: Rename Package Directory

The core directory rename. Git tracks this as a rename if content similarity is high enough. Must be done first before any text replacements so file paths are correct.

**Files:**
- Rename: `ductor_bot/` -> `klir/`
- Rename: `klir/bot/ductor_images/` -> `klir/bot/klir_images/`

**Step 1: Rename the main package directory**

```bash
git mv ductor_bot klir
```

**Step 2: Rename the images subdirectory**

```bash
git mv klir/bot/ductor_images klir/bot/klir_images
```

**Step 3: Delete old branding images**

```bash
rm klir/bot/klir_images/welcome.png klir/bot/klir_images/logo_text.png
rm docs/images/ductor-start.jpeg docs/images/ductor-quick-actions.jpeg
git add -u klir/bot/klir_images/ docs/images/
```

**Step 4: Commit**

```bash
git add -A
git commit -m "refactor: Rename ductor_bot/ to klir/ and remove old images"
```

---

### Task 2: Global Find-Replace — Python Module References

Replace all `ductor_bot` references (imports, patch targets, config strings) with `klir`. This is the highest-volume replacement and must happen before replacing bare `ductor`.

**Files:**
- Modify: All `.py` files in `klir/` and `tests/`
- Modify: `pyproject.toml`

**Step 1: Replace `ductor_bot` with `klir` in all Python files**

```bash
find klir tests -name '*.py' -exec sed -i 's/ductor_bot/klir/g' {} +
```

**Step 2: Replace `ductor_bot` in pyproject.toml**

```bash
sed -i 's/ductor_bot/klir/g' pyproject.toml
```

**Step 3: Run tests to check nothing is broken**

```bash
uv run pytest --tb=short -q 2>&1 | tail -20
```

Expected: All tests pass (imports resolve to new `klir` module).

**Step 4: Commit**

```bash
git add -A
git commit -m "refactor: Replace ductor_bot with klir in all imports"
```

---

### Task 3: Global Find-Replace — Class Names, Config Keys, Env Vars

Replace structured identifiers that contain "ductor" in specific patterns. Order matters: longer/more-specific patterns first.

**Files:**
- Modify: All `.py` files in `klir/` and `tests/`
- Modify: `config.example.json`

**Step 1: Replace class names**

```bash
find klir tests -name '*.py' -exec sed -i 's/DuctorPaths/KlirPaths/g' {} +
find klir tests -name '*.py' -exec sed -i 's/DuctorConfig/KlirConfig/g' {} +
```

**Step 2: Replace config field names**

```bash
find klir tests -name '*.py' -exec sed -i 's/ductor_home/klir_home/g' {} +
sed -i 's/ductor_home/klir_home/g' config.example.json
```

**Step 3: Replace environment variables (DUCTOR_ -> KLIR_)**

```bash
find klir tests -name '*.py' -exec sed -i 's/DUCTOR_/KLIR_/g' {} +
```

**Step 4: Replace Docker defaults**

```bash
find klir tests -name '*.py' -exec sed -i 's/ductor-sandbox/klir-sandbox/g' {} +
sed -i 's/ductor-sandbox/klir-sandbox/g' config.example.json Dockerfile.sandbox
```

**Step 5: Run tests**

```bash
uv run pytest --tb=short -q 2>&1 | tail -20
```

Expected: All tests pass.

**Step 6: Commit**

```bash
git add -A
git commit -m "refactor: Rename classes, config keys, and env vars to klir"
```

---

### Task 4: Global Find-Replace — Service Names and Path Strings

Replace bare `ductor` in service names, CLI references, and path strings. This is the trickiest pass because bare `ductor` can appear in many contexts. Must be done carefully — not a blind global replace.

**Files:**
- Modify: `klir/infra/service_linux.py`, `klir/infra/service_macos.py`, `klir/infra/service_windows.py`
- Modify: `klir/__main__.py`
- Modify: All `.py` files with `~/.ductor` path strings
- Modify: `klir/_home_defaults/` template files (RULES, tool scripts)

**Step 1: Replace service names**

```bash
# Linux systemd
sed -i 's/_SERVICE_NAME = "ductor"/_SERVICE_NAME = "klir"/g' klir/infra/service_linux.py
sed -i 's/Description=ductor/Description=klir/g' klir/infra/service_linux.py

# macOS launchd
sed -i 's/dev\.ductor/dev.klir/g' klir/infra/service_macos.py

# Windows Task Scheduler
sed -i 's/_TASK_NAME = "ductor"/_TASK_NAME = "klir"/g' klir/infra/service_windows.py
```

**Step 2: Replace ~/.ductor path strings in all Python files**

```bash
find klir tests -name '*.py' -exec sed -i 's|~/\.ductor|~/.klir|g' {} +
find klir tests -name '*.py' -exec sed -i "s|/\.ductor|/.klir|g" {} +
```

**Step 3: Replace ~/.ductor in template/default files**

```bash
find klir/_home_defaults -type f -exec sed -i 's|~/\.ductor|~/.klir|g' {} +
find klir/_home_defaults -type f -exec sed -i 's/DUCTOR_/KLIR_/g' {} +
find klir/_home_defaults -type f -exec sed -i 's/ductor-sandbox/klir-sandbox/g' {} +
```

**Step 4: Replace remaining bare "ductor" in Python source (CLI help text, log messages, comments)**

Use targeted replacement — replace `"ductor"` and `ductor` in string contexts:

```bash
# Remaining bare ductor references in Python files (carefully)
find klir -name '*.py' -exec sed -i 's/\bductor\b/klir/g' {} +
find tests -name '*.py' -exec sed -i 's/\bductor\b/klir/g' {} +
```

**Step 5: Replace in config.example.json**

```bash
sed -i 's|~/\.ductor|~/.klir|g' config.example.json
sed -i 's/ductor/klir/g' config.example.json
```

**Step 6: Replace ductor_images references**

```bash
find klir tests -name '*.py' -exec sed -i 's/ductor_images/klir_images/g' {} +
```

**Step 7: Run tests**

```bash
uv run pytest --tb=short -q 2>&1 | tail -20
```

Expected: All tests pass.

**Step 8: Commit**

```bash
git add -A
git commit -m "refactor: Replace service names, paths, and strings to klir"
```

---

### Task 5: Update pyproject.toml — Metadata, Author, Build Config

Update all project metadata, author info, URLs, and prepare for uv-based publishing.

**Files:**
- Modify: `pyproject.toml`

**Step 1: Update project metadata**

In `pyproject.toml`, make these changes:

```toml
[project]
name = "klir"
version = "0.1.0"
description = "Control AI coding CLIs from Telegram. Live streaming, sessions, cron jobs, webhooks, Docker sandboxing. Originally forked from ductor by PleasePrompto."
authors = [{ name = "Jinay Shah" }]
keywords = [
    "klir", "ai", "telegram", "bot", "agent",
    "claude", "codex", "cli", "automation", "streaming",
]
```

**Step 2: Update URLs**

```toml
[project.urls]
Repository = "https://github.com/js-krinay/klir"
Issues = "https://github.com/js-krinay/klir/issues"
Changelog = "https://github.com/js-krinay/klir/releases"
```

Remove `Homepage` and `Documentation` pointing to `ductor.dev` (or update if you have a domain).

**Step 3: Update entry point**

```toml
[project.scripts]
klir = "klir.__main__:main"
```

**Step 4: Update build targets (already done by Task 2 sed, verify)**

```toml
[tool.hatch.build.targets.wheel]
packages = ["klir"]

[tool.hatch.build.targets.wheel.force-include]
"config.example.json" = "klir/_config_example.json"
"Dockerfile.sandbox" = "klir/_Dockerfile.sandbox"

[tool.hatch.build.targets.sdist]
include = [
    "klir/",
    "config.example.json",
    "Dockerfile.sandbox",
    "LICENSE",
    "README.md",
    "pyproject.toml",
]
```

**Step 5: Verify build works**

```bash
uv build
```

Expected: Creates `dist/klir-0.1.0.tar.gz` and `dist/klir-0.1.0-py3-none-any.whl`.

**Step 6: Commit**

```bash
git add pyproject.toml
git commit -m "build: Update metadata, author, and URLs for klir"
```

---

### Task 6: Update CI Workflow to Use uv

Replace `python -m build` + `pypa/gh-action-pypi-publish` with `uv build` + `uv publish`.

**Files:**
- Modify: `.github/workflows/publish.yml`

**Step 1: Rewrite the publish workflow**

```yaml
name: Publish to PyPI

on:
  push:
    tags:
      - "v*"

jobs:
  publish:
    name: Build and publish
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - name: Build package
        run: uv build
      - name: Publish to PyPI
        run: uv publish
        env:
          UV_PUBLISH_TOKEN: ${{ secrets.PYPI_TOKEN }}
```

**Step 2: Commit**

```bash
git add .github/workflows/publish.yml
git commit -m "ci: Switch to uv build and uv publish"
```

---

### Task 7: Update Documentation

Replace all `ductor` references in markdown files, GitHub templates, and project docs.

**Files:**
- Modify: `README.md`, `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`
- Modify: `docs/*.md`
- Modify: `.github/ISSUE_TEMPLATE/*.yml`
- Modify: `Dockerfile.sandbox`

**Step 1: Global replace in all markdown files**

```bash
find . -name '*.md' -not -path './.git/*' -not -path './docs/plans/*' -exec sed -i 's/ductor_bot/klir/g' {} +
find . -name '*.md' -not -path './.git/*' -not -path './docs/plans/*' -exec sed -i 's/DuctorPaths/KlirPaths/g' {} +
find . -name '*.md' -not -path './.git/*' -not -path './docs/plans/*' -exec sed -i 's/ductor_home/klir_home/g' {} +
find . -name '*.md' -not -path './.git/*' -not -path './docs/plans/*' -exec sed -i 's/DUCTOR_/KLIR_/g' {} +
find . -name '*.md' -not -path './.git/*' -not -path './docs/plans/*' -exec sed -i 's|~/\.ductor|~/.klir|g' {} +
find . -name '*.md' -not -path './.git/*' -not -path './docs/plans/*' -exec sed -i 's/ductor-sandbox/klir-sandbox/g' {} +
find . -name '*.md' -not -path './.git/*' -not -path './docs/plans/*' -exec sed -i 's/PleasePrompto\/ductor/js-krinay\/klir/g' {} +
find . -name '*.md' -not -path './.git/*' -not -path './docs/plans/*' -exec sed -i 's/ductor\.dev/klir.dev/g' {} +
find . -name '*.md' -not -path './.git/*' -not -path './docs/plans/*' -exec sed -i 's/\bductor\b/klir/g' {} +
```

**Step 2: Update GitHub issue templates**

```bash
find .github -name '*.yml' -exec sed -i 's/ductor/klir/g' {} +
find .github -name '*.yml' -exec sed -i 's/PleasePrompto/js-krinay/g' {} +
```

**Step 3: Update Dockerfile.sandbox comments**

```bash
sed -i 's/ductor/klir/g' Dockerfile.sandbox
```

**Step 4: Commit**

```bash
git add -A
git commit -m "docs: Update all documentation for klir rebrand"
```

---

### Task 8: Update Test Fixtures

The test conftest has `tmp_ductor_home` fixture that should be renamed.

**Files:**
- Modify: `tests/conftest.py`
- Modify: All test files referencing `tmp_ductor_home`

**Step 1: Rename fixture in conftest.py**

```bash
sed -i 's/tmp_ductor_home/tmp_klir_home/g' tests/conftest.py
sed -i 's/"\.ductor"/".klir"/g' tests/conftest.py
sed -i 's/~\/.ductor/~\/.klir/g' tests/conftest.py
```

**Step 2: Rename fixture references in all test files**

```bash
find tests -name '*.py' -exec sed -i 's/tmp_ductor_home/tmp_klir_home/g' {} +
```

**Step 3: Run full test suite**

```bash
uv run pytest --tb=short -q 2>&1 | tail -30
```

Expected: All tests pass.

**Step 4: Commit**

```bash
git add -A
git commit -m "test: Rename test fixtures for klir rebrand"
```

---

### Task 9: Run Full Quality Gate

Final verification that everything is clean.

**Files:**
- No modifications — verification only.

**Step 1: Run ruff format**

```bash
uv run ruff format .
```

**Step 2: Run ruff check**

```bash
uv run ruff check .
```

Expected: No errors (or only pre-existing ones).

**Step 3: Run mypy**

```bash
uv run mypy klir
```

Expected: No new errors.

**Step 4: Run full test suite**

```bash
uv run pytest -v 2>&1 | tail -40
```

Expected: All tests pass.

**Step 5: Verify build**

```bash
uv build
```

Expected: Builds `klir-0.1.0` wheel and sdist.

**Step 6: Verify no remaining ductor references (excluding plans, git, venv)**

```bash
rg -i 'ductor' --type py --type md --type yaml \
  --glob '!docs/plans/*' --glob '!.git/*' --glob '!.venv/*' \
  -l
```

Expected: No files (or only intentional references like credits in description).

**Step 7: Fix any remaining references and commit**

```bash
git add -A
git commit -m "chore: Final cleanup for klir rebrand"
```

---

### Task 10: Rename GitHub Repo and Publish

This is a manual + CLI step done after all code changes are committed.

**Step 1: Push all changes**

```bash
git push origin main
```

**Step 2: Rename GitHub repo**

```bash
gh repo rename klir
```

This renames `js-krinay/ductor` to `js-krinay/klir`. GitHub auto-redirects the old URL.

**Step 3: Update git remote**

```bash
git remote set-url origin git@github.com:js-krinay/klir.git
```

**Step 4: Tag and publish**

```bash
git tag v0.1.0
git push origin v0.1.0
```

This triggers the CI workflow to build and publish to PyPI.

**Step 5: Verify on PyPI**

Visit `https://pypi.org/project/klir/` and confirm the package is published.

**Step 6: Test install**

```bash
uv pip install klir
klir --version
```

Expected: Installs and runs successfully.
