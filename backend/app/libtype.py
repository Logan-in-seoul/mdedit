"""자료함 유형 판정. frontmatter `type:` 이 없는 파일을 이름과 폴더로 대본·학습·조사에 넣는다.

2026-11-04 서버 열람 로그(파일 223종, 1,076회)로 백테스트해 정했다. 손으로 붙인 태그 63건 중
62건을 재현하고, 하네스 밖에서 연 횟수의 84%를 덮는다. 규칙을 넓히면 `guided`·`memory`·
`scorecard` 같은 낱말이 걸려 잡음이 늘어나므로, 고칠 때는 같은 로그로 다시 잰다.
"""
import re
EXCLUDE = re.compile(
  r'(^|/)(\.[^/]+|node_modules|archive|_archive|backups?|vendor|dist|build|memory|\.venv|sources|_?templates?|validation|records|data|state|out|output)(/|$)'
  r'|^code/'
  r'|/(README[^/]*|CHANGELOG|CLAUDE|AGENTS|SKILL|STATUS|MEMORY)\.md$'
  r'|\.(prev|bak|orig)\.md$|[-_.]v?\d*-?backup|[-_.]old\.md$|/task-\d+[^/]*$|/_harvest|녹취', re.I)
B = r'(^|[-_/⭐★ .])'
RULES = [
  ("대본", re.compile(r'대본|'+B+r'scr([-_.]|$)|(?<!tran)script|진행|runsheet|desk-card|예상질문|발언|talk|verbal|설득|메모(?!리)|memo(?!ry)|meeting-lead|retro-guide', re.I)),
  ("학습", re.compile(r'학습|이해|learning|처음부터|완전판|walkthrough|explainer|강의|교안|study', re.I)),
  ("조사", re.compile(r'research|리서치|조사|브리프|브리핑|(?<!de)brief|미팅.?준비|대면.?준비|상견례|prep|(?<!부재)대비', re.I)),
]
DIR_RULES = [("대본", re.compile(r'(^|/)1on1(/|$)|/upward/[^/]*-card\.md$')), ]
USE_PARENT = True  # 끄면 docs/scr/ 와 *-prep/ 안의 대본이 빠져 덮는 비율이 84%에서 81%로 준다
VERSION = re.compile(r'^(.*?)[-_ ]?(\d+)판\.md$')
def excluded(rel: str) -> bool:
    """하네스·사본·생성물 경로. frontmatter type 이 있어도 자료함에 넣지 않는다."""
    return bool(EXCLUDE.search('/' + rel))


def classify(rel: str) -> str | None:
    """rel: 루트 기준 상대 경로. 유형 이름이나 None."""
    if EXCLUDE.search('/'+rel): return None
    name = rel.rsplit('/',1)[-1]
    parent = rel.rsplit('/',2)[-2] if rel.count('/')>=1 else ''
    for t, rx in RULES:
        if rx.search(name): return t
    for t, rx in DIR_RULES:
        if rx.search(rel): return t
    if USE_PARENT:
        for t, rx in RULES:
            if rx.search(parent): return t
    return None
def keep_latest(paths):
    """같은 폴더 같은 이름의 N판은 가장 높은 판만 남긴다."""
    best = {}
    for p in paths:
        d, _, n = p.rpartition('/')
        m = VERSION.match(n)
        if not m: continue
        k = (d, m.group(1)); v = int(m.group(2))
        if k not in best or v > best[k][0]: best[k] = (v, p)
    keep = {p for _, p in best.values()}
    return [p for p in paths if not VERSION.match(p.rpartition('/')[2]) or p in keep]
