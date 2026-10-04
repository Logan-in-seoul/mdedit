# 무인 작업 로그 (2026-W41)

브랜치: `unattended/2026-w41` · Logan 부재 기간 2026-10-03 ~ 10-10 (KST)

## 큐
- [x] 1. Pretendard 로컬 번들
- [x] 2. 읽기 시간 (words/characters/minutes, 메타데이터 엔드포인트, 에디터 헤더 표시)
- [ ] 3. 정규식 검색 (`regex=true`, 안전한 시간 제한 스캔)
- [ ] 4. 프런트엔드 테스트 하네스 (Vitest + RTL, `.github/workflows` 없음 → 워크플로 생성은 규칙상 금지이므로 보류 사유 기록)
- [ ] 5. 섹션 접기
- [ ] 6. 위키링크 호버 프리뷰
- [ ] 7. 최종 QA

## 2026-10-03 (KST) — 항목 1
변경 파일
- `frontend/index.html`: Pretendard CDN 링크를 `/fonts/pretendard/pretendard.css`로 교체
- `frontend/public/fonts/pretendard/`: v1.3.9 가변 폰트 동적 서브셋(woff2 92개, 약 3MB), CSS(`font-family`를 `Pretendard`로 맞춤), README.txt
- `backend/app/main.py`: SPA fallback이 `/fonts/*` 등 정적 파일을 index.html로 덮어쓰던 문제 → `mount_static()`으로 분리, 실제 파일 우선 서빙 + 경로 이탈 차단
- `backend/tests/test_static_serving.py`: 신규 4건
- `README.md`, `CHANGELOG.md`(Unreleased)

검증
- `pytest`: 183 passed, 1 skipped
- `npm ci && npm run build`: 성공, 빌드된 `index.html`에 Pretendard CDN 참조 없음, TestClient로 woff2 200 확인
- `ruff check .`: 기존 4건(`fs.py` FileEntry 미정의, 테스트 미사용 import) — 이번 변경과 무관, 손대지 않음

Logan 확인 필요
- KaTeX CSS도 CDN(jsdelivr)을 사용합니다. 항목 범위 밖이라 그대로 두었습니다. 번들 전환이 필요하면 알려 주세요.
- `fs.py:160`의 `FileEntry` F821은 실제 런타임 버그일 수 있어 별도 확인이 필요합니다.

## 2026-10-04 (KST) — 항목 2
변경 파일
- `backend/app/schema.py`, `backend/app/fs.py`: `ReadingStats`, `compute_reading_stats()`, `FileContent.reading` 추가 (`/api/file` 응답에 신규 선택 필드)
- `backend/tests/test_fs_read.py`: 4건 추가 (영문, 한글, 코드 펜스 제외, read_file 통합)
- `frontend/src/lib/api.ts`, `components/Reader.tsx`, `styles/global.css`: 본문 상단에 "약 N분 · N자 · N단어" 표시
- `CHANGELOG.md`

검증
- `pytest`: 187 passed, 1 skipped
- `npm run build`: 성공

Logan 확인 필요
- 별도의 "메타데이터 엔드포인트"가 없어 `/api/file` 응답에 필드를 추가했습니다. 분리가 필요하면 알려 주세요.
- 속도 상수(CJK 500자/분, 영문 230단어/분)는 일반적인 값으로 정했습니다.
