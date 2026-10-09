# RTKLIB parameters and tools guide

How the RTKLIB options behind `stopgo static` work, how to pass them (through `stopgo` or straight to `rnx2rtkp`),
and how to prepare input files with the other RTKLIB programs (`convbin`, `str2str`, GUI apps).
For the stopgo commands themselves see [usage.md](usage.md).

Examples assume the [demo5 fork](https://github.com/rtklibexplorer/RTKLIB). Check the exact options of your build
with `rnx2rtkp -?` and `convbin -h`.

## 1. Three ways to set an option

`stopgo static` builds an RTKLIB configuration in layers; later layers win:

1. built-in defaults,
2. `--conf FILE`: a RTKLIB `.conf` file,
3. shortcut flags (`--systems`, `--freq`, `--elmask`, `--arthres`, `--gloar`),
4. `--opt KEY=VALUE` (repeatable), where `KEY` is any key of the `.conf` file.

`--save-conf FILE` writes the effective configuration. This lets you reproduce a run with plain RTKLIB:

```sh
stopgo static survey.PD --rover r.26O --base b.26O --nav *.26P --systems GEC --elmask 10 --save-conf run.conf
rnx2rtkp -k run.conf -ts 2026/09/06 08:56:00 -te 2026/09/06 08:58:00 -o out.pos r.26O b.26O *.26P
```

## 2. stopgo options

| Option | Meaning |
|---|---|
| `--rover` / `--base` / `--nav` | rover obs file(s), base obs file (exactly one), all broadcast nav files. The shell expands globs (`.26O` has an uppercase O) |
| `--base-pos LAT LON H` | base antenna position, WGS84 ellipsoidal (deg, deg, m). Default is the RINEX header, which is only metre-level: pass an accurate position whenever you have one |
| `--systems` | GNSS letters: G GPS, R GLONASS, E Galileo, C BeiDou, J QZSS. Becomes the `pos1-navsys` bitmask (section 3) |
| `--freq` | `l1`, `l1+l2`, `l1+l2+l5` (`pos1-frequency`). Use `l1+l2` if the base lacks L5 |
| `--elmask` | elevation mask [deg]. Sets **both** `pos1-elmask` and `pos2-arelmask` |
| `--arthres` | AR ratio threshold (`pos2-arthres`), see section 4 |
| `--gloar` | GLONASS ambiguity resolution (`pos2-gloarmode`): `off`, `on`, `autocal` |
| `--trim S` | seconds dropped at each end of every window (stop/go transitions). `0` keeps all epochs |
| `--leap S` | GPST - UTC [s] (18 since 2017), converts survey times to GPST |
| `--ant-h M` | override the rover antenna height [m] (default: from the survey project) |
| `--points A B ...` | process only these point names |
| `--opt KEY=VALUE` | any RTKLIB option, repeatable |
| `--conf FILE` / `--save-conf FILE` | load / write a `.conf` file |
| `--exe PATH` | specific `rnx2rtkp` binary |
| `-o FILE` | output CSV |

## 3. RTKLIB options that matter for static processing

stopgo defaults in **bold**. Keys are the `.conf` names, so they work with `--opt`, `--conf` and `rnx2rtkp -k`.

### Positioning and models (`pos1-*`)

| Key | Values | Meaning |
|---|---|---|
| `pos1-posmode` | **static**, kinematic, ... | static solves one position for the whole window |
| `pos1-frequency` | l1, **l1+l2**, l1+l2+l5 | frequencies used (`--freq`) |
| `pos1-soltype` | **forward**, backward, combined | filter direction. For static the end result is the same; stopgo takes the last epoch |
| `pos1-elmask` | **15** [deg] | satellites below are discarded. Lower = more satellites, more multipath and troposphere error |
| `pos1-snrmask_r` | **off**, on | SNR mask for the rover |
| `pos1-dynamics` | **off** | receiver dynamics model; irrelevant for static |
| `pos1-ionoopt` | **brdc**, off, dual-freq, est-stec | `brdc` = Klobuchar broadcast model. `dual-freq` = iono-free combination: removes the ionosphere but amplifies noise, so it is not worth it on short baselines (< ~10 km) where iono cancels in the double difference |
| `pos1-tropopt` | **saas**, off, est-ztd | `saas` = Saastamoinen model. `est-ztd` estimates the zenith delay: only useful on long baselines or large height differences, it adds unknowns and hurts short windows |
| `pos1-sateph` | **brdc**, precise, ... | ephemerides. `precise` needs `.sp3`/`.clk` files |
| `pos1-navsys` | **41** | bitmask: G=1, S=2, R=4, E=8, J=16, C=32, I=64. GE=9, GEC=41, GREC=45 (`--systems`) |

### Ambiguity resolution (`pos2-*`)

| Key | Values | Meaning |
|---|---|---|
| `pos2-armode` | off, **continuous**, instantaneous, fix-and-hold | `continuous` tries AR at every epoch; `fix-and-hold` feeds the fixed result back as a constraint (can lock in a wrong fix on short windows) |
| `pos2-gloarmode` | **off**, on, autocal, fix-and-hold | GLONASS AR. Keep off with mixed receiver brands (inter-channel biases) |
| `pos2-bdsarmode` | **on**, off | BeiDou AR (demo5) |
| `pos2-arthres` | **3** | ratio threshold, see section 4 |
| `pos2-arlockcnt` | **0** | epochs an ambiguity must be tracked before AR is attempted (demo5) |
| `pos2-arelmask` | **15** [deg] | elevation mask for satellites in AR, separate from `pos1-elmask` |
| `pos2-arminfix` | demo5 | fixes required before accepting; see the demo5 manual |

### Statistics and antenna (`stats-*`, `ant*-*`)

| Key | Meaning |
|---|---|
| `stats-eratio1`, `stats-eratio2` | code/phase error ratio for L1/L2 (default 100). Larger = code is down-weighted relative to phase |
| `ant2-postype`, `ant2-pos1..3` | base position (`llh`: deg, deg, m). Set by `--base-pos` |
| `out-solformat` | **llh** output format |

demo5-only options (`bdsarmode`, `arlockcnt`, `arminfix`, ...) are silently ignored or rejected by the original
RTKLIB 2.4.x. Use `--save-conf` to confirm what was actually applied.

## 4. The AR ratio and how to judge a solution

For each epoch the filter produces a float solution, then searches integer ambiguity candidates (LAMBDA). The
**ratio** is the residual of the second-best candidate divided by that of the best. If ratio > `pos2-arthres` the
best candidate is accepted (`Q = 1`, fixed); otherwise the solution stays float (`Q = 2`).

- 3 is the usual threshold. Lower values (2.5, 2) accept more fixes, with a higher risk of **wrong** fixes.
- Ratio is a validation heuristic, not a probability: a high ratio on a very short window can still be wrong.

Checklist for a point:

1. `Q = 1` and `ratio` > 3 (prefer > 5-10); formal std of a few mm horizontal, ~1-3 mm vertical on short baselines.
2. `ns` >= 8 and similar between runs.
3. Stability: fixed coordinates should agree within ~1 cm across reasonable variants (mask 8/10/15, with/without BDS).
4. Float points (`Q = 2`, std of cm or worse) are not usable for precise work; report them as float or re-occupy.
5. Compare against independent coordinates when available (the controller's own `d2d_field`/`dh_field` are a
   consistency check, not ground truth).

## 5. A worked example: tuning on a hard session

Short baseline (~800 m), seven 120 s windows at 1 Hz, Emlid base + Stonex S999 rover, 2026-09-06. Common command:

```zsh
uv run stopgo static survey.PD \
  --rover rinex/*/*.26O \
  --base  base/Reach_raw_20260906082522.26O \
  --nav   rinex/*/*.26[NGLC] base/*.26P \
  --base-pos 46.2790777945 9.780507756 2302.62285 \
  <VARIANT OPTIONS> --leap 18 -o out.csv
```

Fixed (X) / float (F) with the ratio, `--freq l1+l2 --gloar off --leap 18` in all runs:

| Run | Variant options | 1001 | 1008 | 1009 | 1004 | 1010 | 1011 | 2000 |
|---|---|---|---|---|---|---|---|---|
| A | `--systems GE --elmask 15 --arthres 3 --trim 5` | F 1.2 | X 30.8 | X 50.2 | X 43.7 | X 24.9 | F 2.0 | X 3.5 |
| C | `--systems GREC --elmask 15 --trim 5` | F 1.2 | - | - | - | - | F 1.4 | X 3.5 |
| D | A + `--opt pos2-armode=fix-and-hold --opt stats-eratio1=300 --opt stats-eratio2=300` | F 2.4 | - | - | - | - | F 2.0 | X 3.6 |
| E | A + `--opt pos1-ionoopt=dual-freq --opt pos1-tropopt=est-ztd` | F 0.0 | - | - | - | - | F 0.0 | F 0.0 |
| H | `--systems GE --elmask 8 --trim 0` | F 1.0 | X 32.4 | X 52.3 | X 42.4 | X 26.9 | X 6.6 | X 3.9 |
| I | H with `--elmask 10 --arthres 2.5` | F 1.0 | X 32.4 | X 52.3 | X 42.4 | X 26.9 | X 5.6 | X 3.9 |
| **G** | **`--systems GEC --elmask 10 --trim 0`** | F 1.2 | X 31.6 | X 38.8 | X 103.3 | X 12.8 | X 14.6 | X 3.9 |

(Runs B and F, omitted here, are `GE` mask 10 with trim 0 and 5.) Findings:

- A lower mask **and** `--trim 0` fixes 1011. With trim 5 it stays float, because it needs the extra epochs.
- Adding BeiDou raises the ratio on 1011 (6.6 to 14.6) and 1004 (42 to 103), but the fixes exist without it.
- GLONASS, fix-and-hold, and estimated troposphere with dual-frequency iono did not help. The last one breaks
  everything on an 800 m baseline (less redundancy, extra noise for no gain).
- 1001 never fixes and its float position moves by metres between runs: treat it as unreliable (probably poor
  early-session data or multipath). 2000 is a marginal fix (ratio 3.5-3.9) but is stable to < 1 mm: flag as lower confidence.
- Lowering `--arthres` to 2.5 changed nothing useful.

Best, run G (6/7 fixed):

```zsh
--systems GEC --freq l1+l2 --elmask 10 --arthres 3 --gloar off --trim 0 --leap 18 \
--save-conf run_G.conf -o static_G.csv
```

Method: change **one thing at a time**, keep the table, and prefer the simplest configuration whose fixed
coordinates agree with the neighbouring variants.

## 6. Using rnx2rtkp directly

```sh
rnx2rtkp [options] rover.obs base.obs nav1 [nav2 ...]
```

The first obs file is the rover, the second the base, then at least one nav file (up to 16 input files; use
quotes `"*.nav"` to let RTKLIB expand wildcards). Output goes to stdout unless `-o`.

| Option | Meaning | stopgo equivalent |
|---|---|---|
| `-k file` | read options from a `.conf` (command-line options take precedence) | `--conf` |
| `-o file` | output `.pos` file | (internal) |
| `-ts y/m/d h:m:s`, `-te ...` | start / end time, GPST | window from survey |
| `-ti s` | decimate to this interval | |
| `-p mode` | 0 single, 1 dgps, 2 kinematic, 3 static, 4 static-start, 5 moving-base, 6 fixed, 7-9 PPP | `pos1-posmode` |
| `-m deg` | elevation mask | `--elmask` |
| `-sys G,R,E,J,C,I` | systems | `--systems` |
| `-f n` | 1 = L1, 2 = L1+L2, 3 = L1+L2+L5 | `--freq` |
| `-v thres` | AR ratio threshold (0 = no AR) | `--arthres` |
| `-b`, `-c` | backward / combined solution | `pos1-soltype` |
| `-i`, `-h` | instantaneous AR / fix-and-hold | `pos2-armode` |
| `-l lat lon h`, `-r x y z` | base position (llh deg/m, or ECEF m) | `--base-pos` |
| `-e`, `-a`, `-g` | output ECEF / ENU baseline / dms | |
| `-t`, `-u` | time as yyyy/mm/dd hh:mm:ss / in UTC | |
| `-y level` | status output (1 states, 2 residuals), written to `<out>.stat` | |
| `-x level` | debug trace | |

Example, equivalent to one stopgo window (static, GPS+Galileo, 10 deg mask):

```sh
rnx2rtkp -p 3 -sys G,E -m 10 -f 2 -l 46.2790777945 9.780507756 2302.62285 \
  -ts 2026/09/06 08:56:00 -te 2026/09/06 08:58:00 -o w1001.pos \
  rover.26O base.26O base.26P
```

`.pos` columns: date, GPST time, lat, lon, h, `Q`, `ns`, std n/e/u, std ne/eu/un, `age`, `ratio`.
`Q`: 1 fixed, 2 float, 4 DGPS, 5 single.

## 7. Converting raw data with convbin

`convbin` converts receiver logs into RINEX. It handles one input file per call, and takes the format from the
extension or from `-r`. The GUI equivalent is `rtkconv` (`rtkconv_qt` on Linux builds): same options in a dialog,
and a preview of the satellites and time span.

### Basic use

```sh
convbin -r rtcm3 -v 3.03 -od -os -tr 2026/09/06 08:00:00 -d out/ file.dat
```

| Option | Meaning |
|---|---|
| `-r fmt` | input format: `rtcm2`, `rtcm3`, `ubx`, `nov`, `sbf`, `rt17`, `binex`, `javad`, `rinex`, ... |
| `-v ver` | RINEX version (default 3.04). Use `3.03` or `3.02` for older tools |
| `-od`, `-os` | include Doppler and SNR in the obs file (needed for SNR masks and some processing) |
| `-tr y/m/d h:m:s` | approximate time, **required for RTCM** (see below) |
| `-ts`, `-te`, `-ti`, `-span` | start / end time, interval [s], span [h] |
| `-hp x/y/z`, `-hd h/e/n`, `-hm name`, `-ha ant`, `-hr rec` | RINEX header fields (approx position, antenna delta, marker, antenna, receiver) |
| `-y C` / `-y R ...`, `-x sat` | exclude systems / satellites |
| `-mask`, `-nomask` | include / exclude specific signals, e.g. `-nomask CL1I` |
| `-f n` | number of frequencies |
| `-d dir`, `-o`, `-n`, `-g`, ... | output directory / explicit obs / nav / GLONASS nav file names |
| `-c staid` | use the RINEX naming convention with this station id |

By default the outputs are written next to the input as `<name>.obs`, `<name>.nav` (mixed systems, RINEX 3).

### RTCM 3 logs (e.g. DJI `.dat`)

RTCM 3 messages carry the time of week but **not the week number**, so `convbin` needs an approximate date
(`-tr`, within a few days) to place the data. DJI RTK/drone logs that store raw RTCM 3 MSM messages (1074/1084/1094/
1124, plus ephemerides 1019/1020/1045/1046) are read with `-r rtcm3`, whatever the extension:

```sh
convbin -r rtcm3 -v 3.03 -od -os -tr 2026/09/06 08:00:00 -d rinex/ DJI_0001.dat
```

Notes:

- Broadcast ephemerides must be in the stream. If the log has no 1019/1020/1045/... messages the nav file is
  empty: supply nav files from another source (e.g. the base, or an IGS `BRDC` file).
- An RTCM stream often has no header information: set marker, antenna and approximate position with `-hm`, `-ha`,
  `-hp`. Without `-hp` the header position is zero, which matters when `stopgo` reads the base position from the
  header (use `--base-pos` then).
- I have not verified what a specific DJI model writes in its `.dat` files; check with
  `convbin -r rtcm3 -trace 3 -tr ... file.dat` and look at the message counts if the output is empty.
- Several RTCM files from the same receiver can be concatenated first (`cat a.dat b.dat > all.dat`) and converted
  once.

### Many files

`convbin` has no multi-file mode, so loop in the shell:

```sh
mkdir -p rinex
for f in raw/*.ubx; do convbin -r ubx -v 3.03 -od -os -d rinex/ "$f"; done
```

### Other vendors

```sh
convbin -r ubx  -od -os -f 2 raw.ubx            # u-blox F9P/M8T
convbin -r sbf  -od -os raw.sbf                  # Septentrio
convbin -r rtcm3 -tr 2026/09/06 08:00:00 base.rtcm3
```

## 8. Trimming and decimating RINEX

`convbin` can read RINEX (`-r rinex`) and write it back with a time window and interval. This is also how to
cut a huge file down to the survey span:

```sh
# keep 08:50-10:10 GPST at 1 s
convbin -r rinex -v 3.03 -ts 2026/09/06 08:50:00 -te 2026/09/06 10:10:00 -ti 1 \
  -od -os -d trimmed/ rover.26O

# decimate base data from 1 Hz to 30 s
convbin -r rinex -v 3.03 -ti 30 -d trimmed/ base.26O
```

Notes:

- Times are in the time system of the RINEX file (GPST for most receivers): check the header.
- `convbin` rewrites the header from its own defaults, so re-set `-hp`/`-hd`/`-hm` if you need them preserved.
- For stopgo you rarely need to trim: `static` cuts each window itself with `rnx2rtkp -ts/-te`. Trimming only
  saves disk and time.

## 9. Merging RINEX files

RTKLIB has no merge tool for RINEX observation files. Options:

- **`gfzrnx`** (free, from GFZ, separate download): `gfzrnx -finp a.26O b.26O -fout merged.26O`. Reliable, handles
  headers, observation types and gaps.
- **RTCM / raw logs**: merge *before* converting: `cat a.rtcm3 b.rtcm3 > all.rtcm3`, then one `convbin` call. Works
  for formats that are plain message streams (RTCM, UBX); not for file formats with a header.
- **Manually** (same receiver, same observation types, consecutive files only): keep the full first file and
  append the epoch records of the second, i.e. everything after its `END OF HEADER` line. This is untested here,
  and mixed-up observation types, or a changed antenna or interval, silently produce a bad file.

**Do you need to merge for stopgo?** Only when a window straddles two rover files; `stopgo static` assigns each
window to the first file that fully covers it (see [usage.md](usage.md#multiple-input-files)).

Navigation files never need merging: pass them all with `--nav` (or as extra arguments to `rnx2rtkp`).

## 10. Streams, plots and the GUI apps

| Program | Use |
|---|---|
| `str2str` | record or relay a stream (serial, TCP, NTRIP) to a file, e.g. log a base's RTCM3 for later conversion |
| `rtkconv` (`rtkconv_qt`) | GUI for `convbin` |
| `rtkpost` (`rtkpost_qt`) | GUI for `rnx2rtkp`: build and test a `.conf` interactively, then load it with `--conf` |
| `rtkplot` (`rtkplot_qt`) | plot `.pos` files, observations (SNR, multipath, satellite visibility), solution status |
| `rtkget` (`rtkget_qt`) | download ephemerides, precise orbits, base station data |
| `pos2kml` | convert a `.pos` file to KML for Google Earth |

```sh
# record a base station NTRIP stream for 1 h
str2str -in ntrip://user:pass@caster:2101/MOUNT -out file://base_%Y%m%d_%h%M.rtcm3
```

A practical tip: tune options on one hard window in `rtkpost` (it shows ratio and residuals via `rtkplot`), save
the `.conf`, then run the whole survey with `stopgo static --conf tuned.conf`.

## 11. Troubleshooting

- **Everything float.** Check, in order: base position (`--base-pos`), systems tracked by both receivers,
  navigation files for each system, `--trim` too large for the window, mask too high.
- **Fix with a huge ratio but a wrong position.** Common with a wrong base position or wrong antenna height: the
  ambiguities fix consistently but the coordinates are shifted. Compare with a known point.
- **`rnx2rtkp` rejects a key.** The key name is spelled as in the `.conf` (`pos1-elmask`, not `elmask`). The
  option may exist only in demo5.
- **Empty RINEX from `convbin`.** Wrong `-r` format, missing `-tr` for RTCM, or no observation messages
  (MSM 107x/108x/109x/112x) in the log.
- **Wrong time (week) after conversion.** Check `-tr`; RTCM time is ambiguous by whole weeks.

## References

- RTKLIB manual (T. Takasu), chapter 3 "RTKLIB Programs" and appendix on `rnx2rtkp`/`convbin` options and
  configuration: <https://www.rtklib.com/prog/manual_2.4.2.pdf>
- demo5 manual (options added in the rtklibexplorer fork): <https://rtkexplorer.com/downloads/rtklib-code/>
- LAMBDA and the ratio test: Teunissen, P.J.G. (1995), "The least-squares ambiguity decorrelation adjustment",
  *J. Geodesy* 70, 65-82.
