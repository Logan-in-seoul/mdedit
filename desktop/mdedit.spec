# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — mdedit.app (macOS, 서명 없음, 개인용).

- backend/app 파이썬 모듈은 pathex/hiddenimports로 수집하고,
  프론트 빌드 산출물(backend/app/static)은 datas로 번들한다.
  frozen 상태에서 app.main의 `Path(__file__).parent / "static"`은
  sys._MEIPASS/app/static을 가리키므로 datas 대상 경로를 "app/static"으로 맞춘다.
- argv_emulation=True: 앱 미실행 상태에서 Finder .md 더블클릭 시 macOS가 보내는
  open-document Apple Event를 sys.argv로 변환한다.
  (실행 중 수신은 desktop/main.py의 application:openFile: 핸들러가 처리)
"""

from pathlib import Path

spec_dir = Path(SPECPATH).resolve()
repo_root = spec_dir.parent
backend_dir = repo_root / "backend"
static_dir = backend_dir / "app" / "static"

if not (static_dir / "index.html").is_file():
    raise SystemExit(
        "frontend build missing: run `npm --prefix frontend run build` first "
        "(desktop/build.sh가 자동으로 수행한다)"
    )

datas = [(str(static_dir), "app/static")]

hiddenimports = [
    # backend 패키지 (uvicorn 워커가 런타임에 끌어오는 경로 보강)
    "app",
    "app.main",
    "app.config",
    "app.fs",
    "app.schema",
    "app.index",
    "app.wikilinks",
    "app.graph",
    "app.blocks",
    # uvicorn이 동적으로 import하는 모듈들
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.loops.uvloop",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.protocols.websockets.wsproto_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
]

a = Analysis(
    [str(spec_dir / "main.py")],
    pathex=[str(backend_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest", "ruff"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="mdedit",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    argv_emulation=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="mdedit",
)

app = BUNDLE(
    coll,
    name="mdedit.app",
    icon=None,
    bundle_identifier="app.mdedit.desktop",
    info_plist={
        "CFBundleName": "mdedit",
        "CFBundleDisplayName": "mdedit",
        "CFBundleShortVersionString": "0.5.0",
        "CFBundleVersion": "0.5.0",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "12.0",
        # Finder에서 .md를 mdedit으로 열 수 있게 viewer로 등록
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "Markdown Document",
                "CFBundleTypeRole": "Viewer",
                "LSHandlerRank": "Alternate",
                "LSItemContentTypes": ["net.daringfireball.markdown"],
                "CFBundleTypeExtensions": ["md", "markdown"],
            }
        ],
        # net.daringfireball.markdown UTI가 선언 안 된 시스템 대비 import 선언
        "UTImportedTypeDeclarations": [
            {
                "UTTypeIdentifier": "net.daringfireball.markdown",
                "UTTypeDescription": "Markdown Document",
                "UTTypeConformsTo": ["public.plain-text"],
                "UTTypeTagSpecification": {
                    "public.filename-extension": ["md", "markdown"],
                    "public.mime-type": ["text/markdown"],
                },
            }
        ],
    },
)
