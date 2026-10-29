# PyInstaller spec for the BlockTrace desktop app. Run via build.ps1.
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [("web", "web")], [], []
for pkg in ("webview", "clr_loader", "pythonnet"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["blocktrace_desktop.py"],
    datas=datas,
    binaries=binaries,
    hiddenimports=hiddenimports + ["clr"],
    excludes=["tkinter", "unittest", "pydoc", "test"],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BlockTrace",
    icon="assets/BlockTrace.ico",
    version="version_info.txt",
    console=False,
    upx=False,
)

coll = COLLECT(exe, a.binaries, a.datas, name="BlockTrace", upx=False)
