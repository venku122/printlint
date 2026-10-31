import sys

import pytest

from printlint.doctor import doctor


@pytest.mark.skipif(
    sys.platform != "darwin", reason="Full environment doctor requires native macOS slicers"
)
def test_doctor_environment():
    r = doctor()
    assert r["exit_code"] == 0
    assert r["environment"]["trimesh"]
    assert r["environment"]["slicers"]["bambu"]["available"]
