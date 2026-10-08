# Stonex S999 sample dataset (Ventina, 2026-09-06)

Stop-and-go survey with a Stonex S999 rover (RTK-capable, GPS+GLO+BDS+GAL, 1 Hz, dual frequency),
4 points occupied for 120 s each (antenna height 2.073 m), processed against the SONP Spin3 CORS
(about 13 km baseline). This is the first of the two rover sessions of the original survey
(the second one, with 3 more points, was dropped to keep the sample small).

| Path | Content |
|---|---|
| `project/ventina_20260906.PD` | Cube-a project database (SQLite): points, field SINGLE solutions, per-epoch log (UTC) |
| `rover/01482491.26O` | Rover RINEX 3.02 observations, 08:48-10:07 GPST. **Not tracked in git (too large)** |
| `rover/01482491.pos` | Kinematic solution (RTKLIB `.pos`, GPST, llh) from Emlid Studio 1.10 |
| `base/sonp249g00.26o` | SONP 1 Hz observations, trimmed to 08:45-10:11 GPST. **Not tracked in git (too large)** |
| `base/sonp249g00.26{n,g,l,f}` | SONP broadcast navigation (GPS, GLO, GAL, other), whole day |

The base antenna position is the `APPROX POSITION XYZ` of the SONP RINEX header; `stopgo static` reads it automatically.
The untracked RINEX files must be copied in separately (rover from the receiver, base from the Spin3 archive).

```sh
D=data/stonex_s999
stopgo windows $D/project/ventina_20260906.PD
stopgo extract $D/project/ventina_20260906.PD $D/rover/01482491.pos --ant-h 0
stopgo static  $D/project/ventina_20260906.PD --rover $D/rover/01482491.26O \
    --base $D/base/sonp249g00.26o --nav $D/base/sonp249g00.26{n,g,l,f}
```

Notes
- The `.pos` was computed against an Emlid Reach base that is not included. Its heights agree with
  the static ground heights to about 10 cm, i.e. it appears to be already reduced by the antenna height,
  hence `--ant-h 0` (not confirmed against the Emlid Studio settings).
- Static heights against SONP include the base antenna delta (+0.05 m from the header) and sit about 4-8 cm
  below the kinematic ones (same effect as in the Emlid sample, cause not identified).
- The field coordinates in the `.PD` are SINGLE solutions (1-2 m noise): not a quality reference.
- Expected: the two methods disagree on purpose, which makes the sample useful.
  Kinematic fixes 1001 only (1008, 1009, 1004 are float in the `.pos`); static (120 s windows) fixes 1008 only
  (ratio 5.3), the other three stay float.
