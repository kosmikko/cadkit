"""Golden-PNG visual diff for a project folder's exported artifacts.

Scopes the agent's visual inspection to what a change actually altered:
keep a baseline render of every visual artifact (SVG sheets, PDF pages),
then after an edit report which artifacts/pages changed — only those need
to be looked at with vision. Full every-page inspection is still owed once
before a final "done" claim.

Run from inside a project folder (the one holding the plan doc and the
exported artifacts):

    uv run cadkit snapshot [name-filter ...]
    uv run cadkit diff     [name-filter ...]

`snapshot` renders every .svg and .pdf under the folder — including the ones
in svg/ — into .golden/ and records a content hash per artifact. `diff`
re-checks: artifacts whose file hash
matches the baseline are skipped without rendering; the rest are rendered
and compared pixel-for-pixel per page. Changed pages get the current
render plus a red-overlay diff written to .golden/_diff/ — read those PNGs,
not the whole package. Name filters are substrings of artifact filenames.

.golden/ is per-machine state and belongs in .gitignore. If `diff` reports
everything as NEW, snapshot a known-good state first.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pymupdf

EXPORT = Path(".")
GOLDEN = Path(".golden")
DIFF_DIR = GOLDEN / "_diff"
MANIFEST = GOLDEN / "manifest.json"
TARGET_PX = 1000  # long edge of rendered pages; keep stable or re-snapshot


def artifacts(export_dir: Path, filters: list[str]) -> list[Path]:
    """Every visual artifact under `export_dir`, at any depth.

    Recursive because a project folder sorts its output into subfolders
    (`svg/`, `step/`). Dot-directories are skipped so `.golden/` does not
    diff its own baseline renders. Filenames stay unique inside one project
    folder, so the manifest can keep keying on ``path.name``.
    """
    files = sorted(
        p
        for p in export_dir.rglob("*")
        if p.suffix.lower() in (".svg", ".pdf")
        and not any(part.startswith(".") for part in p.relative_to(export_dir).parts)
    )
    if filters:
        files = [p for p in files if any(f in p.name for f in filters)]
    return files


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_pages(path: Path, target: int = TARGET_PX) -> list[pymupdf.Pixmap]:
    doc = pymupdf.open(path)
    out = []
    for page in doc:
        zoom = target / max(page.rect.width, page.rect.height)
        out.append(page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False))
    return out


def diff_overlay(cur: pymupdf.Pixmap, gold: pymupdf.Pixmap) -> tuple[int, pymupdf.Pixmap]:
    """Count of differing pixels, and the current render with them in red."""
    n = cur.n  # bytes per pixel (RGB → 3)
    cs, gs = cur.samples, gold.samples
    out = bytearray(cs)
    changed = 0
    for i in range(0, len(cs), n):
        if cs[i : i + n] != gs[i : i + n]:
            changed += 1
            out[i : i + n] = b"\xff\x00\x00"[:n]
    return changed, pymupdf.Pixmap(cur.colorspace, cur.width, cur.height, bytes(out), False)


def load_manifest(golden_dir: Path) -> dict:
    manifest = golden_dir / "manifest.json"
    return json.loads(manifest.read_text()) if manifest.exists() else {}


def snapshot(export_dir: Path, golden_dir: Path, filters: list[str]) -> None:
    manifest = load_manifest(golden_dir)
    files = artifacts(export_dir, filters)
    for path in files:
        page_dir = golden_dir / path.name
        shutil.rmtree(page_dir, ignore_errors=True)
        page_dir.mkdir(parents=True)
        pixmaps = render_pages(path)
        for i, pm in enumerate(pixmaps, 1):
            pm.save(page_dir / f"page-{i}.png")
        manifest[path.name] = {"sha256": sha256(path), "pages": len(pixmaps)}
    if not filters:  # full snapshot: drop baselines for deleted artifacts
        gone = set(manifest) - {p.name for p in files}
        for name in sorted(gone):
            del manifest[name]
            shutil.rmtree(golden_dir / name, ignore_errors=True)
            print(f"dropped baseline (no longer exported): {name}")
    golden_dir.mkdir(parents=True, exist_ok=True)
    (golden_dir / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(f"baseline: {len(files)} artifact(s) snapshotted to {golden_dir}/")


def diff(export_dir: Path, golden_dir: Path, filters: list[str]) -> list[str]:
    """Compare export/ against the baseline; return report lines."""
    manifest = load_manifest(golden_dir)
    diff_dir = golden_dir / "_diff"
    shutil.rmtree(diff_dir, ignore_errors=True)
    report, unchanged = [], 0
    files = artifacts(export_dir, filters)
    for path in files:
        entry = manifest.get(path.name)
        if entry is None:
            out = diff_dir / path.name
            out.mkdir(parents=True)
            for i, pm in enumerate(render_pages(path), 1):
                pm.save(out / f"page-{i}.png")
            report.append(f"NEW (no baseline, look at all pages): {out}/")
            continue
        if entry["sha256"] == sha256(path):
            unchanged += 1
            continue
        cur = render_pages(path)
        gold_dir = golden_dir / path.name
        out = diff_dir / path.name
        out.mkdir(parents=True)
        if len(cur) != entry["pages"]:
            for i, pm in enumerate(cur, 1):
                pm.save(out / f"page-{i}.png")
            report.append(
                f"CHANGED {path.name}: page count {entry['pages']} -> {len(cur)}, "
                f"all pages at {out}/"
            )
            continue
        pages = []
        for i, pm in enumerate(cur, 1):
            gold = pymupdf.Pixmap(str(gold_dir / f"page-{i}.png"))
            if pm.irect != gold.irect:
                pm.save(out / f"page-{i}.png")
                pages.append(f"page {i} (resized)")
                continue
            n_diff, overlay = diff_overlay(pm, gold)
            if n_diff == 0:
                continue
            pm.save(out / f"page-{i}.png")
            overlay.save(out / f"page-{i}.diff.png")
            pages.append(f"page {i} ({n_diff} px differ)")
        if pages:
            report.append(f"CHANGED {path.name}: {', '.join(pages)} -> {out}/")
        else:  # bytes moved, pixels did not (e.g. reordered SVG elements)
            report.append(f"unchanged render (source bytes differ): {path.name}")
    present = {p.name for p in files}
    for name in sorted(set(manifest) - present):
        if not filters or any(f in name for f in filters):
            report.append(f"MISSING (baseline exists, not exported): {name}")
    report.append(f"{unchanged} artifact(s) unchanged")
    return report
