# Changelog

## [0.10.0] - 2026-06-25

### Changed
- **한글 검색** — 라인 인덱스 토크나이저를 `unicode61` → `trigram`으로 전환. `회의자료`를 `회의자`로 찾는 부분/중간 매치가 동작한다. trigram이 못 잡는 2글자 이하 토큰(예: 한글 `회의`)은 LIKE 부분 스캔으로 폴백, 스니펫 하이라이트는 양쪽 공통으로 계산. 기존 DB는 기동 시 자동 재생성·재인덱싱 (`_migrate_trigram`)
- **자동 산출물 제외** — 에이전트 세션 로그·메모리(`~/.claude/projects`)가 트리·검색에 섞이지 않도록 기본 exclude에 `projects` 추가 (`config.example.yaml`)

## [0.9.0] - 2026-06-14

### Added
- **콜아웃** — `> [!type] 제목` 블록을 색상 구분 박스로 렌더. 표준(note·tip·important·warning·caution) + 회의 자료용 커스텀(key·goal·say·ask·danger). 제목 생략 시 타입별 기본 라벨, 마커 없는 인용은 기존 blockquote 유지. 라이트/다크 양쪽 토큰 (`components/Callout.tsx`, `rehypeCallouts`)

## [0.8.0] - 2026-06-08

### Added
- **⌘K Quick Switcher** — 파일명/제목 퍼지 매치 + 본문 FTS 매치(스니펫·라인 점프), 빈 입력 시 최근 연 파일
- **최근 활동 피드(홈)** — 실행 시 오늘/어제/이번 주 변경 파일 그룹 뷰, 신규 배지(birthtime), "이어서 읽기" 카드. 브랜드 클릭으로 복귀 (`GET /api/activity`)
- **뒤로/앞으로** — ⌘[ ⌘] 문서 히스토리
- **읽던 위치·세션 복원** — 파일별 스크롤 위치 기억, 마지막 문서 이어서 읽기

### Changed
- **우측 패널 개요 중심 전환** — 개요(목차) 기본 표시(⌘⇧O 토글), 백링크 패널 제거 (백링크 API·그래프 inlink는 유지). 홈 화면에서는 개요 숨김

> 리서치 layer: Obsidian·Bear·Logseq·Marked 2 등 11개 제품 서베이 → 에이전트가 쓰고 사람이 읽는 vault 특성에 맞춰 선별 (docs/specs/v0.8.0.md)

## [0.7.0] - 2026-06-07

### Added
- **vault 밖 .md 임시 열기** — 글로벌 .md 핸들러 완성. roots 밖 파일도 더블클릭으로 열림 (`ext://` 등록제, 표시 전용·검색 비포함, Reader 안내 배지)
- **업데이트 체크** — 사이드바 하단 버전 표기 + 새 릴리스 배지 (`GET /api/update-check`, 1시간 캐시, 오프라인 무시)

## [0.6.0] - 2026-06-07

### Changed
- **디자인 업그레이드 "세련된 리더"**: CSS 디자인 토큰 시스템(:root) 도입, 라이트/다크 단일 소스
  - 본문 17px / 행간 1.78 / 측정폭 646px, 제목 위계·자간 정돈
  - 종이톤 배경 + 웜 블랙 텍스트, 차분한 액센트 블루
  - 사이드바 surface 분리, 선택 행 좌측 액센트 바
  - 인용·표·구분선·인라인 코드·frontmatter 카드 재설계
- Shiki 코드 하이라이트 듀얼 테마(github-light/github-dark) — 다크 모드 코드블록 가독성 수정
- 백링크·그래프 패널 스타일을 디자인 토큰으로 통합

## [0.5.0] - 2026-06-07

### Added
- **데스크톱 앱 (macOS)**: pywebview 네이티브 창 + PyInstaller `.app`/`.dmg` 빌드 (`desktop/build.sh`)
  - Finder에서 `.md` 파일을 mdedit으로 열기 (`POST /api/open` + Apple Event 핸들러)
  - 실행 중 서버 재사용, 단일 인스턴스 파일 열기
- **별표 고정**: 파일 별표 → 리스트 최상단 "★ 고정" 섹션 (`/api/starred` PUT/DELETE/GET, SQLite 영속)
- **검색 랭킹 점수 모델**: bm25 + 제목/파일명/경로 매치 부스트 + 최근 수정(7일/30일) 부스트, 파일 단위 그룹 정렬
- `files` 테이블 `title` 컬럼 (첫 H1, 구버전 DB 자동 마이그레이션)
- `MDEDIT_STATE_DIR` 환경변수로 인덱스 DB 위치 지정

### Changed
- **좌우 패널 독립 스크롤**: 문서를 스크롤해도 좌측 리스트가 고정된다 (100dvh 고정 그리드, 문서 전환 시 스크롤 리셋)
- 검색 랭킹을 프론트엔드 tier 후처리에서 백엔드 점수 모델로 일원화

### Removed
- `setup-remote.sh` (개인 부트스트랩 스크립트 — public 전환 정리)

## [0.1.0] - 2026-04-23

### Added
- FastAPI 백엔드(`/api/health`, `/api/config`, `/api/tree`, `/api/file`)
- Pydantic 기반 config 로더 (네 개 루트, 제외 패턴, 서버 설정)
- 마크다운 프런트매터 파서와 경로 traversal 방어
- React+Vite 프런트엔드 (Pretendard, 두 컬럼 레이아웃)
- FileTree 컴포넌트 (네 개 루트, 지연 로딩)
- Reader 컴포넌트 (GFM, 코드 하이라이트, Mermaid, KaTeX, 프런트매터 카드)
- systemd user service와 `install.sh` 부트스트랩 (systemd 미가용 시 nohup 폴백)
- Windows Chrome에서 `http://localhost:8787` 접속 지원
