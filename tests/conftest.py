"""The scripts are not a package: put scripts/ on sys.path once for every test (CLAUDE.md「コマンド」)."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
