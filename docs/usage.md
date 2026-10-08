# Usage guide

## Workflow

A survey controller gives you *when* each point was occupied; RTKLIB gives you *where* the rover was. `stopgo`
joins the two: it turns each occupation into a window in GPST, then gets one coordinate per point in one of two ways.

| Command | Input | Method | RTKLIB needed |
|---|---|---|---|
| `windows` | survey file | list the occupation windows (check times, antenna height) | no |
| `extract` | survey file + kinematic `.pos` | average the epochs of a trajectory that fall in each window | no |
| `static` | survey file + RINEX (rover, base, nav) | run `rnx2rtkp` in static mode once per window | yes |

Use `extract` when you already have a kinematic solution (e.g. from Emlid Studio, RTKLIB or the vendor software)
and `static` when you want a fresh solution with your own settings. Comparing the two is a good consistency check.

Inputs: the survey is a Stonex `.PD` or an Emlid Flow `.csv`; the trajectory is an RTKLIB-style llh `.pos`;
RINEX obs/nav are standard RINEX 3 files. Sample files for each receiver are in `data/`.

## Options shared by all commands

| Option | Meaning |
|---|---|
| `survey` | positional: `.PD` or `.csv` |
| `-o, --out FILE` | also write the result as CSV |
| `--points A B ...` | process only these point names |
| `--trim S` | drop `S` seconds at both ends of every window (settling after arriving, leaving early) |
| `--ant-h M` | override the antenna height of all points [m]; use `0` if the `.pos` is already reduced to the ground |
| `--leap S` | GPST - UTC [s], default 18 (valid since 2017); the survey logs UTC, RTKLIB uses GPST |

## `stopgo windows`

```sh
stopgo windows survey.PD --trim 5
```

Prints `name, start, end, n_logged, ant_h` (start/end in GPST). Check here that the windows fall inside your
RINEX/`.pos` time span before processing.

## `stopgo extract`

```sh
stopgo extract survey.csv kinematic.pos [more.pos ...] [--all-q] [--ant-h 0] [-o points.csv]
```

Averages the trajectory epochs inside each window. By default only fixed epochs (Q = 1) are used; `--all-q` also
accepts float ones. Several `.pos` files (e.g. two sessions) are merged by time. A point with no usable epoch is
printed with empty coordinates: look at `fix_pct` and `n_epochs` to see whether the window had no data or no fix.

## `stopgo static`

```sh
stopgo static survey.PD --rover rover.obs [rover2.obs ...] --base base.obs \
    --nav base.nav rover.nav [--base-pos LAT LON H] [RTKLIB options] [-o points.csv]
```

Each window is solved with `rnx2rtkp -ts/-te` (times at 1 s resolution) on the first rover file that fully covers
it; the result is the last epoch of the forward filter. Windows not covered by any rover file are reported as
"no rover data".

- **Base position.** By default read from the base RINEX header (`APPROX POSITION XYZ` plus antenna delta H).
  Override with `--base-pos LAT LON H` (WGS84, ellipsoidal) or `ant2-pos1..3` in `--conf`. Use it when the header
  is only approximate. The base file does not need to cover more than the survey span, so trimmed files are fine.
- **Navigation.** Pass every nav file needed for the systems you use (base and rover nav can be mixed).

### RTKLIB options

Built-in defaults: static mode, L1+L2, forward filter, 15 deg mask, GPS+Galileo+BeiDou, broadcast iono and
Saastamoinen troposphere, continuous ambiguity resolution (threshold 3, GLONASS AR off, BeiDou AR on).
They are layered, later ones win:

1. built-in defaults,
2. `--conf FILE`: any RTKLIB `.conf`, loaded on top of the defaults,
3. the shortcut flags below,
4. `--opt KEY=VALUE` (repeatable): any RTKLIB option by its `.conf` key.

