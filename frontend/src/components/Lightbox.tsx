import { useEffect, useState } from "react";

// 그림과 도식을 화면 가득 띄운다. 2,400px로 구운 도식이 본문 폭에 맞춰 줄면
// 글자가 작아져 안 읽히던 것을 원본 크기로 볼 수 있게 한다.

export type ZoomTarget =
  | { kind: "img"; src: string; caption?: string; plate?: boolean }
  | { kind: "svg"; html: string; caption?: string; plate?: boolean };

interface Props {
  target: ZoomTarget;
  onClose: () => void;
}

const STEPS = [1, 1.5, 2, 3, 4];

export function Lightbox({ target, onClose }: Props) {
  const [step, setStep] = useState(0);
  const scale = STEPS[step];

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        onClose();
      } else if (e.key === "+" || e.key === "=" || e.key === "-" || e.key === "0") {
        // 읽기 모드의 글자 크기 단축키와 겹치므로 여기서 멈춘다
        e.preventDefault();
        e.stopPropagation();
        if (e.key === "-") setStep((s) => Math.max(0, s - 1));
        else if (e.key === "0") setStep(0);
        else setStep((s) => Math.min(STEPS.length - 1, s + 1));
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [onClose]);

  const fit = scale === 1;
  const sized = fit ? undefined : { width: `${Math.round(92 * scale)}vw`, maxWidth: "none", maxHeight: "none" };

  return (
    <div className="lightbox" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="lightbox-bar" onClick={(e) => e.stopPropagation()}>
        <span className="lightbox-caption">{target.caption}</span>
        <button type="button" onClick={() => setStep((s) => Math.max(0, s - 1))} disabled={step === 0} aria-label="축소">
          −
        </button>
        <span className="lightbox-scale">{fit ? "맞춤" : `${Math.round(scale * 100)}%`}</span>
        <button
          type="button"
          onClick={() => setStep((s) => Math.min(STEPS.length - 1, s + 1))}
          disabled={step === STEPS.length - 1}
          aria-label="확대"
        >
          +
        </button>
        {target.kind === "img" && (
          <a className="lightbox-open" href={target.src} target="_blank" rel="noreferrer">
            새 탭
          </a>
        )}
        <button type="button" onClick={onClose} aria-label="닫기">
          닫기
        </button>
      </div>
      <div className={fit ? "lightbox-stage fit" : "lightbox-stage"}>
        <div
          className={target.plate ? "lightbox-item plate" : "lightbox-item"}
          style={sized}
          onClick={(e) => {
            e.stopPropagation();
            setStep((s) => (s === 0 ? 2 : 0));
          }}
        >
          {target.kind === "img" ? (
            <img src={target.src} alt={target.caption ?? ""} />
          ) : (
            <div className="lightbox-svg" dangerouslySetInnerHTML={{ __html: target.html }} />
          )}
        </div>
      </div>
    </div>
  );
}
