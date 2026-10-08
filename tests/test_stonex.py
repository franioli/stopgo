from pathlib import Path

import pandas as pd
import pytest

from stopgo import stonex


def test_read_occupations(pd_file: Path) -> None:
    occ = stonex.read_occupations(pd_file)
    assert list(occ["name"]) == ["P1", "P2"]  # sorted by time, deleted point dropped
    p1 = occ.iloc[0]
    assert p1.t0_utc == pd.Timestamp("2026-09-06 08:00:00")
    assert p1.t1_utc == pd.Timestamp("2026-09-06 08:00:02")
    assert p1.n_logged == 3 and p1.ant_h == pytest.approx(2.073)
    assert p1.field_h == 1000.0


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        stonex.read_points(tmp_path / "nope.PD")
