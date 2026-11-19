import json

from printlint import slicer


def setup_stock(tmp_path, monkeypatch):
    stock = "; X2D end\nM620 S65279 B\nT65279\nG150.1 F8000\nM621 S65279 B\nM620 S65535 B\nT65535\nG150.1 F8000\nM621 S65535 B\n"
    preset = tmp_path / "end.json"
    preset.write_text(json.dumps({"machine_end_gcode": stock}))
    monkeypatch.setattr(slicer, "X2D_END_PROFILE", preset)
    cfg = {"printer_model": "Bambu Lab X2D", "machine_end_gcode": stock}
    g = tmp_path / "plate_1.gcode"
    g.write_text("; FEATURE: Outer wall\nG1 X1 E1\n; pull back filament to AMS\n" + stock)
    return cfg, [g]


def test_exact_installed_x2d_end_sentinels_are_advisory(tmp_path, monkeypatch):
    cfg, gcodes = setup_stock(tmp_path, monkeypatch)
    for command in ["T65279", "T65535"]:
        assert slicer.is_stock_end_sentinel(f"[error] Invalid T command ({command}).", cfg, gcodes)


def test_other_errors_and_custom_gcode_still_block(tmp_path, monkeypatch):
    cfg, gcodes = setup_stock(tmp_path, monkeypatch)
    assert not slicer.is_stock_end_sentinel("[error] Invalid T command (T999).", cfg, gcodes)
    cfg["machine_end_gcode"] += "; custom\n"
    assert not slicer.is_stock_end_sentinel("[error] Invalid T command (T65535).", cfg, gcodes)


def test_duplicate_or_wrong_machine_sentinels_still_block(tmp_path, monkeypatch):
    cfg, gcodes = setup_stock(tmp_path, monkeypatch)
    gcodes[0].write_text("T65535\n" + gcodes[0].read_text())
    assert not slicer.is_stock_end_sentinel("[error] Invalid T command (T65535).", cfg, gcodes)
    cfg["printer_model"] = "Other printer"
    assert not slicer.is_stock_end_sentinel("[error] Invalid T command (T65279).", cfg, gcodes)
