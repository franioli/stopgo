"""Read survey data from a Stonex Cube-a project database (Data/*.PD, SQLite)."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd


def _connect(pd_file: Path) -> sqlite3.Connection:
    if not pd_file.is_file():
        raise FileNotFoundError(pd_file)
    return sqlite3.connect(f"file:{pd_file}?mode=ro", uri=True)


def read_points(pd_file: Path) -> pd.DataFrame:
    """Surveyed points with the field (onboard) solution at ground level."""
    q = """SELECT NAME AS name, CODE AS code, GPSID AS gps_id,
                  Latitude AS field_lat, Longitude AS field_lon, Altitude AS field_h,
                  North AS north, East AS east
           FROM Point WHERE DeleteSign = 0"""
    with closing(_connect(pd_file)) as con:
        return pd.read_sql(q, con)


def read_epochs(pd_file: Path) -> pd.DataFrame:
    """All epochs logged during point occupations (antenna-level positions, UTC time)."""
    q = """SELECT ID AS gps_id, UTCDate, UTCTime,
                  WGS84Latitude AS lat, WGS84Longitude AS lon, WGS84Altitude AS h_ant,
                  Antenna_AntennaHeight AS ant_h, Pos_State AS solution
           FROM GPSBackup"""
    with closing(_connect(pd_file)) as con:
        ep = pd.read_sql(q, con)
    ep["t_utc"] = pd.to_datetime(ep.pop("UTCDate") + " " + ep.pop("UTCTime"))
    return ep


def read_occupations(pd_file: Path) -> pd.DataFrame:
    """One row per point: UTC occupation window, epoch count, antenna height, field solution."""
    win = (
        read_epochs(pd_file)
        .groupby("gps_id")
        .agg(
            t0_utc=("t_utc", "min"),
            t1_utc=("t_utc", "max"),
            n_logged=("t_utc", "size"),
            ant_h=("ant_h", "first"),
        )
    )
    occ = read_points(pd_file).merge(win, left_on="gps_id", right_index=True)
    return occ.sort_values("t0_utc").reset_index(drop=True)
