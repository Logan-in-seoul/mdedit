## 요약
무인 주간(2026-W41) 자동 작업 PR입니다. 진행 상황은 `UNATTENDED-WORKLOG.md`를 참고해 주세요.

### 완료
- Pretendard 로컬 번들 (CDN 제거, 정적 파일 서빙 보완, 테스트 추가)
- 읽기 시간 (`/api/file`의 `reading` 필드, 리더 상단 표시, 테스트 추가)

### 남은 항목
정규식 검색, 프런트엔드 테스트 하네스, 섹션 접기, 위키링크 호버 프리뷰, 최종 QA

### 확인 필요
- KaTeX CSS는 아직 CDN 사용
- `backend/app/fs.py:160` `FileEntry` 미정의(ruff F821)
