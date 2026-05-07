import { useEffect, useState } from "react";
import { api, FileNode } from "../lib/api";

interface Props {
  onSelect: (virtualPath: string) => void;
  selected: string | null;
}

function TreeNode({
  node,
  depth,
  onSelect,
  selected,
}: {
  node: FileNode;
  depth: number;
  onSelect: (p: string) => void;
  selected: string | null;
}) {
  const [open, setOpen] = useState(depth < 1);
  const isDir = node.kind === "dir";
  const isSelected = node.path === selected;

  return (
    <div>
      <div
        className={`tree-row ${isSelected ? "selected" : ""}`}
        style={{ paddingLeft: 8 + depth * 12 }}
        onClick={() => {
          if (isDir) {
            setOpen(!open);
          } else {
            onSelect(node.path);
          }
        }}
      >
        {isDir ? (open ? "▾" : "▸") : "·"} {node.name}
      </div>
      {isDir && open && node.children && (
        <div>
          {node.children.map((child) => (
            <TreeNode
              key={child.path}
              node={child}
              depth={depth + 1}
              onSelect={onSelect}
              selected={selected}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function FileTree({ onSelect, selected }: Props) {
  const [tree, setTree] = useState<FileNode[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .tree()
      .then(setTree)
      .catch((e) => setError(String(e)));
  }, []);

  if (error) return <div className="placeholder">트리 로드 실패: {error}</div>;
  if (!tree) return <div className="placeholder">로딩 중…</div>;

  return (
    <div className="tree">
      {tree.map((root) => (
        <TreeNode
          key={root.path}
          node={root}
          depth={0}
          onSelect={onSelect}
          selected={selected}
        />
      ))}
    </div>
  );
}
