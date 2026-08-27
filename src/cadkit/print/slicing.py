"""Optional OrcaSlicer stage: slice an STL headlessly for time/filament stats.

Degrades gracefully when OrcaSlicer isn't installed (install:
`brew install --cask orcaslicer`).

NOTE: the CLI invocation below is UNVERIFIED — written from OrcaSlicer docs,
not tested against a real install (none was present when this was built).
On first use with Orca installed: run it, and if flags have drifted, fix
this file and remove this note. `--help` on the binary lists current flags.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ORCA_CANDIDATES = [
    "/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer",
    "/usr/bin/orca-slicer",  # Linux AppImage installs vary; adjust as needed
]


def find_slicer() -> str | None:
    for p in ORCA_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def slice_stl(stl_path, outdir, profile_args: list[str] | None = None) -> dict | None:
    """Slice to G-code and return {'time': str, 'filament_g': float} or None.

    profile_args: extra CLI args for machine/filament/process profiles —
    without them Orca uses its defaults, which is fine for estimates.
    """
    slicer = find_slicer()
    if slicer is None:
        return None
    stl = Path(stl_path)
    out = Path(outdir) / (stl.stem + ".gcode")
    cmd = [slicer, "--slice", "0", "--export-gcode", "--outputdir", str(outdir)]
    cmd += profile_args or []
    cmd.append(str(stl))
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if res.returncode != 0 or not out.exists():
        print(f"slicer failed for {stl.name}: {res.stderr.strip()[:500]}")
        return None
    return parse_gcode_stats(out)


def parse_gcode_stats(gcode_path) -> dict:
    stats = {}
    text = Path(gcode_path).read_text(errors="ignore")
    m = re.search(r";\s*(?:total estimated time|estimated printing time.*?)\s*[:=]\s*(.+)", text)
    if m:
        stats["time"] = m.group(1).strip()
    m = re.search(r";\s*(?:total )?filament used \[g\]\s*[:=]\s*([\d.]+)", text)
    if m:
        stats["filament_g"] = float(m.group(1))
    return stats
