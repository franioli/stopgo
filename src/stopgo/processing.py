"""Stop-and-go processing: occupation windows -> per-point coordinates.

Instrument-agnostic: `windows` is any DataFrame with columns
name, start, end (GPST), ant_h and optionally field_lat/field_lon/field_h.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from . import rtklib

EARTH_RADIUS_M = 6378137.0


def occupation_windows(
    occ: pd.DataFrame, trim_s: int = 0, leap_s: int = rtklib.GPST_UTC_OFFSET_S
) -> pd.DataFrame:
    """Add GPST `start`/`end` to UTC occupations, trimming `trim_s` at both ends."""
    w = occ.copy()
    w["start"] = rtklib.utc_to_gpst(w.t0_utc, leap_s) + pd.Timedelta(seconds=trim_s)
    w["end"] = rtklib.utc_to_gpst(w.t1_utc, leap_s) - pd.Timedelta(seconds=trim_s)
    ok = w.end > w.start  # also False for missing times
    if not ok.all():
        warnings.warn(
            f"{(~ok).sum()} window(s) dropped (empty after trimming or missing times): "
            + ", ".join(w.loc[~ok, "name"].astype(str)),
            stacklevel=2,
        )
    return w[ok].reset_index(drop=True)


def assign_rover(
    start: pd.Timestamp,
    end: pd.Timestamp,
    spans: dict[Path, tuple[pd.Timestamp, pd.Timestamp]],
) -> Path | None:
    """Rover file fully covering [start, end], if any."""
    return next(
        (p for p, (s, e) in spans.items() if s is not None and s <= start and e >= end),
        None,
    )


def _en_offsets(
    lat: np.ndarray, lon: np.ndarray, lat0: np.ndarray | float, lon0: np.ndarray | float
) -> tuple[np.ndarray, np.ndarray]:
    """East/North offsets in metres (small-area approximation)."""
    n = np.radians(lat - lat0) * EARTH_RADIUS_M
    e = np.radians(lon - lon0) * EARTH_RADIUS_M * np.cos(np.radians(lat0))
    return e, n


def _base_row(w: pd.Series) -> dict:
    return {"name": w["name"], "start": w.start, "end": w.end, "ant_h": w.ant_h}


def process_static(
    windows: pd.DataFrame,
    rovers: Sequence[Path],
    base: Path,
    nav: Sequence[Path],
    config: rtklib.RtkConfig,
    exe: str = "rnx2rtkp",
    progress: Callable[[str], None] | None = None,
) -> pd.DataFrame:
    """Static rnx2rtkp solution for each window."""
    spans = {r: rtklib.rinex_span(r) for r in rovers}
    rows = []
    for _, w in windows.iterrows():
        rover = assign_rover(w.start, w.end, spans)
        row = _base_row(w) | {"source": rover.name if rover else None}
        sol = (
            rtklib.solve_static(rover, base, nav, config, w.start, w.end, exe)
            if rover
            else None
        )
        if sol is not None:
            row |= {
                "Q": int(sol.Q),
                "fixed": bool(sol.Q == 1),
                "ratio": sol.ratio,
                "ns": int(sol.ns),
                "lat": sol.lat,
                "lon": sol.lon,
                "h_ant": sol.h,
                "sd_e": sol.sde,
                "sd_n": sol.sdn,
                "sd_u": sol.sdu,
            }
        if progress:
            progress(
                f"{w['name']}: "
                + (
                    f"Q={row['Q']} ratio={row['ratio']:.1f}"
                    if sol is not None
                    else "no rover data"
                    if rover is None
                    else "no solution"
                )
            )
        rows.append(row)
    return pd.DataFrame(rows)


def extract_from_trajectory(
    windows: pd.DataFrame, pos: pd.DataFrame, fix_only: bool = True
) -> pd.DataFrame:
    """Average kinematic .pos epochs falling in each window."""
    rows = []
    for _, w in windows.iterrows():
        seg = pos[(pos.t >= w.start) & (pos.t <= w.end)]
        n_all = len(seg)
        row = _base_row(w) | {
            "source": "trajectory",
            "n_epochs": n_all,
            "fix_pct": 100.0 * (seg.Q == 1).sum() / n_all if n_all else 0.0,
        }
        if fix_only:
            seg = seg[seg.Q == 1]
        row["n_used"] = len(seg)
        if len(seg):
            lat, lon = seg.lat.mean(), seg.lon.mean()
            e, n = _en_offsets(seg.lat.to_numpy(), seg.lon.to_numpy(), lat, lon)
            ddof = 1 if len(seg) > 1 else 0
            row |= {
                "fixed": bool((seg.Q == 1).all()),
                "lat": lat,
                "lon": lon,
                "h_ant": seg.h.mean(),
                "sd_e": e.std(ddof=ddof),
                "sd_n": n.std(ddof=ddof),
                "sd_u": seg.h.std(ddof=ddof),
            }
        rows.append(row)
    return pd.DataFrame(rows)


def add_ground_and_checks(res: pd.DataFrame, windows: pd.DataFrame) -> pd.DataFrame:
    """Ground height and differences w.r.t. the field solution (if available in `windows`)."""
    out = res.copy()
    if "h_ant" not in out:
        return out
    out["h_ground"] = out.h_ant - out.ant_h
    field_cols = ["field_lat", "field_lon", "field_h"]
    if set(field_cols) <= set(windows.columns):
        # a re-occupied point appears twice: pair the n-th result with the n-th window of that name
        out["_k"] = out.groupby("name").cumcount()
        fields = windows[["name", *field_cols]].assign(
            _k=windows.groupby("name").cumcount()
        )
        out = out.merge(fields, on=["name", "_k"], how="left").drop(columns="_k")
        e, n = _en_offsets(
            out.lat.to_numpy(),
            out.lon.to_numpy(),
            out.field_lat.to_numpy(),
            out.field_lon.to_numpy(),
        )
        out["d2d_field"] = np.hypot(e, n)
        out["dh_field"] = out.h_ground - out.field_h
        out = out.drop(columns=field_cols)
    return out
