# Changelog

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