| Option | RTKLIB key | Example |
|---|---|---|
| `--systems` | `pos1-navsys` | `GR` for GPS+GLONASS (letters `G R E C J S I`) |
| `--freq` | `pos1-frequency` | `l1`, `l1+l2`, `l1+l2+l5` |
| `--elmask` | `pos1-elmask`, `pos2-arelmask` | `10` |
| `--arthres` | `pos2-arthres` | `2.5` (lower accepts fixes more easily) |
| `--gloar` | `pos2-gloarmode` | `off`, `on`, `autocal` |
| `--opt` | any | `--opt pos1-tropopt=est-ztd` |

`--save-conf FILE` writes the effective configuration so a run can be reproduced with plain `rnx2rtkp`.
`--exe PATH` selects a specific `rnx2rtkp` binary. The `--systems` choice must match what the rover tracks
(e.g. the Stonex S80G has no Galileo/BeiDou, so use `--systems GR`).

## Output columns

| Column | `extract` | `static` |
|---|---|---|
| `name, start, end, ant_h` | point, GPST window, antenna height | same |
| `source` | `trajectory` | rover file used |
| `Q, ratio, ns` | - | RTKLIB quality (1 fix, 2 float), AR ratio, satellites |
| `fixed` | all used epochs are fixed | `Q == 1` |
| `n_epochs, fix_pct, n_used` | epochs in the window, % fixed, epochs averaged | - |
| `lat, lon, h_ant` | mean position of the antenna (ellipsoidal height) | final-epoch position |
| `sd_e, sd_n, sd_u` | scatter of the averaged epochs [m] | RTKLIB formal std of the final epoch [m] |
| `h_ground` | `h_ant - ant_h` | same |
| `d2d_field, dh_field` | horizontal and height difference to the controller's own (SINGLE) coordinates, when available | same |

The two `sd` flavours differ in meaning: compare them across points of the same command, not between commands.
With `-o`, the CSV keeps full precision (9 decimals).

## Python API

```python
from pathlib import Path
from stopgo import processing, rtklib, stonex  # or emlid

occ = stonex.read_occupations(
    Path("project/ronconi.PD")
)  # emlid.read_occupations(csv) for Emlid
w = processing.occupation_windows(occ, trim_s=5)  # adds GPST start/end

# 1) average a kinematic trajectory
pos = rtklib.read_pos([
    Path("rover/a.pos"),
    Path("rover/b.pos"),
])  # time-sorted DataFrame, column `t` in GPST
res = processing.extract_from_trajectory(w, pos, fix_only=True)

# 2) or run static rnx2rtkp per window
base = Path("base/base.23O")
cfg = (
    rtklib
    .RtkConfig()  # defaults; RtkConfig.from_file(conf) to start from a .conf
    .updated({"pos1-navsys": rtklib.navsys_mask("GR")})
    .with_base_llh(*rtklib.header_llh(base))
)
res = processing.process_static(
    w, [Path("rover/rover.23O")], base, [Path("base/base.23P")], cfg, progress=print
)

res = processing.add_ground_and_checks(res, w)  # h_ground, d2d_field, dh_field
```

| Module | Contents |
|---|---|
| `stopgo.stonex` | `read_occupations`, plus `read_points` / `read_epochs` for the raw `.PD` tables |
| `stopgo.emlid` | `read_occupations` |
| `stopgo.processing` | `occupation_windows`, `extract_from_trajectory`, `process_static`, `add_ground_and_checks` |
| `stopgo.rtklib` | `RtkConfig` (immutable options: `from_file`, `updated`, `with_base_llh`, `write`), `read_pos`, `run_rnx2rtkp`, `solve_static`, `header_llh`, `rinex_span`, `navsys_mask`, `find_rnx2rtkp` |

## Troubleshooting

- **All points empty / "no rover data".** The windows are outside the file span: run `windows` and compare with the
  RINEX/`.pos` time range; check `--leap`.
- **Points float in `static`.** Short windows (30 s) on a long baseline often cannot fix. Try `--arthres`, a longer
  window (less `--trim`), more systems, or use `extract` on a kinematic solution that has converged beforehand.
- **Heights off by the antenna height.** The `.pos` may already be reduced to the ground: use `--ant-h 0`
  (see the sample READMEs for examples of both cases).
- **`rnx2rtkp` not found.** See the install hints in the README.
