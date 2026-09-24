import os
from pathlib import Path

# Pillow's Windows wheels include raqm (complex-script text shaping, needed for
# Telugu) but only enable it when fribidi-0.dll can be found at the moment its
# font engine first loads - which can happen early, since google-genai imports
# Pillow. So the vendored DLL goes on PATH here, before any agent module runs.
_VENDOR = Path(__file__).resolve().parent.parent / "vendor"
if _VENDOR.is_dir():
    os.environ["PATH"] = str(_VENDOR) + os.pathsep + os.environ.get("PATH", "")
