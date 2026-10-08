# 무인 작업 로그 (2026-W41)

브랜치: `unattended/2026-w41` · Logan 부재 기간 2026-10-03 ~ 10-10 (KST)

## 큐
- [x] 1. Pretendard 로컬 번들
- [x] 2. 읽기 시간 (words/characters/minutes, 메타데이터 엔드포인트, 에디터 헤더 표시)
- [x] 3. 정규식 검색 (`regex=true`, 안전한 시간 제한 스캔)
- [x] 4. 프런트엔드 테스트 하네스 (Vitest + RTL, `.github/workflows` 없음 → 워크플로 생성은 규칙상 금지이므로 보류 사유 기록)
- [x] 5. 섹션 접기
- [x] 6. 위키링크 호버 프리뷰
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

## 2026-10-05 (KST) — 항목 3
변경 파일
- `backend/app/index.py`: `compile_safe_regex()`(AST 검사로 위험 패턴 거부), `_search_regex()`(시간 예산 2초·라인 400자·파일당 5건·`limit` 상한), `search(..., regex=False)`
- `backend/app/main.py`: `/api/search`에 `regex` 쿼리 파라미터, `RegexSearchError` → HTTP 400
- `backend/tests/test_search_regex.py`: 신규(매치·필터·랭킹·한도·시간 초과·위험 패턴·API)
- `frontend/src/lib/api.ts`, `components/FlatList.tsx`, `styles/global.css`: `.*` 토글, 거부 시 안내 문구
- `CHANGELOG.md`

검증
- `pytest`: 210 passed, 1 skipped
- `ruff check app tests/test_search_regex.py`: 기존 `fs.py` F821 1건만(변경 무관)
- `npm run build`: 성공

Logan 확인 필요
- 안전 정책이 보수적입니다: `(foo|bar)+`처럼 반복 안의 `|`와 `a*b*c*d*`처럼 무한 반복 4개 이상은 거부합니다. 완화가 필요하면 알려 주세요.
- 파이썬 `re`는 매칭 도중 중단할 수 없어 시간 예산은 라인 단위로 확인합니다. 패턴 제한 + 라인 길이 제한으로 라인당 최악 비용을 묶었습니다.
- 정규식 모드는 대소문자 무시 고정입니다.

## 2026-10-06 (KST) — 항목 4
변경 파일
- `frontend/package.json`, `package-lock.json`: vitest 2, jsdom, @testing-library/react·dom·jest-dom·user-event 추가, `npm test` 스크립트
- `frontend/vitest.config.ts`, `src/test/setup.ts`: jsdom 환경, 테스트 후 cleanup
- `frontend/src/components/FlatList.test.tsx`: 신규 6건 (검색창은 별도 컴포넌트가 아니라 `FlatList` 안에 있어 함께 다룸 — 별표 고정 순서·해제·행 선택, 검색 호출·하이라이트, 정규식 토글·거부 문구)
- `CHANGELOG.md`

검증
- `npm test`: 6 passed
- `npx tsc -b`, `npm run build`: 성공

Logan 확인 필요
- `.github/workflows`가 없지만 규칙상 워크플로 파일은 만들지 않았습니다(pytest + 프런트 build/test CI는 보류). 필요하면 직접 추가하거나 허용해 주세요.
- 검색창과 별표 목록이 `FlatList` 한 컴포넌트라 테스트도 한 파일입니다.

## 2026-10-07 (KST) — 항목 5
변경 파일
- `frontend/src/lib/fold.ts`: `setupFolding()` — 헤딩에 토글 버튼 부착, 하위 헤딩 포함 숨김, 접힘 키(순번:제목)를 노트 경로별 localStorage에 저장·복원, 정리 함수 제공
- `frontend/src/components/Reader.tsx`: 렌더 완료 후 `setupFolding` 연결
- `frontend/src/styles/global.css`: 토글 스타일(호버/포커스 시 표시, 접힌 헤딩은 항상 표시)
- `frontend/src/lib/fold.test.ts`: 신규 3건 (접기·중첩, 저장/복원, 정리)
- `CHANGELOG.md`

검증
- `npm test`: 9 passed (기존 6 + 신규 3)
- `npx tsc -b`, `npm run build`: 성공

Logan 확인 필요
- 현재 앱에는 편집기(CodeMirror)가 없고 리더 뷰만 있어, "에디터 뷰"를 리더 본문으로 해석했습니다.
- 접힘 키에 헤딩 순번이 포함되어, 노트 앞부분에 헤딩이 추가/삭제되면 저장된 접힘 상태가 어긋날 수 있습니다(보수적 선택).
- 접힌 구간 안의 검색 결과 이동/앵커 이동은 자동으로 펼치지 않습니다.

## 2026-10-08 (KST) — 항목 6
변경 파일
- `frontend/src/lib/preview.ts`: `previewText()`(헤딩 마커·코드 펜스 제거, 6줄/320자 제한), `loadPreview()`(노트별 캐시, 실패 시 캐시 안 함)
- `frontend/src/lib/api.ts`: `api.peek()` — `mdedit:note-opened` 이벤트(그래프 패널 갱신)를 발생시키지 않는 파일 조회
- `frontend/src/components/WikiLink.tsx`: 호버/포커스 350ms 후 포털 팝오버 표시, 해결된 링크의 기본 `title` 툴팁은 제거(중복 방지)
- `frontend/src/styles/global.css`: `.wiki-preview`
- `frontend/src/lib/preview.test.ts`(3건), `frontend/src/components/WikiLink.test.tsx`(2건)
- `CHANGELOG.md`

검증
- `npm test`: 14 passed (기존 9 + 신규 5)
- `npx tsc -b`, `npm run build`: 성공
- 백엔드 변경 없음(pytest 미실행)

Logan 확인 필요
- 프리뷰는 원문 첫 줄들을 일반 텍스트로 보여 줍니다(마크다운 렌더 없음, XSS 표면 없음). 렌더된 프리뷰가 필요하면 알려 주세요.
- 터치 기기에는 호버가 없어 표시되지 않습니다.
