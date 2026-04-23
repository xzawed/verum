#!/usr/bin/env python3
"""
PostToolUse hook — 테스트 커버리지 알림 (비블로킹)

src/ 파일 수정 후 대응 테스트 파일 존재 여부를 확인하고 경고합니다.
항상 exit 0 — 작업을 블로킹하지 않습니다.
"""
import sys
import json
import os
import re
import subprocess


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = data.get("tool_name", "") or data.get("tool_use_name", "")
    tool_input = data.get("tool_input", {})
    file_path = (tool_input.get("file_path", "") or "").replace("\\", "/")

    # Edit/Write가 아니면 통과
    if tool_name not in ("Edit", "Write"):
        sys.exit(0)

    if not file_path:
        sys.exit(0)

    # Python 소스 파일 감지
    py_match = re.search(r"apps/api/src/(.+)\.py$", file_path)
    # TypeScript 소스 파일 감지 (테스트/선언 파일 제외)
    ts_match = re.search(r"apps/dashboard/src/(.+)\.tsx?$", file_path)

    if not py_match and not ts_match:
        sys.exit(0)

    # __init__.py, main.py 등 단순 진입점은 제외
    basename = os.path.basename(file_path)
    SKIP_FILES = {"__init__.py", "main.py", "conftest.py"}
    if basename in SKIP_FILES:
        sys.exit(0)

    # 테스트 파일인 경우 제외 (재귀 방지)
    if ".test." in file_path or "test_" in basename or ".spec." in file_path:
        sys.exit(0)

    if py_match:
        # apps/api/src/loop/infer/engine.py → apps/api/tests/loop/infer/test_engine.py
        relative = py_match.group(1)  # e.g. "loop/infer/engine"
        parts = relative.rsplit("/", 1)
        if len(parts) == 2:
            test_path = f"apps/api/tests/{parts[0]}/test_{parts[1]}.py"
        else:
            test_path = f"apps/api/tests/test_{parts[0]}.py"

        _check_and_run_python(file_path, test_path)

    elif ts_match:
        # apps/dashboard/src/lib/db/jobs.ts → apps/dashboard/src/lib/db/__tests__/jobs.test.ts
        # apps/dashboard/src/app/api/repos/[id]/status/route.ts → same dir __tests__/route.test.ts
        relative = ts_match.group(1)  # e.g. "lib/db/jobs" or "app/api/repos/[id]/status/route"
        parts = relative.rsplit("/", 1)
        if len(parts) == 2:
            dir_part, file_part = parts
            ext = "test.ts" if file_path.endswith(".ts") else "test.tsx"
            test_path = f"apps/dashboard/src/{dir_part}/__tests__/{file_part}.{ext}"
        else:
            test_path = f"apps/dashboard/src/__tests__/{relative}.test.ts"

        _check_and_run_ts(file_path, test_path)


def _check_and_run_python(src_path: str, test_path: str) -> None:
    if not os.path.exists(test_path):
        print(
            f"\n[test-orchestrator] No test found for {src_path}\n"
            f"  Expected: {test_path}\n"
            f"  Run test-orchestrator to backfill missing tests.\n",
            file=sys.stderr,
        )
        return

    print(f"\n[test-orchestrator] Running tests for {src_path}...", file=sys.stderr)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", test_path, "-x", "--tb=short", "-q"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=os.getcwd(),
        )
        if result.returncode != 0:
            # 실패해도 경고만 — exit 0 유지
            output = (result.stdout + result.stderr).strip()
            last_lines = "\n".join(output.splitlines()[-8:])
            print(
                f"\n[test-orchestrator] ⚠ Test failure detected:\n{last_lines}\n"
                f"  Fix before committing: {test_path}\n",
                file=sys.stderr,
            )
        else:
            lines = result.stdout.strip().splitlines()
            summary = lines[-1] if lines else "passed"
            print(f"[test-orchestrator] ✓ {summary}", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print(
            f"[test-orchestrator] ⚠ Test timed out (10s): {test_path}",
            file=sys.stderr,
        )
    except Exception as e:
        print(f"[test-orchestrator] ⚠ Could not run tests: {e}", file=sys.stderr)


def _check_and_run_ts(src_path: str, test_path: str) -> None:
    if not os.path.exists(test_path):
        print(
            f"\n[test-orchestrator] No test found for {src_path}\n"
            f"  Expected: {test_path}\n"
            f"  Run test-orchestrator to backfill missing tests.\n",
            file=sys.stderr,
        )
        return

    print(f"\n[test-orchestrator] Running tests for {src_path}...", file=sys.stderr)
    try:
        result = subprocess.run(
            ["npx", "jest", test_path, "--no-coverage", "--passWithNoTests"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd="apps/dashboard",
            shell=(sys.platform == "win32"),
        )
        if result.returncode != 0:
            output = (result.stdout + result.stderr).strip()
            last_lines = "\n".join(output.splitlines()[-8:])
            print(
                f"\n[test-orchestrator] ⚠ Test failure detected:\n{last_lines}\n"
                f"  Fix before committing: {test_path}\n",
                file=sys.stderr,
            )
        else:
            lines = result.stdout.strip().splitlines()
            summary = lines[-1] if lines else "passed"
            print(f"[test-orchestrator] ✓ {summary}", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print(
            f"[test-orchestrator] ⚠ Test timed out (30s): {test_path}",
            file=sys.stderr,
        )
    except Exception as e:
        print(f"[test-orchestrator] ⚠ Could not run tests: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
    sys.exit(0)
