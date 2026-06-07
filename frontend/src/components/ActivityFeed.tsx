import { useEffect, useState } from "react";
import { api, FileEntry } from "../lib/api";
import { getLastDoc } from "../lib/nav";

// 오늘의 변경 피드 (v0.8) — 문서 미선택 상태의 홈 화면.
// 에이전트가 vault에 쓴 파일을 날짜 그룹(오늘/어제/이번 주/그 이전)으로 보여준다.

interface Props {
  files: FileEntry[] | null;
  onSelect: (path: string) => void;
}

interface Entry {
  path: string;
  name: string;
  title: string | null;
  mtime: number;
  created_same_day: boolean;
}

function dayLabel(mtime: number, now: Date): string {
  const d = new Date(mtime * 1000);
  const startOfDay = (x: Date) =>
    new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diffDays = Math.floor((startOfDay(now) - startOfDay(d)) / 86400000);
  if (diffDays <= 0) return "오늘";
  if (diffDays === 1) return "어제";
  if (diffDays < 7) return "이번 주";
  return "그 이전";
}

function timeOf(mtime: number): string {
  const d = new Date(mtime * 1000);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function dirOf(path: string): string {
  return path.replace(/^[^:]+:\/\//, "").replace(/\/[^/]*$/, "");
}

export function ActivityFeed({ files, onSelect }: Props) {
  const [entries, setEntries] = useState<Entry[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    api
      .activity()
      .then((r) => setEntries(r.entries))
      .catch(() => setError(true));
  }, []);

  const lastDoc = getLastDoc();
  const lastEntry = lastDoc && files?.find((f) => f.path === lastDoc);

  if (error || (entries !== null && entries.length === 0 && !lastEntry)) {
    return <div className="placeholder">파일을 선택하세요</div>;
  }
  if (entries === null) return <div className="placeholder">로딩 중…</div>;

  const now = new Date();
  const groups: { label: string; items: Entry[] }[] = [];
  for (const e of entries) {
    const label = dayLabel(e.mtime, now);
    const g = groups[groups.length - 1];
    if (g && g.label === label) g.items.push(e);
    else groups.push({ label, items: [e] });
  }

  return (
    <div className="feed">
      <h2 className="feed-title">최근 활동</h2>

      {lastEntry && (
        <div className="feed-resume" onClick={() => onSelect(lastEntry.path)}>
          <span className="feed-resume-label">이어서 읽기</span>
          <span className="feed-resume-name">
            {lastEntry.title || lastEntry.name}
          </span>
          <span className="feed-resume-path">{dirOf(lastEntry.path)}</span>
        </div>
      )}

      {groups.map((g) => (
        <section key={g.label} className="feed-group">
          <h3 className="feed-group-label">{g.label}</h3>
          {g.items.map((e) => (
            <div
              key={e.path}
              className="feed-row"
              onClick={() => onSelect(e.path)}
              title={e.path}
            >
              <span className="feed-name">{e.title || e.name}</span>
              {e.created_same_day && <span className="feed-badge">신규</span>}
              <span className="feed-meta">
                {dirOf(e.path)} · {timeOf(e.mtime)}
              </span>
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}
