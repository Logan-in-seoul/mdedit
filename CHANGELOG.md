# Changelog

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
