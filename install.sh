#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${HOME}/.config/mdedit"
STATE_DIR="${HOME}/.local/state/mdedit"
SERVICE_DIR="${HOME}/.config/systemd/user"

echo "[1/5] Python venv 구성"
cd "${ROOT}/backend"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"

echo "[2/5] frontend 빌드"
cd "${ROOT}/frontend"
if [[ ! -d node_modules ]]; then
  npm install
fi
npm run build

echo "[3/5] 설정 디렉터리 준비"
mkdir -p "${CONFIG_DIR}" "${STATE_DIR}"
if [[ ! -f "${CONFIG_DIR}/config.yaml" ]]; then
  cp "${ROOT}/config.example.yaml" "${CONFIG_DIR}/config.yaml"
  echo "  config.yaml이 없으니 예제를 복사했다. 필요하면 ${CONFIG_DIR}/config.yaml을 편집하라."
fi

echo "[4/5] systemd user service 등록"
mkdir -p "${SERVICE_DIR}"
SERVICE_SRC="${ROOT}/mdedit.service"
SERVICE_DST="${SERVICE_DIR}/mdedit.service"
sed "s|@@ROOT@@|${ROOT}|g" "${SERVICE_SRC}" > "${SERVICE_DST}"

SYSTEMD_AVAILABLE=0
if systemctl --user daemon-reload >/dev/null 2>&1; then
  systemctl --user enable mdedit.service >/dev/null 2>&1
  systemctl --user restart mdedit.service
  SYSTEMD_AVAILABLE=1
  echo "  systemd user service 등록 완료"
else
  echo "  systemd user 버스를 찾지 못했다. WSL에 systemd가 꺼져 있을 수 있다."
  echo "  service 파일은 ${SERVICE_DST}에 복사했으니 systemd 활성화 후 다음을 실행하라:"
  echo "    systemctl --user daemon-reload && systemctl --user enable --now mdedit"
  echo "  지금은 nohup으로 백엔드를 백그라운드 기동한다."
  pkill -f "${ROOT}/backend/.venv/bin/python -m app" 2>/dev/null || true
  sleep 1
  nohup "${ROOT}/backend/.venv/bin/python" -m app \
    > "${STATE_DIR}/mdedit.log" 2>&1 &
  disown || true
fi

echo "[5/5] 헬스 체크"
sleep 2
if curl -sf http://127.0.0.1:8787/api/health >/dev/null; then
  echo "OK: http://127.0.0.1:8787"
else
  if [[ "${SYSTEMD_AVAILABLE}" -eq 1 ]]; then
    echo "WARN: 아직 응답이 없다. 'journalctl --user -u mdedit -n 50' 로 로그 확인하라."
  else
    echo "WARN: 아직 응답이 없다. '${STATE_DIR}/mdedit.log' 로그를 확인하라."
  fi
fi
