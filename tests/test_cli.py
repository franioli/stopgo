from pathlib import Path

import pandas as pd
import pytest

from stopgo import cli, rtklib


def test_windows_command(pd_file: Path, tmp_path: Path) -> None:
    out = tmp_path / "w.csv"
    assert cli.main(["windows", str(pd_file), "-o", str(out), "--points", "P2"]) == 0
    assert list(pd.read_csv(out)["name"]) == ["P2"]


def test_static_requires_base_position(pd_file: Path) -> None:
    with pytest.raises(SystemExit):
        cli.main(["static", str(pd_file), "--rover", "r", "--base", "b", "--nav", "n"])


def test_static_config_flags(pd_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rtklib, "rinex_span", lambda p: (None, None))
    conf = tmp_path / "eff.conf"
    cli.main(["static", str(pd_file), "--rover", "r", "--base", "b", "--nav", "n",
              "--base-pos", "46", "9", "2300", "--systems", "GE", "--elmask", "10",
              "--opt", "pos1-snrmask_r=on", "--save-conf", str(conf)])
    opts = rtklib.RtkConfig.from_file(conf, with_defaults=False).options
    assert opts["pos1-navsys"] == "9" and float(opts["pos1-elmask"]) == 10 and float(opts["pos2-arelmask"]) == 10
    assert opts["pos1-snrmask_r"] == "on" and opts["ant2-pos3"] == "2300.0000"
    assert opts["pos2-arthres"] == "3"  # default untouched
