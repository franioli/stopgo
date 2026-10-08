from pathlib import Path

import pandas as pd
import pytest

from stopgo import cli, emlid

CSV = """Name,Code,Antenna height,Antenna height units,Latitude,Longitude,Ellipsoidal height,Averaging start,Averaging end,Samples
1002,,1.934,m,46.1,9.1,2000.0,2025-09-14 12:02:14.2 UTC+02:00,2025-09-14 12:08:08.2 UTC+02:00,1770
1001,,1.934,m,46.0,9.0,1000.0,2025-09-14 11:37:15.4 UTC+02:00,2025-09-14 11:43:24.2 UTC+02:00,1815
"""


@pytest.fixture
def emlid_csv(tmp_path: Path) -> Path:
    f = tmp_path / "pts.csv"
    f.write_text(CSV)
    return f


def test_read_occupations(emlid_csv: Path) -> None:
    occ = emlid.read_occupations(emlid_csv)
    assert list(occ["name"]) == ["1001", "1002"]  # sorted by time
    p = occ.iloc[0]
    assert p.t0_utc == pd.Timestamp("2025-09-14 09:37:15.4")  # UTC+02:00 -> UTC
    assert p.n_logged == 1815 and p.ant_h == pytest.approx(1.934) and p.field_h == 1000.0


def test_windows_command_accepts_csv(emlid_csv: Path, tmp_path: Path) -> None:
    out = tmp_path / "w.csv"
    assert cli.main(["windows", str(emlid_csv), "-o", str(out)]) == 0
    w = pd.read_csv(out, parse_dates=["start"])
    assert w.start[0] == pd.Timestamp("2025-09-14 09:37:33.4")  # + 18 s leap


def test_unsupported_survey_file(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        cli.main(["windows", str(tmp_path / "x.txt")])
