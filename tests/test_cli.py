import os
import subprocess
import sys
from pathlib import Path

from disclosures.cli import ORDER

REPO = Path(__file__).resolve().parent.parent
COMMANDS = ["scrape", "extract", "validate", "score", "load", "entities", "export", "refresh",
            "web"]


def test_help_lists_exactly_the_subcommands():
    r = subprocess.run([sys.executable, "-m", "disclosures", "--help"], cwd=REPO,
                       capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(REPO)})
    assert r.returncode == 0
    assert "{" + ",".join(COMMANDS) + "}" in r.stdout
    assert ORDER == COMMANDS

