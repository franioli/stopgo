from pathlib import Path

import pandas as pd
import pytest

from stopgo import processing, rtklib, stonex
from conftest import POS_HEADER, pos_line


@pytest.fixture
def windows(pd_file: Path) -> pd.DataFrame:
    return processing.occupation_windows(stonex.read_occupations(pd_file))


def test_occupation_windows_offset_and_trim(pd_file: Path) -> None:
    occ = stonex.read_occupations(pd_file)
    w = processing.occupation_windows(occ)
    assert w.start.iloc[0] == pd.Timestamp("2026-09-06 08:00:18")  # UTC + 18 s
    assert w.end.iloc[0] == pd.Timestamp("2026-09-06 08:00:20")
    assert processing.occupation_windows(occ, trim_s=1).empty  # windows of <=2 s collapse


def test_assign_rover() -> None:
    t = pd.Timestamp
    spans = {Path("a"): (t("2026-01-01 08:00"), t("2026-01-01 09:00")),
             Path("b"): (t("2026-01-01 10:00"), t("2026-01-01 11:00"))}
    assert processing.assign_rover(t("2026-01-01 10:10"), t("2026-01-01 10:12"), spans) == Path("b")
    assert processing.assign_rover(t("2026-01-01 08:59"), t("2026-01-01 09:01"), spans) is None


def test_extract_from_trajectory(tmp_path: Path, windows: pd.DataFrame) -> None:
    f = tmp_path / "t.pos"
    f.write_text(POS_HEADER + pos_line("08:00:18", 46.0, 9.0, 1002.0, 1) + pos_line("08:00:19", 46.0, 9.0, 1004.0, 1)
                 + pos_line("08:00:20", 46.0, 9.0, 1100.0, 2) + pos_line("09:00:30", 46.0, 9.0, 1.0, 1))
    res = processing.extract_from_trajectory(windows, rtklib.read_pos(f))
    p1 = res.set_index("name").loc["P1"]
    assert p1.n_epochs == 3 and p1.n_used == 2 and p1.h_ant == pytest.approx(1003.0)
    assert p1.fix_pct == pytest.approx(200 / 3)
    assert res.set_index("name").loc["P2"].n_epochs == 0
    all_q = processing.extract_from_trajectory(windows, rtklib.read_pos(f), fix_only=False)
    assert all_q.set_index("name").loc["P1"].n_used == 3


def test_add_ground_and_checks(windows: pd.DataFrame) -> None:
    res = pd.DataFrame({"name": ["P1"], "ant_h": [2.073], "lat": [46.0], "lon": [9.0], "h_ant": [1002.073]})
    out = processing.add_ground_and_checks(res, windows)
    assert out.h_ground.iloc[0] == pytest.approx(1000.0)
    assert out.dh_field.iloc[0] == pytest.approx(0.0)
    assert out.d2d_field.iloc[0] == pytest.approx(0.0)


def test_process_static(monkeypatch: pytest.MonkeyPatch, windows: pd.DataFrame) -> None:
    t = pd.Timestamp
    monkeypatch.setattr(rtklib, "rinex_span", lambda p: (t("2026-09-06 07:00"), t("2026-09-06 08:30")))
    sol = pd.Series({"Q": 1, "ratio": 30.0, "ns": 14, "lat": 46.0, "lon": 9.0, "h": 1002.0,
                     "sde": 0.001, "sdn": 0.001, "sdu": 0.002})
    monkeypatch.setattr(rtklib, "solve_static", lambda *a, **k: sol)
    res = processing.process_static(windows, [Path("rov.26O")], Path("b"), [], rtklib.RtkConfig())
    r = res.set_index("name")
    assert r.loc["P1"].fixed and r.loc["P1"].source == "rov.26O"
    assert pd.isna(r.loc["P2"].source)  # outside rover span
