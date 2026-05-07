#!/usr/bin/env bash
# mdedit 일상 재기동 스크립트.
# 설치·빌드는 생략하고 백엔드만 켠다. 처음 설치하거나 코드·프런트엔드를 바꾼 뒤에는 install.sh를 쓴다.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_DIR="${HOME}/.local/state/mdedit"
mkdir -p "${STATE_DIR}"

BIN="${ROOT}/backend/.venv/bin/python"
if [[ ! -x "${BIN}" ]]; then
  echo "venv가 없습니다. ./install.sh를 먼저 실행하세요."
  exit 1
fi

# 기존 프로세스 정리
pkill -f "${BIN} -m app" 2>/dev/null || true
sleep 1

# nohup으로 백그라운드 기동
cd "${ROOT}/backend"
nohup "${BIN}" -m app > "${STATE_DIR}/mdedit.log" 2>&1 &
disown

sleep 2
if curl -sf http://127.0.0.1:8787/api/health >/dev/null; then
  echo "OK: http://localhost:8787 (Chrome에서 열면 됩니다)"
else
  echo "WARN: 응답이 없습니다. ${STATE_DIR}/mdedit.log 확인하세요."
fi
