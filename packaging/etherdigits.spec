# PyInstaller recipe: one file per platform with voices, web interface and pad tool inside.
#   pyinstaller packaging/etherdigits.spec
import os

from PyInstaller.utils.hooks import collect_submodules

root = os.path.dirname(SPECPATH)  # noqa: F821 - provided by PyInstaller

a = Analysis(  # noqa: F821
    [os.path.join(SPECPATH, "etherdigits_app.py")],  # noqa: F821
    pathex=[root],
    datas=[
        (os.path.join(root, "voices"), "voices"),
        (os.path.join(root, "web"), "web"),
        (os.path.join(root, "pad_tool.html"), "."),
        (os.path.join(root, "LICENSE"), "."),
        (os.path.join(root, "NOTICE.md"), "."),
    ],
    hiddenimports=collect_submodules("etherdigits"),
    excludes=["tkinter", "piper", "onnxruntime"],
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz, a.scripts, a.binaries, a.datas, [],
    name="etherdigits",
    console=True,  # the window shows the station's log; closing it stops the station
    upx=False,
)
