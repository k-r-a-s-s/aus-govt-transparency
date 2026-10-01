import os
import subprocess
import sys
from pathlib import Path

import pytest

from disclosures.cli import ORDER, STUBS, main

REPO = Path(__file__).resolve().parent.parent
COMMANDS = ["scrape", "extract", "validate", "score", "load", "entities", "export", "refresh"]


def test_help_lists_exactly_the_subcommands():
    r = subprocess.run([sys.executable, "-m", "disclosures", "--help"], cwd=REPO,
                       capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(REPO)})
    assert r.returncode == 0
    assert "{" + ",".join(COMMANDS) + "}" in r.stdout
    assert ORDER == COMMANDS


@pytest.mark.parametrize("cmd", sorted(STUBS))
def test_stubs_exit_2_with_message(cmd, capsys):
    assert main([cmd]) == 2
    assert f"{cmd}: not implemented yet (Phase {STUBS[cmd]})" in capsys.readouterr().err
