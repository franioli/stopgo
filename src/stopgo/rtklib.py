"""Thin wrapper around RTKLIB rnx2rtkp: configuration, execution and .pos parsing."""

from __future__ import annotations

import math
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

GPST_UTC_OFFSET_S = 18  # GPST - UTC leap seconds (valid since 2017)

POS_COLS = [
    "date",
    "time",
    "lat",
    "lon",
    "h",
    "Q",
    "ns",
    "sdn",
    "sde",
    "sdu",
    "sdne",
    "sdeu",
    "sdun",
    "age",
    "ratio",
]

NAVSYS_BITS = {"G": 1, "S": 2, "R": 4, "E": 8, "J": 16, "C": 32, "I": 64}

# Static, dual-frequency, short-baseline defaults (GPS+GAL+BDS, GLONASS AR off).
DEFAULT_OPTIONS: dict[str, str] = {
    "pos1-posmode": "static",
    "pos1-frequency": "l1+l2",
    "pos1-soltype": "forward",
    "pos1-elmask": "15",
    "pos1-snrmask_r": "off",
    "pos1-dynamics": "off",
    "pos1-ionoopt": "brdc",
    "pos1-tropopt": "saas",
    "pos1-sateph": "brdc",
    "pos1-navsys": "41",
    "pos2-armode": "continuous",
    "pos2-gloarmode": "off",
    "pos2-bdsarmode": "on",
    "pos2-arthres": "3",
    "pos2-arlockcnt": "0",
    "pos2-arelmask": "15",
    "out-solformat": "llh",
    "ant1-anttype": "",
    "ant2-anttype": "",
}


RTKLIB_URL = "https://github.com/rtklibexplorer/RTKLIB"


def install_hint() -> str:
    """How to install rnx2rtkp on the current platform."""
    if sys.platform == "win32":
        return (
            f"Download an RTKLIB release (demo5 recommended: {RTKLIB_URL}/releases), unzip it, and add "
            "the folder containing rnx2rtkp.exe to your PATH, or pass --exe C:\\path\\to\\rnx2rtkp.exe."
        )
    return (
        f"Build it from source (demo5 recommended):\n"
        f"  git clone {RTKLIB_URL}\n"
        "  cd RTKLIB/app/consapp/rnx2rtkp/gcc && make && sudo make install\n"
        "or copy the binary to a folder on your PATH. Debian/Ubuntu may also offer an older build "
        "(sudo apt install rtklib). Alternatively pass --exe /path/to/rnx2rtkp."
    )


def find_rnx2rtkp(exe: str = "rnx2rtkp") -> str:
    """Resolve the rnx2rtkp executable; raise FileNotFoundError with install hints if missing."""
    path = shutil.which(exe)
    if path is None:
        raise FileNotFoundError(f"'{exe}' not found on PATH. {install_hint()}")
    return path


def navsys_mask(systems: str) -> int:
    """RTKLIB navsys bitmask from system letters, e.g. 'GEC' -> 41."""
    try:
        return sum(NAVSYS_BITS[s] for s in set(systems.upper()))
    except KeyError as e:
        raise ValueError(
            f"unknown GNSS system {e}; use letters from {''.join(NAVSYS_BITS)}"
        ) from None


def utc_to_gpst(t: pd.Timestamp, leap_s: int = GPST_UTC_OFFSET_S) -> pd.Timestamp:
    return t + pd.Timedelta(seconds=leap_s)


@dataclass(frozen=True)
class RtkConfig:
    """Immutable set of rnx2rtkp options (keys as in RTKLIB .conf files)."""

    options: Mapping[str, str] = field(default_factory=lambda: dict(DEFAULT_OPTIONS))

    @classmethod
    def from_file(cls, path: Path, with_defaults: bool = True) -> RtkConfig:
        """Load an RTKLIB .conf file, optionally on top of DEFAULT_OPTIONS."""
        opts = dict(DEFAULT_OPTIONS) if with_defaults else {}
        for line in path.read_text().splitlines():
            line = line.split("#", 1)[0].strip()
            if "=" in line:
                key, value = line.split("=", 1)
                opts[key.strip()] = value.strip()
        return cls(opts)

    def updated(self, overrides: Mapping[str, object]) -> RtkConfig:
        return RtkConfig({**self.options, **{k: str(v) for k, v in overrides.items()}})

    def with_base_llh(self, lat: float, lon: float, h: float) -> RtkConfig:
        return self.updated({
            "ant2-postype": "llh",
            "ant2-pos1": f"{lat:.9f}",
            "ant2-pos2": f"{lon:.9f}",
            "ant2-pos3": f"{h:.4f}",
        })

    @property
    def has_base_position(self) -> bool:
        return all(k in self.options for k in ("ant2-pos1", "ant2-pos2", "ant2-pos3"))

    def to_text(self) -> str:
        return "".join(f"{k:<19}={v}\n" for k, v in self.options.items())

    def write(self, path: Path) -> Path:
        path.write_text(self.to_text())
        return path


def _fmt_time(t: pd.Timestamp) -> list[str]:
    return [t.strftime("%Y/%m/%d"), t.strftime("%H:%M:%S")]


