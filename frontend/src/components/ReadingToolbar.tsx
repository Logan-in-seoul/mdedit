// 읽기 모드 플로팅 툴바. 스타일은 global.css `.reading-toolbar`.
import { ReadingMode } from "../lib/useReadingMode";

const SCALE_STEP = 0.1;

export function ReadingToolbar({ mode }: { mode: ReadingMode }) {
  if (!mode.reading) return null;
  return (
    <div className="reading-toolbar" role="toolbar" aria-label="읽기 모드">
      <button onClick={() => mode.jumpBeat(-1)} title="이전 발언 (k)">
        ↑
      </button>
      <button onClick={() => mode.jumpBeat(1)} title="다음 발언 (j)">
        ↓
      </button>
      <button onClick={() => mode.bumpScale(-SCALE_STEP)} title="글자 작게 (-)">
        A−
      </button>
      <span className="reading-scale" title="0으로 초기화">
        {Math.round(mode.scale * 100)}%
      </span>
      <button onClick={() => mode.bumpScale(SCALE_STEP)} title="글자 크게 (+)">
        A+
      </button>
      <button onClick={() => window.print()} title="인쇄 / PDF">
        인쇄
      </button>
      <button className="reading-exit" onClick={mode.exit} title="종료 (Esc)">
        종료
      </button>
    </div>
  );
}
