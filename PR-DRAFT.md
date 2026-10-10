## 요약
무인 주간(2026-W41) 자동 작업 PR입니다. 진행 상황은 `UNATTENDED-WORKLOG.md`를 참고해 주세요.

### 완료
- Pretendard 로컬 번들 (CDN 제거, 정적 파일 서빙 보완, 테스트 추가)
- 읽기 시간 (`/api/file`의 `reading` 필드, 리더 상단 표시, 테스트 추가)
- 정규식 검색 (`regex=true`, 안전한 시간 제한 스캔, `.*` 토글, 테스트 추가)
- 프런트엔드 테스트 하네스 (Vitest + RTL, `npm test`, FlatList 스모크 6건)
- 섹션 접기 (헤딩 토글, 노트별 상태 저장, 테스트 3건)
- 위키링크 호버 프리뷰 (첫 6줄 팝오버, 캐시, 테스트 5건)

### 최종 QA
- pytest 210 passed, npm test 14 passed, 빌드 성공, ruff 신규 경고 없음

### 복귀 후 검수 수정 (2026-10-10)
- 정규식 검색 ReDoS 수정: 매칭을 별도 워커 프로세스로 옮기고 예산 초과 시 강제 종료 (`truncated_reason`)
- `limit` 1~1000 제한, SPA fallback 500 수정, Node 26에서 fold 테스트 실패 수정
- pytest 220 passed, npm test 14 passed (Node 22·26), ruff 신규 경고 없음

### 확인 필요
- 실제 `mdedit.app` 빌드에서 정규식 검색 시 창 중복 여부(워커 프로세스 + `freeze_support`)
- KaTeX CSS는 아직 CDN 사용
- `backend/app/fs.py:160` `FileEntry` 미정의(ruff F821)
- `.github/workflows`가 없으나 규칙상 CI 파일은 만들지 않음