def build_command(
    conf: Path,
    rover: Path,
    base: Path,
    nav: Sequence[Path],
    out: Path,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
    exe: str = "rnx2rtkp",
) -> list[str]:
    """rnx2rtkp command line; start/end are GPST."""
    cmd = [exe, "-k", str(conf)]
    if start is not None:
        cmd += ["-ts", *_fmt_time(start)]
    if end is not None:
        cmd += ["-te", *_fmt_time(end)]
    return cmd + ["-o", str(out), str(rover), str(base), *map(str, nav)]


def run_rnx2rtkp(
    rover: Path,
    base: Path,
    nav: Sequence[Path],
    config: RtkConfig,
    out: Path,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
    exe: str = "rnx2rtkp",
) -> Path:
    """Run rnx2rtkp and return the output .pos path."""
    exe = find_rnx2rtkp(exe)
    with tempfile.TemporaryDirectory() as tmp:
        conf = config.write(Path(tmp) / "rtk.conf")
        cmd = build_command(conf, rover, base, nav, out, start, end, exe)
        proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"rnx2rtkp failed ({proc.returncode}): {proc.stderr.strip()[-500:]}"
        )
    return out


def _pos_time_system(path: Path) -> str:
    """Time system ('GPST' or 'UTC') of a .pos file; raise if it is not a decimal-degree llh file."""
    with path.open() as f:
        for line in f:
            if not line.startswith("%"):
                break
            if "x-ecef" in line:
                raise ValueError(
                    f"{path}: ECEF .pos files are not supported, export lat/lon/height"
                )
            if "latitude(" in line:
                if "latitude(deg)" not in line:
                    raise ValueError(
                        f"{path}: latitude/longitude must be in decimal degrees"
                    )
                tsys = line.lstrip("% ").split()[0].upper()
                if tsys not in ("GPST", "UTC"):
                    raise ValueError(
                        f"{path}: unsupported time system {tsys}, use GPST or UTC"
                    )
                return tsys
    return "GPST"  # no column header: assume the RTKLIB default


def read_pos(
    paths: Path | str | Sequence[Path | str], leap_s: int = GPST_UTC_OFFSET_S
) -> pd.DataFrame:
    """Read one or more RTKLIB llh .pos files into a time-sorted DataFrame (column `t` in GPST).

    UTC files are shifted to GPST by `leap_s`; ECEF or non-degree files raise ValueError.
    """
    paths = (
        [Path(paths)] if isinstance(paths, (str, Path)) else [Path(p) for p in paths]
    )
    frames = []
    for p in paths:
        df = pd.read_csv(p, comment="%", sep=r"\s+", header=None, names=POS_COLS)
        df["t"] = pd.to_datetime(df.date + " " + df.time)
        if _pos_time_system(p) == "UTC":
            df["t"] = utc_to_gpst(df["t"], leap_s)
        frames.append(df)
    return pd.concat(frames, ignore_index=True).sort_values("t").reset_index(drop=True)


def solve_static(
    rover: Path,
    base: Path,
    nav: Sequence[Path],
    config: RtkConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
    exe: str = "rnx2rtkp",
) -> pd.Series | None:
    """Static solution over [start, end]: the last (cumulative) epoch of the forward filter."""
    with tempfile.TemporaryDirectory() as tmp:
        out = run_rnx2rtkp(
            rover, base, nav, config, Path(tmp) / "out.pos", start, end, exe
        )
        if not out.exists() or out.stat().st_size == 0:
            return None
        pos = read_pos(out)
    return pos.iloc[-1] if len(pos) else None


def rinex_span(obs: Path | str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """First and last epoch (GPST) of a RINEX 3 observation file.

    Event records without a timestamp are skipped; raises ValueError if no epoch is found.
    """
    first = last = None
    with Path(obs).open() as f:
        for line in f:
            if not line.startswith(">"):
                continue
            try:
                y, mo, d, h, mi, s = line[1:].split()[:6]
                last = pd.Timestamp(
                    int(y), int(mo), int(d), int(h), int(mi)
                ) + pd.Timedelta(seconds=float(s))
            except ValueError:
                continue
            if first is None:
                first = last
    if first is None or last is None:
        raise ValueError(f"no RINEX 3 epochs found in {obs}")
    return first, last


def header_llh(obs: Path | str) -> tuple[float, float, float]:
    """WGS84 lat, lon [deg] and ellipsoidal height [m] of the antenna from the RINEX header.

    Uses `APPROX POSITION XYZ` plus the vertical `ANTENNA: DELTA H/E/N`, if present.
    """
    xyz, dh = None, 0.0
    with Path(obs).open() as f:
        for line in f:
            if "APPROX POSITION XYZ" in line:
                xyz = tuple(map(float, line[:42].split()))
            elif "ANTENNA: DELTA H/E/N" in line:
                dh = float(line[:14])
            elif "END OF HEADER" in line:
                break
    if xyz is None or xyz == (0.0, 0.0, 0.0):
        raise ValueError(f"no valid APPROX POSITION XYZ in {obs}")
    x, y, z = xyz
    a, fl = 6378137.0, 1 / 298.257223563
    e2 = fl * (2 - fl)
    p = math.hypot(x, y)
    lat = math.atan2(z, p * (1 - e2))
    for _ in range(10):  # fixed-point iteration, converges to sub-mm in a few steps
        n = a / math.sqrt(1 - e2 * math.sin(lat) ** 2)
        h = p / math.cos(lat) - n
        lat = math.atan2(z, p * (1 - e2 * n / (n + h)))
    return math.degrees(lat), math.degrees(math.atan2(y, x)), h + dh
