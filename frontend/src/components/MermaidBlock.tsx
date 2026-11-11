import { useEffect, useRef, useState } from "react";
import { useColorScheme, type Scheme } from "../lib/scheme";

let counter = 0;

const FONT = '"Pretendard", -apple-system, "맑은 고딕", sans-serif';

// 다크에서 도식이 안 보이던 원인: theme "default"는 라이트 전용이라 선과 화살표(#333)가
// 검은 배경에 묻혔다. 화면 테마마다 대비를 맞춘 변수를 따로 준다.
// 배경 #15171a 기준 선 #c3cad5는 대비 11:1, 노드 글자 #f4f6f8 / 노드 바탕 #1e3354 는 12:1이다.
const DARK_VARS = {
  darkMode: true,
  background: "#15171a",
  fontFamily: FONT,
  fontSize: "15px",
  primaryColor: "#1e3354",
  primaryTextColor: "#f4f6f8",
  primaryBorderColor: "#7aa5f0",
  secondaryColor: "#2a2140",
  secondaryTextColor: "#f4f6f8",
  secondaryBorderColor: "#b487f0",
  tertiaryColor: "#1d2b24",
  tertiaryTextColor: "#f4f6f8",
  tertiaryBorderColor: "#4fc795",
  mainBkg: "#1e3354",
  nodeBorder: "#7aa5f0",
  nodeTextColor: "#f4f6f8",
  lineColor: "#c3cad5",
  textColor: "#e8eaed",
  titleColor: "#f4f6f8",
  labelColor: "#f4f6f8",
  clusterBkg: "#1b1f26",
  clusterBorder: "#5b6472",
  edgeLabelBackground: "#262a31",
  noteBkgColor: "#3a3010",
  noteTextColor: "#f4f6f8",
  noteBorderColor: "#e0b94d",
  actorBkg: "#1e3354",
  actorBorder: "#7aa5f0",
  actorTextColor: "#f4f6f8",
  actorLineColor: "#8a93a1",
  signalColor: "#c3cad5",
  signalTextColor: "#e8eaed",
  labelBoxBkgColor: "#1e3354",
  labelBoxBorderColor: "#7aa5f0",
  labelTextColor: "#f4f6f8",
  loopTextColor: "#e8eaed",
  activationBkgColor: "#2a3a55",
  activationBorderColor: "#7aa5f0",
  sequenceNumberColor: "#15171a",
  sectionBkgColor: "#1c2330",
  altSectionBkgColor: "#15171a",
  sectionBkgColor2: "#232a36",
  taskBkgColor: "#2e66d0",
  taskBorderColor: "#7aa5f0",
  taskTextColor: "#ffffff",
  taskTextLightColor: "#ffffff",
  taskTextOutsideColor: "#e8eaed",
  taskTextDarkColor: "#f4f6f8",
  activeTaskBkgColor: "#2f9e6e",
  activeTaskBorderColor: "#4fc795",
  doneTaskBkgColor: "#4b5563",
  doneTaskBorderColor: "#8a93a1",
  critBkgColor: "#c0392b",
  critBorderColor: "#e0685c",
  todayLineColor: "#e0b94d",
  gridColor: "#3a3f47",
  pieStrokeColor: "#15171a",
  pieOuterStrokeColor: "#8a93a1",
  pieSectionTextColor: "#ffffff",
  pieTitleTextColor: "#f4f6f8",
  pieLegendTextColor: "#e8eaed",
  attributeBackgroundColorOdd: "#1c1f24",
  attributeBackgroundColorEven: "#23272e",
};

const LIGHT_VARS = {
  darkMode: false,
  background: "#ffffff",
  fontFamily: FONT,
  fontSize: "15px",
  primaryColor: "#e8f0fc",
  primaryTextColor: "#121417",
  primaryBorderColor: "#2e66d0",
  secondaryColor: "#f1eafc",
  secondaryTextColor: "#121417",
  secondaryBorderColor: "#8a5cd6",
  tertiaryColor: "#e9f6ef",
  tertiaryTextColor: "#121417",
  tertiaryBorderColor: "#2f9e6e",
  lineColor: "#4b5563",
  textColor: "#1c1e21",
  titleColor: "#121417",
  clusterBkg: "#f7f7f5",
  clusterBorder: "#c9cbd0",
  edgeLabelBackground: "#ffffff",
  noteBkgColor: "#fff6d9",
  noteTextColor: "#1c1e21",
  noteBorderColor: "#d8b64a",
  actorBkg: "#e8f0fc",
  actorBorder: "#2e66d0",
  actorTextColor: "#121417",
  signalColor: "#4b5563",
  signalTextColor: "#1c1e21",
};

/** 작성자가 `%%{init}%%`나 frontmatter config로 색을 정했으면 라이트 기준 색이라 본다. */
export function hasAuthoredTheme(code: string): boolean {
  return /%%\{\s*init/i.test(code) || /^---[\s\S]*?\n\s*config\s*:/m.test(code);
}

type Mermaid = (typeof import("mermaid"))["default"];
let _mermaid: Promise<Mermaid> | null = null;
function loadMermaid(): Promise<Mermaid> {
  if (!_mermaid) _mermaid = import("mermaid").then((m) => m.default);
  return _mermaid;
}

// initialize가 전역 설정이라 렌더를 한 줄로 세워 테마가 섞이지 않게 한다.
let queue: Promise<unknown> = Promise.resolve();
function renderWith(scheme: Scheme, id: string, code: string): Promise<string> {
  const job = queue.then(async () => {
    const mermaid = await loadMermaid();
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: "base",
      themeVariables: scheme === "dark" ? DARK_VARS : LIGHT_VARS,
      fontFamily: FONT,
      flowchart: { htmlLabels: true, useMaxWidth: true, padding: 14, nodeSpacing: 46, rankSpacing: 52 },
      sequence: { useMaxWidth: true, mirrorActors: false },
      gantt: { useMaxWidth: true },
    });
    const { svg } = await mermaid.render(id, code);
    return svg;
  });
  queue = job.catch(() => {});
  return job;
}

interface Props {
  code: string;
}

export function MermaidBlock({ code }: Props) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [error, setError] = useState<string | null>(null);
  const screen = useColorScheme();
  const authored = hasAuthoredTheme(code);
  // 작성자 색은 라이트 바탕을 전제로 하므로 다크 화면에서도 밝은 판 위에 라이트로 그린다
  const scheme: Scheme = authored ? "light" : screen;

  useEffect(() => {
    let cancelled = false;
    const id = `mermaid-${++counter}`;
    setError(null);
    renderWith(scheme, id, code)
      .then((svg) => {
        if (!cancelled && ref.current) ref.current.innerHTML = svg;
      })
      .catch((e) => {
        if (!cancelled) setError(String(e?.message ?? e));
        // mermaid가 실패하면 body에 남기는 임시 노드를 치운다
        document.getElementById(`d${id}`)?.remove();
      });
    return () => {
      cancelled = true;
    };
  }, [code, scheme]);

  if (error) {
    return (
      <pre className="mermaid-error">
        Mermaid 렌더 실패: {error}
        {"\n\n"}
        {code}
      </pre>
    );
  }

  return (
    <div
      className={authored ? "mermaid mermaid-authored zoomable" : "mermaid zoomable"}
      ref={ref}
      title="눌러서 크게 보기"
    />
  );
}
