#!/usr/bin/env bash
# mdedit.app + mdedit.dmg 빌드 (macOS, 서명 없음, 개인용)
#
# 사용: ./desktop/build.sh
# 산출물: desktop/dist/mdedit.app, desktop/dist/mdedit.dmg
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
VENV="$SCRIPT_DIR/.venv"
PYTHON="${PYTHON:-python3}"

# homebrew 파이썬의 pyexpat가 OS libexpat보다 새 심볼을 요구해 깨지는 환경 보정
# (Symbol not found: _XML_SetAllocTracker... → brew의 expat을 우선 로드)
if [[ "$(uname)" == "Darwin" && -d /opt/homebrew/opt/expat/lib ]]; then
  export DYLD_LIBRARY_PATH="/opt/homebrew/opt/expat/lib${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
fi

echo "==> python venv ($VENV)"
if [[ ! -x "$VENV/bin/python" ]]; then
  "$PYTHON" -m venv "$VENV"
fi
"$VENV/bin/pip" install -q --upgrade pip
# requirements.txt의 ../backend 상대 경로는 cwd 기준이므로 desktop/에서 실행
(cd "$SCRIPT_DIR" && "$VENV/bin/pip" install -q -r requirements.txt)

echo "==> frontend build → backend/app/static"
if [[ ! -d "$REPO_ROOT/frontend/node_modules" ]]; then
  npm --prefix "$REPO_ROOT/frontend" install --no-audit --no-fund
fi
npm --prefix "$REPO_ROOT/frontend" run build

echo "==> pyinstaller (mdedit.app)"
rm -rf "$SCRIPT_DIR/build" "$SCRIPT_DIR/dist/mdedit" "$SCRIPT_DIR/dist/mdedit.app"
"$VENV/bin/pyinstaller" --noconfirm --clean \
  --distpath "$SCRIPT_DIR/dist" \
  --workpath "$SCRIPT_DIR/build" \
  "$SCRIPT_DIR/mdedit.spec"

echo "==> dmg"
STAGING="$(mktemp -d)"
trap 'rm -rf "$STAGING"' EXIT
cp -R "$SCRIPT_DIR/dist/mdedit.app" "$STAGING/"
ln -s /Applications "$STAGING/Applications"
rm -f "$SCRIPT_DIR/dist/mdedit.dmg"
hdiutil create -volname mdedit -srcfolder "$STAGING" -ov -format UDZO \
  "$SCRIPT_DIR/dist/mdedit.dmg"

echo
echo "done:"
echo "  $SCRIPT_DIR/dist/mdedit.app"
echo "  $SCRIPT_DIR/dist/mdedit.dmg"
