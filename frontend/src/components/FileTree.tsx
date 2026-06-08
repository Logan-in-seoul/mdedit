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

// 모듈 레벨 캐시 (ISSUE-002): /api/tree는 vault 전체 FS 워크라 8~16초 걸린다.
// All↔Tree 토글마다 컴포넌트가 remount되며 재요청하던 것을 세션당 1회로 줄인다.
// 새 파일 반영은 페이지 새로고침 시점에 따라간다.
let treeCache: FileNode[] | null = null;
let treePromise: Promise<FileNode[]> | null = null;

function loadTree(): Promise<FileNode[]> {
  if (treeCache) return Promise.resolve(treeCache);
  if (!treePromise) {
    treePromise = api
      .tree()
      .then((t) => {
        treeCache = t;
        return t;
      })
      .catch((e) => {
        treePromise = null; // 실패 시 다음 mount에서 재시도
        throw e;
      });
  }
  return treePromise;
}

export function FileTree({ onSelect, selected }: Props) {
  const [tree, setTree] = useState<FileNode[] | null>(treeCache);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    loadTree()
      .then((t) => {
        if (alive) setTree(t);
      })
      .catch((e) => {
        if (alive) setError(String(e));
      });
    return () => {
      alive = false;
    };
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
