import sqlite3
from pathlib import Path

import pytest

POS_HEADER = "% header\n%  GPST latitude(deg) ...\n"


def pos_line(t: str, lat: float, lon: float, h: float, q: int, ratio: float = 10.0) -> str:
    return (f"2026/09/06 {t}   {lat:.9f}  {lon:.9f}  {h:.4f}   {q}  15   0.0040   0.0030"
            f"   0.0090  -0.0010  -0.0010   0.0010   0.00  {ratio:.1f}\n")


@pytest.fixture
def pd_file(tmp_path: Path) -> Path:
    """Minimal Cube-a database: two points, 3 and 2 logged epochs."""
    f = tmp_path / "p.PD"
    con = sqlite3.connect(f)
    con.execute("CREATE TABLE Point (NAME, CODE, GPSID, Latitude, Longitude, Altitude, North, East,"
                " DeleteSign INTEGER DEFAULT 0)")
    con.execute("CREATE TABLE GPSBackup (ID, UTCDate, UTCTime, WGS84Latitude, WGS84Longitude,"
                " WGS84Altitude, Antenna_AntennaHeight, Pos_State)")
    con.executemany("INSERT INTO Point VALUES (?,?,?,?,?,?,?,?,?)", [
        ("P2", "", "id2", 46.1, 9.1, 2000.0, 0, 0, 0),
        ("P1", "", "id1", 46.0, 9.0, 1000.0, 0, 0, 0),
        ("DEL", "", "id3", 46.0, 9.0, 1000.0, 0, 0, 1),
    ])
    rows = [("id1", "2026-09-06", f"08:00:0{s}", 46.0, 9.0, 1002.0, 2.073, "SINGLE") for s in range(3)]
    rows += [("id2", "2026-09-06", f"09:00:0{s}", 46.1, 9.1, 2002.0, 2.073, "SINGLE") for s in range(2)]
    con.executemany("INSERT INTO GPSBackup VALUES (?,?,?,?,?,?,?,?)", rows)
    con.commit()
    con.close()
    return f
