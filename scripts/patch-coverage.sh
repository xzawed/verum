#!/usr/bin/env bash
# scripts/patch-coverage.sh
#
# Approximates Codecov patch coverage locally before pushing.
# Shows line coverage for each source file changed vs the base branch.
#
# Usage:
#   ./scripts/patch-coverage.sh              # compares against origin/main
#   ./scripts/patch-coverage.sh origin/dev   # compare against a different base
#
# Why this exists:
#   Codecov patch analysis uses "which diff lines are covered" — not the same as
#   overall project coverage. This script surfaces the same information locally
#   so you catch failures before pushing (not after 4 CI rounds).
#
# Requirements: pytest, python, pnpm/npx (jest)

set -euo pipefail

BASE=${1:-origin/main}
REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}=== Patch Coverage Check (base: $BASE) ===${NC}"
echo ""

# ── Collect changed source files ─────────────────────────────────────────────

PY_CHANGED=$(git diff "$BASE"...HEAD --name-only -- '*.py' \
  | grep -E '^(apps/api/src|packages/sdk-python/src)' \
  | grep -v '__pycache__' || true)

TS_CHANGED=$(git diff "$BASE"...HEAD --name-only -- '*.ts' \
  | grep -E '^(apps/dashboard/src|packages/sdk-typescript/src)' \
  | grep -v '\.test\.ts$' \
  | grep -v '__tests__' || true)

if [ -z "$PY_CHANGED" ] && [ -z "$TS_CHANGED" ]; then
  echo "No source files changed vs $BASE. Nothing to check."
  exit 0
fi

if [ -n "$PY_CHANGED" ]; then
  echo -e "${CYAN}Changed Python source files:${NC}"
  echo "$PY_CHANGED" | sed 's/^/  /'
fi
if [ -n "$TS_CHANGED" ]; then
  echo -e "${CYAN}Changed TypeScript source files:${NC}"
  echo "$TS_CHANGED" | sed 's/^/  /'
fi
echo ""

PASS=true

# ── Python coverage ───────────────────────────────────────────────────────────

if [ -n "$PY_CHANGED" ]; then
  echo -e "${CYAN}--- Python coverage ---${NC}"

  # Group by package
  API_FILES=$(echo "$PY_CHANGED" | grep '^apps/api/' || true)
  SDK_PY_FILES=$(echo "$PY_CHANGED" | grep '^packages/sdk-python/' || true)

  run_py_coverage() {
    local pkg_dir=$1
    local files=$2
    local label=$3

    if [ -z "$files" ]; then return; fi

    # Build --source args for just the changed files (strip leading path to src/)
    local cov_args=""
    while IFS= read -r f; do
      # Convert file path to module path for --cov
      local rel="${f#$pkg_dir/}"  # e.g. src/loop/analyze/prompts.py
      local mod_path="${rel%.py}" # e.g. src/loop/analyze/prompts
      cov_args="$cov_args --cov=${pkg_dir}/${rel%/*}"
    done <<< "$files"

    # Run pytest with coverage, capture term-missing output
    local output
    output=$(cd "$REPO_ROOT/$pkg_dir" && \
      python -m pytest --tb=no -q \
        --cov="${pkg_dir}/src" \
        --cov-report=term-missing:skip-covered \
        --no-header \
        2>/dev/null || true)

    echo -e "\n  ${label}:"
    # Filter to only show lines for changed files
    while IFS= read -r f; do
      local basename
      basename=$(basename "$f" .py)
      local line
      line=$(echo "$output" | grep -E "^\s*${basename}" | head -1 || true)
      if [ -n "$line" ]; then
        # Extract coverage percentage
        local pct
        pct=$(echo "$line" | grep -oE '[0-9]+%' | head -1 || echo "?%")
        local num
        num=${pct%\%}
        if [ "$num" -lt 90 ] 2>/dev/null; then
          echo -e "    ${RED}✗${NC} $f → ${RED}${pct}${NC}"
          PASS=false
        else
          echo -e "    ${GREEN}✓${NC} $f → ${GREEN}${pct}${NC}"
        fi
      else
        echo -e "    ${YELLOW}?${NC} $f → (not found in coverage report)"
      fi
    done <<< "$files"
  }

  [ -n "$API_FILES" ] && run_py_coverage "apps/api" "$API_FILES" "apps/api"
  [ -n "$SDK_PY_FILES" ] && run_py_coverage "packages/sdk-python" "$SDK_PY_FILES" "sdk-python"
