from pathlib import Path
import sys

from scripts.runtime_assets import collect_phonon_assets

ROOT = Path(SPECPATH).parent
APP_NAME = "Syllentra"
icon = Path(SPECPATH) / ("logo.icns" if sys.platform == "darwin" else "logo.ico")

# The fixed speech runtime loads vendor source and native assets dynamically.
phonon_data, phonon_binaries, phonon_hidden = collect_phonon_assets()
datas = [(str(ROOT / "frontend_dist"), "frontend_dist"), *phonon_data]

analysis = Analysis(
    [str(ROOT / "backend/main.py")],
    pathex=[str(ROOT / "backend")],
    datas=datas,
    binaries=phonon_binaries,
    hiddenimports=phonon_hidden,
    module_collection_mode={"fermion": "pyz+py"},
    excludes=["tkinter", "matplotlib", "IPython"],
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,
    icon=str(icon) if icon.exists() else None,
    argv_emulation=False,
)
collection = COLLECT(exe, analysis.binaries, analysis.datas, name=APP_NAME)

if sys.platform == "darwin":
    app = BUNDLE(
        collection,
        name=f"{APP_NAME}.app",
        # Set the final release identity when configuring signing and notarization.
        bundle_identifier="com.jolacdev.syllentra",
        icon=str(icon) if icon.exists() else None,
    )
