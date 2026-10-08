from pathlib import Path

import pandas as pd
import pytest

from stopgo import rtklib
from conftest import POS_HEADER, pos_line


def test_navsys_mask() -> None:
    assert rtklib.navsys_mask("GEC") == 41
    assert rtklib.navsys_mask("gregc") == 45
    with pytest.raises(ValueError):
        rtklib.navsys_mask("GX")


def test_config_from_file_and_overrides(tmp_path: Path) -> None:
    f = tmp_path / "a.conf"
    f.write_text("# comment\npos1-elmask        =10  # (deg)\nfoo-bar=baz\n")
    cfg = rtklib.RtkConfig.from_file(f)
    assert cfg.options["pos1-elmask"] == "10"
    assert cfg.options["foo-bar"] == "baz"
    assert cfg.options["pos1-posmode"] == "static"  # default kept
    assert rtklib.RtkConfig.from_file(f, with_defaults=False).options.keys() == {"pos1-elmask", "foo-bar"}
    cfg2 = cfg.updated({"pos1-elmask": 20}).with_base_llh(46.0, 9.0, 2300.0)
    assert cfg.options["pos1-elmask"] == "10"  # immutable
    assert cfg2.options["pos1-elmask"] == "20"
    assert cfg2.has_base_position and not cfg.has_base_position
    assert "ant2-pos3          =2300.0000\n" in cfg2.to_text()


def test_build_command() -> None:
    t0, t1 = pd.Timestamp("2026-09-06 08:00:18"), pd.Timestamp("2026-09-06 08:02:17")
    cmd = rtklib.build_command(Path("c.conf"), Path("r.obs"), Path("b.obs"), [Path("n1"), Path("n2")],
                               Path("o.pos"), t0, t1)
    assert cmd == ["rnx2rtkp", "-k", "c.conf", "-ts", "2026/09/06", "08:00:18", "-te", "2026/09/06",
                   "08:02:17", "-o", "o.pos", "r.obs", "b.obs", "n1", "n2"]
    assert "-ts" not in rtklib.build_command(Path("c"), Path("r"), Path("b"), [], Path("o"))


def test_read_pos_sorted_concat(tmp_path: Path) -> None:
    a, b = tmp_path / "a.pos", tmp_path / "b.pos"
    a.write_text(POS_HEADER + pos_line("09:00:00", 46, 9, 100, 1))
    b.write_text(POS_HEADER + pos_line("08:00:00", 46, 9, 100, 2))
    df = rtklib.read_pos([a, b])
    assert list(df.Q) == [2, 1]
    assert df.t.iloc[0] == pd.Timestamp("2026-09-06 08:00:00")


def test_rinex_span(tmp_path: Path) -> None:
    f = tmp_path / "r.26O"
    f.write_text("     3.02  OBSERVATION DATA\n   END OF HEADER\n"
                 "> 2026 09 06 08 48 40.0000000  0 20\nG01 ...\n"
                 "> 2026 09 06 10 07 06.0000000  0 18\nG01 ...\n")
    assert rtklib.rinex_span(f) == (pd.Timestamp("2026-09-06 08:48:40"), pd.Timestamp("2026-09-06 10:07:06"))


def test_solve_static_returns_last_epoch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(rover, base, nav, config, out, start, end, exe):  # noqa: ANN001, ANN202
        out.write_text(POS_HEADER + pos_line("08:00:00", 46, 9, 1, 2) + pos_line("08:00:01", 46, 9, 2, 1))
        return out

    monkeypatch.setattr(rtklib, "run_rnx2rtkp", fake_run)
    sol = rtklib.solve_static(Path("r"), Path("b"), [], rtklib.RtkConfig(), pd.Timestamp(0), pd.Timestamp(1))
    assert sol.Q == 1 and sol.h == 2


def test_run_rnx2rtkp_raises_on_failure(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        rtklib.run_rnx2rtkp(Path("r"), Path("b"), [], rtklib.RtkConfig(), tmp_path / "o.pos", exe="false")
