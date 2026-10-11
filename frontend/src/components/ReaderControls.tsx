// 본문 우상단 보기 설정 (줄 너비·글자 크기·읽기 모드). 스타일은 global.css `.reader-controls`.
// 읽기 모드에서는 ReadingToolbar가 같은 일을 맡으므로 숨는다.
import { Measure } from "../lib/useMeasure";
import { ReadingMode } from "../lib/useReadingMode";

const SCALE_STEP = 0.1;

interface Props {
  mode: ReadingMode;
  measure: Measure;
}

export function ReaderControls({ mode, measure }: Props) {
  if (mode.reading) return null;
  const percent = Math.round(mode.scale * 100);
  return (
    <div className="reader-controls-anchor">
      <div className="reader-controls" role="toolbar" aria-label="보기 설정">
        <button onClick={measure.cycle} title="줄 너비 바꾸기 (좁게·보통·넓게·전체)">
          폭 {measure.label}
        </button>
        <button onClick={() => mode.bumpScale(-SCALE_STEP)} title="글자 작게">
          A−
        </button>
        {percent !== 100 && (
          <button onClick={mode.resetScale} title="글자 크기 초기화">
            {percent}%
          </button>
        )}
        <button onClick={() => mode.bumpScale(SCALE_STEP)} title="글자 크게">
          A+
        </button>
        <button onClick={mode.toggle} title="읽기 모드 (Ctrl/Cmd + .)">
          읽기
        </button>
      </div>
    </div>
  );
}
