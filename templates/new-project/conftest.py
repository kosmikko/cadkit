"""Put every project's ``cad/`` on ``sys.path``.

One folder per build, each holding its plan doc, its ``cad/`` sources and its
exported output. Module basenames are unique across the tree, so the flat
namespace holds and ``uv run pytest`` from here collects every project's suite
in one go.
"""

import sys
from pathlib import Path

for cad in sorted(Path(__file__).parent.glob("*/cad")):
    sys.path.insert(0, str(cad))
