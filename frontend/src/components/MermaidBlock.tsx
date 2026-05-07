import { useEffect, useRef, useState } from "react";
import mermaid from "mermaid";

mermaid.initialize({ startOnLoad: false, theme: "default", securityLevel: "strict" });

let counter = 0;

interface Props {
  code: string;
}

export function MermaidBlock({ code }: Props) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const id = `mermaid-${++counter}`;
    mermaid
      .render(id, code)
      .then(({ svg }) => {
        if (ref.current) {
          ref.current.innerHTML = svg;
        }
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
