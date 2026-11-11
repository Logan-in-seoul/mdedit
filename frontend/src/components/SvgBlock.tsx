// ```svg 펜스를 그림으로 그린다. <img>의 data 주소로 넣어 SVG 안 스크립트는 돌지 않는다.
// 손으로 그린 도해를 문서 안에 바로 둘 때 쓴다. 다크 화면에서는 밝은 판 위에 놓인다.

interface Props {
  code: string;
}

export function svgDataUrl(code: string): string {
  let svg = code.trim();
  if (/^<svg[\s>]/i.test(svg) && !/xmlns=/.test(svg.slice(0, 400))) {
    svg = svg.replace(/^<svg/i, '<svg xmlns="http://www.w3.org/2000/svg"');
  }
  // 폭이 없으면 <img>가 칸 폭으로 늘려 글자가 커진다. viewBox 폭을 그린 크기로 쓴다.
  const open = svg.match(/^<svg[^>]*>/i)?.[0] ?? "";
  const vb = /viewBox\s*=\s*["']\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)/i.exec(open);
  if (vb && !/\swidth\s*=/.test(open)) {
    svg = svg.replace(/^<svg/i, `<svg width="${vb[1]}" height="${vb[2]}"`);
  }
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

export function SvgBlock({ code }: Props) {
  if (!/<svg[\s>]/i.test(code)) {
    return <pre className="mermaid-error">SVG 블록에 &lt;svg&gt; 요소가 없습니다.{"\n\n"}{code}</pre>;
  }
  return (
    <figure className="md-figure svg-block">
      <img className="md-img" src={svgDataUrl(code)} alt="" />
    </figure>
  );
}
