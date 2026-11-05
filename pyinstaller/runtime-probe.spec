# Build an offline inference probe independently of the desktop shell.
from pathlib import Path

from scripts.runtime_assets import collect_phonon_assets

ROOT = Path(SPECPATH).parent
datas, binaries, hidden = collect_phonon_assets()
analysis = Analysis(
    [str(ROOT / "backend/verify_runtime.py")],
    pathex=[str(ROOT / "backend")],
    datas=datas,
    binaries=binaries,
    hiddenimports=hidden,
    module_collection_mode={"fermion": "pyz+py"},
    excludes=["tkinter", "matplotlib", "IPython"],
)
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name="SyllentraProbe", console=True)
collection = COLLECT(exe, analysis.binaries, analysis.datas, name="SyllentraProbe")
