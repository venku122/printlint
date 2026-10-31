import os
import shutil

from printlint.compliance import compliance
from printlint.policy import ROOT
from printlint.report import new_report


def test_compliance_uses_node_from_path(tmp_path, monkeypatch):
    node = shutil.which("node")
    assert node
    marker = tmp_path / "node-used"
    wrapper = tmp_path / "node"
    wrapper.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\nexec "' + node + '" "$@"\n')
    wrapper.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path) + ":" + os.environ["PATH"])
    report = new_report()
    compliance(ROOT / "tests/fixtures/core-colored.3mf", report)
    assert marker.exists(), "Compliance ignored the Node executable on PATH"
    assert report["compliance"]["parseable"]
