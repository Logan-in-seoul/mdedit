from pathlib import Path

from pydantic import BaseModel, Field


class RootConfig(BaseModel):
    name: str
    path: Path


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8787


class AppConfig(BaseModel):
    roots: list[RootConfig]
    exclude: list[str] = Field(default_factory=list)
    respect_gitignore: bool = True
    server: ServerConfig = Field(default_factory=ServerConfig)


class FileNode(BaseModel):
    name: str
    path: str  # root_name://relative/path
    kind: str  # "file" | "dir"
    children: list["FileNode"] | None = None


class ReadingStats(BaseModel):
    words: int  # 비 CJK 단어 수
    characters: int  # CJK 글자 수 (공백 제외)
    minutes: int  # 예상 읽기 시간(분, 올림, 내용이 있으면 최소 1)


class FileContent(BaseModel):
    path: str
    title: str | None = None
    frontmatter: dict | None = None
    body: str
    mtime: int
    size: int
    reading: ReadingStats | None = None


FileNode.model_rebuild()


class FileEntry(BaseModel):
    path: str
    name: str
    mtime: int
    size: int
    title: str | None = None


class SearchHit(BaseModel):
    path: str
    name: str
    line: int
    snippet: str
    match_start: int
    match_end: int


class SearchResponse(BaseModel):
    query: str
    total: int
    truncated: bool
    hits: list[SearchHit]


class OpenRequest(BaseModel):
    abs_path: str


class TagEntry(BaseModel):
    tag: str
    count: int


class GraphNode(BaseModel):
    id: str
    label: str
    isCurrent: bool = False


class GraphEdge(BaseModel):
    source: str
    target: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class EmbedResponse(BaseModel):
    path: str
    title: str | None
    body: str


class BlockResponse(BaseModel):
    path: str
    block_id: str
    content: str