fi

# ── TypeScript coverage ───────────────────────────────────────────────────────

if [ -n "$TS_CHANGED" ]; then
  echo ""
  echo -e "${CYAN}--- TypeScript coverage ---${NC}"

  SDK_TS_FILES=$(echo "$TS_CHANGED" | grep '^packages/sdk-typescript/' || true)
  DASH_FILES=$(echo "$TS_CHANGED" | grep '^apps/dashboard/' || true)

  run_ts_coverage() {
    local pkg_dir=$1
    local files=$2
    local label=$3

    if [ -z "$files" ]; then return; fi

    # Run jest with JSON reporter to parse coverage
    local json_output
    json_output=$(cd "$REPO_ROOT/$pkg_dir" && \
      npx jest --coverage --coverageReporters=json-summary --passWithNoTests \
        --silent 2>/dev/null || true)

    # Parse coverage-summary.json
    local summary_file="$REPO_ROOT/$pkg_dir/coverage/coverage-summary.json"

    echo -e "\n  ${label}:"
    while IFS= read -r f; do
      local abs_path="$REPO_ROOT/$f"
      if [ -f "$summary_file" ]; then
        # Extract line coverage for this file from the JSON summary
        local pct
        pct=$(python3 -c "
import json, sys
try:
    data = json.load(open('$summary_file'))
    # Try to find the file in the summary (path may vary)
    target = '$abs_path'.replace('\\\\', '/')
    for k, v in data.items():
        if k.replace('\\\\', '/').endswith(target.split('/')[-2] + '/' + target.split('/')[-1]):
            pct = v['lines']['pct']
            print(f'{pct:.0f}%')
            sys.exit(0)
    print('?%')
except Exception as e:
    print('?%')
" 2>/dev/null || echo "?%")
        local num="${pct%\%}"
        if [ "$num" = "?" ]; then
          echo -e "    ${YELLOW}?${NC} $f → (not in coverage report — may be untested)"
          PASS=false
        elif [ "$num" -lt 90 ] 2>/dev/null; then
          echo -e "    ${RED}✗${NC} $f → ${RED}${pct}${NC}"
          PASS=false
        else
          echo -e "    ${GREEN}✓${NC} $f → ${GREEN}${pct}${NC}"
        fi
      else
        echo -e "    ${YELLOW}?${NC} $f → (coverage report not found; run jest --coverage first)"
        PASS=false
      fi
    done <<< "$files"
  }

  [ -n "$SDK_TS_FILES" ] && run_ts_coverage "packages/sdk-typescript" "$SDK_TS_FILES" "sdk-typescript"
  [ -n "$DASH_FILES" ] && run_ts_coverage "apps/dashboard" "$DASH_FILES" "dashboard"
fi

# ── Summary ───────────────────────────────────────────────────────────────────

echo ""
if $PASS; then
  echo -e "${GREEN}=== All changed files have ≥90% line coverage. Safe to push. ===${NC}"
  exit 0
else
  echo -e "${RED}=== Some changed files have <90% coverage. Fix before pushing to avoid Codecov failure. ===${NC}"
  echo ""
  echo "  Tip: run 'make patch-coverage' again after adding tests."
  echo "  Reminder: adding test files without improving source coverage WORSENS patch%."
  exit 1
fi
