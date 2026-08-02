#!/usr/bin/env bash
set -euo pipefail

show_usage() {
  printf '%s\n' \
    'Usage: run_luna_worker.sh [--effort low|medium|high|xhigh|max]' \
    '                          [--sandbox read-only|workspace-write]' \
    '                          [--workdir /absolute/repository/path]' \
    '' \
    'Read one bounded task packet from stdin and run it with GPT-5.6 Luna.'
}

worker_effort='max'
worker_sandbox='read-only'
worker_workdir="$PWD"

while (($# > 0)); do
  case "$1" in
    --effort)
      [[ $# -ge 2 ]] || { printf '%s\n' 'Missing value for --effort' >&2; exit 2; }
      worker_effort="$2"
      shift 2
      ;;
    --sandbox)
      [[ $# -ge 2 ]] || { printf '%s\n' 'Missing value for --sandbox' >&2; exit 2; }
      worker_sandbox="$2"
      shift 2
      ;;
    --workdir)
      [[ $# -ge 2 ]] || { printf '%s\n' 'Missing value for --workdir' >&2; exit 2; }
      worker_workdir="$2"
      shift 2
      ;;
    -h|--help)
      show_usage
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      show_usage >&2
      exit 2
      ;;
  esac
done

case "$worker_effort" in
  low|medium|high|xhigh|max) ;;
  *)
    printf 'Unsupported reasoning effort: %s\n' "$worker_effort" >&2
    exit 2
    ;;
esac

case "$worker_sandbox" in
  read-only|workspace-write) ;;
  *)
    printf 'Unsupported sandbox: %s\n' "$worker_sandbox" >&2
    exit 2
    ;;
esac

command -v codex >/dev/null 2>&1 || {
  printf '%s\n' 'Codex CLI is not available on PATH.' >&2
  exit 127
}

[[ -d "$worker_workdir" ]] || {
  printf 'Work directory does not exist: %s\n' "$worker_workdir" >&2
  exit 2
}

git -C "$worker_workdir" rev-parse --show-toplevel >/dev/null 2>&1 || {
  printf 'Work directory is not inside a Git repository: %s\n' "$worker_workdir" >&2
  exit 2
}

worker_task="$(</dev/stdin)"
[[ -n "${worker_task//[[:space:]]/}" ]] || {
  printf '%s\n' 'Task packet is empty. Pass it through stdin.' >&2
  exit 2
}

# 使用临时会话，避免把 Worker 的中间过程写入主任务；权限不足时直接失败并交回主 Agent。
exec codex -a never exec \
  --ephemeral \
  -m gpt-5.6-luna \
  -c "model_reasoning_effort=\"$worker_effort\"" \
  -s "$worker_sandbox" \
  -C "$worker_workdir" \
  "$worker_task"
