import { useEffect, useRef, useState } from "react";

let counter = 0;

// lazy-load mermaid on first use to keep the main bundle lean
let _mermaidReady: Promise<typeof import("mermaid")["default"]> | null = null;
function getMermaid() {
  if (!_mermaidReady) {
    _mermaidReady = import("mermaid").then((m) => {
      m.default.initialize({ startOnLoad: false, theme: "default", securityLevel: "strict" });
      return m.default;
    });
  }
  return _mermaidReady;
}

interface Props {
  code: string;
}

export function MermaidBlock({ code }: Props) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const id = `mermaid-${++counter}`;
    getMermaid()
      .then((mermaid) => mermaid.render(id, code))
      .then(({ svg }) => {
        if (ref.current) ref.current.innerHTML = svg;
      })
      .catch((e) => setError(String(e)));
  }, [code]);

  if (error) {
    return (
      <pre className="mermaid-error">
        Mermaid 렌더 실패: {error}
        {"\n\n"}
        {code}
      </pre>
    );
  }

  return <div className="mermaid" ref={ref} />;
}
