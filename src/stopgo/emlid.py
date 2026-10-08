"""Read survey data from an Emlid Flow point export (CSV)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def _utc(s: pd.Series) -> pd.Series:
    """Parse 'YYYY-MM-DD hh:mm:ss.s UTC+02:00' into naive UTC."""
    t = pd.to_datetime(
        s.str.replace(" UTC", "", regex=False), format="ISO8601", utc=True
    )
    return t.dt.tz_localize(None)


def read_occupations(csv: Path) -> pd.DataFrame:
    """One row per point: UTC averaging window, sample count, antenna height, field solution."""
    df = pd.read_csv(csv, dtype={"Name": str}, keep_default_na=False, na_values=[""])
    if (df["Antenna height units"].dropna() != "m").any():
        raise ValueError("antenna height must be in metres")
    occ = pd.DataFrame({
        "name": df["Name"],
        "code": df["Code"].fillna(""),
        "t0_utc": _utc(df["Averaging start"]),
        "t1_utc": _utc(df["Averaging end"]),
        "n_logged": df["Samples"],
        "ant_h": df["Antenna height"],
        "field_lat": df["Latitude"],
        "field_lon": df["Longitude"],
        "field_h": df["Ellipsoidal height"],
    })
    return occ.sort_values("t0_utc").reset_index(drop=True)
