# mdedit

Logan 전용 로컬 MD 워크스페이스. WSL Ubuntu 안에서 FastAPI가 마크다운 파일을 서빙하고, Windows 브라우저로 접속해 예쁘게 리뷰한다. Phase 1은 파일 트리 탐색과 리더 뷰를 제공한다.

## Phase 1 제공 범위

- 네 개 루트를 묶은 단일 파일 트리
- 마크다운 리더 뷰 (GFM, 코드 하이라이트, Mermaid, KaTeX, 프런트매터 카드, Pretendard 타이포)
- systemd user service 또는 nohup 기동
- Windows Chrome에서 `http://localhost:8787` 접속으로 즉시 사용

인덱싱·검색·위키 링크·편집·Claude 통합·Tauri 셸은 Phase 2 이후에 추가된다.

## 설치

```bash
git clone <repo-url> ~/workspace/mdedit
cd ~/workspace/mdedit
./install.sh
```

스크립트가 Python venv, 프런트엔드 빌드, 설정 파일 생성까지 수행한다. systemd user 버스가 활성화돼 있으면 `mdedit.service`를 등록해 자동 기동하고, 그렇지 않으면 nohup으로 백그라운드 기동한다. 설정 파일은 `~/.config/mdedit/config.yaml`에 생성되며 예제는 `config.example.yaml`에 있다.

WSL에서 systemd를 쓰고 싶다면 `/etc/wsl.conf`에 `[boot]\nsystemd=true`를 추가한 뒤 `wsl --shutdown`으로 재시작한다. 재시작 이후 다음 명령으로 서비스를 붙인다.

```bash
systemctl --user daemon-reload
systemctl --user enable --now mdedit
loginctl enable-linger $USER
```

## 사용

설치 이후 브라우저에서 `http://localhost:8787`을 연다. Chrome/Edge의 "앱 설치" 기능으로 PWA로 고정하면 단일 창처럼 쓸 수 있다.

## 수동 실행

서비스·nohup을 쓰지 않고 직접 띄우려면:

```bash
cd ~/workspace/mdedit/backend
source .venv/bin/activate
python -m app
```

## 데스크톱 앱 (macOS)

브라우저 대신 네이티브 창으로 쓰고 싶으면 `mdedit.app`을 빌드한다.

```bash
./desktop/build.sh
```

스크립트가 venv 생성, 의존성 설치(pywebview·PyInstaller·백엔드), 프런트엔드 빌드, PyInstaller 번들, `.dmg` 생성까지 수행한다. 산출물은 `desktop/dist/mdedit.app`과 `desktop/dist/mdedit.dmg`. dmg를 열어 `mdedit.app`을 Applications로 드래그하면 설치 끝이다 (서명 없음 — 첫 실행 시 우클릭 → 열기).

- Dock/Spotlight에서 실행하면 백엔드가 내장 스레드로 함께 뜨고, 창을 닫으면 같이 종료된다.
- `localhost:8787`에 서버가 이미 떠 있으면 두 번째 서버를 띄우지 않고 재사용한다. 브라우저 접속도 기존대로 동작한다.
- Finder에서 `.md` 파일을 "다음으로 열기 → mdedit"으로 열면 config roots와 대조해 해당 문서를 바로 연다. roots 밖 파일이면 열리지 않는다 (로그에 안내).
- 데스크톱 로그: `~/.local/state/mdedit/desktop.log`

## 개발 모드

프런트엔드 핫리로드가 필요하면 두 프로세스를 띄운다.

```bash
# 터미널 1 (백엔드)
cd ~/workspace/mdedit/backend && source .venv/bin/activate && python -m app --port 8787

# 터미널 2 (프런트엔드)
cd ~/workspace/mdedit/frontend && npm run dev
```

Vite dev 서버는 `/api`를 백엔드로 프록시한다.

## 문제 해결

- **응답이 없다 (systemd 사용 중)**: `journalctl --user -u mdedit -n 50`으로 로그를 본다.
- **응답이 없다 (nohup 사용 중)**: `~/.local/state/mdedit/mdedit.log`로 로그를 본다.
- **config 오류**: `~/.config/mdedit/config.yaml`의 루트 경로가 실제로 존재하는지 확인한다.
- **Pretendard가 안 뜬다**: 인터넷이 끊겨 CDN 접근이 안 될 때다. 프런트엔드 번들로 옮기는 작업은 Phase 2에서 다룬다.

## 파일 구조

`backend/`가 FastAPI 프로세스, `frontend/`가 Vite로 빌드되는 SPA. 빌드 산출물은 `backend/app/static/`에 복사돼 같은 프로세스가 서빙한다.

## 라이선스

개인 사용 전용.
