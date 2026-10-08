## 요약
무인 주간(2026-W41) 자동 작업 PR입니다. 진행 상황은 `UNATTENDED-WORKLOG.md`를 참고해 주세요.

### 완료
- Pretendard 로컬 번들 (CDN 제거, 정적 파일 서빙 보완, 테스트 추가)
- 읽기 시간 (`/api/file`의 `reading` 필드, 리더 상단 표시, 테스트 추가)
- 정규식 검색 (`regex=true`, 안전한 시간 제한 스캔, `.*` 토글, 테스트 추가)
- 프런트엔드 테스트 하네스 (Vitest + RTL, `npm test`, FlatList 스모크 6건)
- 섹션 접기 (헤딩 토글, 노트별 상태 저장, 테스트 3건)
- 위키링크 호버 프리뷰 (첫 6줄 팝오버, 캐시, 테스트 5건)

### 남은 항목
최종 QA

### 확인 필요
- KaTeX CSS는 아직 CDN 사용
- `backend/app/fs.py:160` `FileEntry` 미정의(ruff F821)
- `.github/workflows`가 없으나 규칙상 CI 파일은 만들지 않음
