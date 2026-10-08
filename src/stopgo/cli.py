"""Command-line interface: `stopgo {windows,static,extract}`."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from . import __version__, emlid, processing, rtklib, stonex

SUMMARY_COLS = [
    "name",
    "source",
    "Q",
    "fixed",
    "ratio",
    "ns",
    "fix_pct",
    "n_used",
    "lat",
    "lon",
    "h_ant",
    "ant_h",
    "h_ground",
    "sd_e",
    "sd_n",
    "sd_u",
    "d2d_field",
    "dh_field",
]
FORMATS = {
    "lat": "{:.9f}",
    "lon": "{:.9f}",
    "h_ant": "{:.4f}",
    "h_ground": "{:.4f}",
    "ant_h": "{:.3f}",
    "ratio": "{:.1f}",
    "fix_pct": "{:.0f}",
    "sd_e": "{:.4f}",
    "sd_n": "{:.4f}",
    "sd_u": "{:.4f}",
    "d2d_field": "{:.3f}",
    "dh_field": "{:.3f}",
}


def _key_value(s: str) -> tuple[str, str]:
    if "=" not in s:
        raise argparse.ArgumentTypeError(f"expected key=value, got {s!r}")
    k, v = s.split("=", 1)
    return k.strip(), v.strip()


def _print_table(df: pd.DataFrame) -> None:
    cols = [c for c in SUMMARY_COLS if c in df]
    fmt = {
        c: (lambda f: lambda x: "" if pd.isna(x) else f.format(x))(f)
        for c, f in FORMATS.items()
        if c in cols
    }
    print(df[cols].to_string(index=False, formatters=fmt))


def _save(df: pd.DataFrame, out: Path | None) -> None:
    if out:
        df.to_csv(out, index=False, float_format="%.9f")
        print(f"\nwritten {out}", file=sys.stderr)


def _read_survey(path: Path) -> pd.DataFrame:
    """Occupations from a Stonex .PD project or an Emlid .csv export."""
    readers = {".pd": stonex.read_occupations, ".csv": emlid.read_occupations}
    try:
        return readers[path.suffix.lower()](path)
    except KeyError:
        raise SystemExit(f"stopgo: unsupported survey file {path} (use .PD or .csv)")


def _load_windows(a: argparse.Namespace) -> pd.DataFrame:
    w = processing.occupation_windows(_read_survey(a.survey), a.trim, a.leap)
    if a.ant_h is not None:
        w["ant_h"] = a.ant_h
    if a.points:
        w = w[w["name"].isin(a.points)].reset_index(drop=True)
    return w


def _rtk_config(
    a: argparse.Namespace, parser: argparse.ArgumentParser
) -> rtklib.RtkConfig:
    cfg = rtklib.RtkConfig.from_file(a.conf) if a.conf else rtklib.RtkConfig()
    flags = {
        "pos1-navsys": a.systems and rtklib.navsys_mask(a.systems),
        "pos1-frequency": a.freq,
        "pos1-elmask": a.elmask,
        "pos2-arelmask": a.elmask,
        "pos2-arthres": a.arthres,
        "pos2-gloarmode": a.gloar,
    }
    cfg = cfg.updated({k: v for k, v in flags.items() if v is not None} | dict(a.opt))
    if a.base_pos:
        cfg = cfg.with_base_llh(*a.base_pos)
    if not cfg.has_base_position:
        try:
            cfg = cfg.with_base_llh(*rtklib.header_llh(a.base))
        except (ValueError, OSError) as e:
            parser.error(f"base position missing ({e}): use --base-pos or --conf")
        print("base position from RINEX header", file=sys.stderr)
    return cfg


def cmd_windows(a: argparse.Namespace, _: argparse.ArgumentParser) -> None:
    w = _load_windows(a)
    print(w[["name", "start", "end", "n_logged", "ant_h"]].to_string(index=False))
    _save(w, a.out)


def cmd_static(a: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    cfg = _rtk_config(a, parser)
    try:
        rtklib.find_rnx2rtkp(a.exe)
    except FileNotFoundError as e:
        parser.error(str(e))
    if a.save_conf:
        cfg.write(a.save_conf)
    w = _load_windows(a)
    res = processing.process_static(
        w,
        a.rover,
        a.base,
        a.nav,
        cfg,
        a.exe,
        progress=lambda m: print(m, file=sys.stderr),
    )
    res = processing.add_ground_and_checks(res, w)
    _print_table(res)
    _save(res, a.out)


def cmd_extract(a: argparse.Namespace, _: argparse.ArgumentParser) -> None:
    w = _load_windows(a)
    res = processing.extract_from_trajectory(
        w, rtklib.read_pos(a.pos), fix_only=not a.all_q
    )
    res = processing.add_ground_and_checks(res, w)
    _print_table(res)
    _save(res, a.out)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="stopgo",
        description="Stop-and-go GNSS post-processing "
        "with occupation windows from a Stonex Cube-a project or an Emlid Flow export.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "survey",
        type=Path,
        help="Stonex Cube-a project database (Data/*.PD) or Emlid Flow point export (.csv)",
    )
    common.add_argument("-o", "--out", type=Path, help="output CSV")
    common.add_argument("--points", nargs="+", help="process only these point names")
    common.add_argument(
        "--trim", type=int, default=0, help="seconds dropped at each end of a window"
    )
    common.add_argument(
        "--ant-h",
        type=float,
        help="rover antenna height override [m] "
        "(default: from project; use 0 if the .pos is already at ground)",
    )
    common.add_argument(
        "--leap", type=int, default=rtklib.GPST_UTC_OFFSET_S, help="GPST-UTC [s]"
    )

    sp = sub.add_parser(
        "windows", parents=[common], help="list occupation windows in GPST"
    )
    sp.set_defaults(func=cmd_windows)

    sp = sub.add_parser(
        "static", parents=[common], help="static rnx2rtkp solution per window"
    )
    sp.add_argument(
        "--rover", type=Path, nargs="+", required=True, help="rover RINEX obs file(s)"
    )
    sp.add_argument("--base", type=Path, required=True, help="base RINEX obs file")
    sp.add_argument(
        "--nav", type=Path, nargs="+", required=True, help="navigation file(s)"
    )
    sp.add_argument(
        "--base-pos",
        type=float,
        nargs=3,
        metavar=("LAT", "LON", "H"),
        help="base antenna position, WGS84 ellipsoidal "
        "(default: APPROX POSITION XYZ of the base RINEX)",
    )
    sp.add_argument(
        "--conf", type=Path, help="RTKLIB .conf loaded on top of the built-in defaults"
    )
    sp.add_argument(
        "--systems", help="GNSS letters, e.g. GEC (G GPS, R GLO, E GAL, C BDS, J QZS)"
    )
    sp.add_argument("--freq", choices=["l1", "l1+l2", "l1+l2+l5"], help="frequencies")
    sp.add_argument("--elmask", type=float, help="elevation mask [deg]")
    sp.add_argument("--arthres", type=float, help="AR ratio threshold")
    sp.add_argument("--gloar", choices=["off", "on", "autocal"], help="GLONASS AR mode")
    sp.add_argument(
        "--opt",
        type=_key_value,
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="any RTKLIB option, repeatable (e.g. --opt pos1-snrmask_r=on)",
    )
    sp.add_argument(
        "--save-conf", type=Path, help="write the effective RTKLIB config here"
    )
    sp.add_argument("--exe", default="rnx2rtkp", help="rnx2rtkp executable")
    sp.set_defaults(func=cmd_static)

    sp = sub.add_parser(
        "extract", parents=[common], help="average a kinematic .pos within windows"
    )
    sp.add_argument(
        "pos", type=Path, nargs="+", help="RTKLIB/Emlid Studio .pos file(s)"
    )
    sp.add_argument("--all-q", action="store_true", help="also use float epochs")
    sp.set_defaults(func=cmd_extract)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    a = parser.parse_args(argv)
    a.func(a, parser)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
