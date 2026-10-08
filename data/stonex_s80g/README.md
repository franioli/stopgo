# Stonex S80G sample dataset (Ronconi, 2023-06-17)

Stop-and-go survey with a low-cost Stonex S80G rover (u-blox, GPS+GLO, L1/L2, 1 Hz), 15 points
(4-18) occupied for 30 s each (antenna height 0.016 m in the project). The base is a second S80G left static
for about 1.8 h, a few tens of metres from the surveyed points; its position (point 1000 below) was obtained
by post-processing the base observations against several CORS.

| Path | Content |
|---|---|
| `project/ronconi.PD` | Cube-a project database (SQLite): points, field SINGLE solutions, per-epoch log (UTC) |
| `rover/1_2023-06-17-06-40-38.ubx` | Raw u-blox rover data, source of the rover RINEX |
| `rover/1_2023-06-17-06-40-38.23{O,P}` | Rover RINEX 3.03 observations and navigation (04:41-05:03 GPST) |
| `rover/1_2023-06-17-06-40-38.pos` | Kinematic solution (RTKLIB `.pos`, GPST, llh) from Emlid Studio 1.5 against the local base |
| `base/1_2023-06-17-06-31-45.23O` | Local base observations, trimmed to 04:35-05:06 GPST |
| `base/1_2023-06-17-06-31-45.23P` | Local base navigation |

Base position (WGS84, in the `APPROX POSITION XYZ` header of the base `.23O`, read automatically by `stopgo static`):
lat 46.28901474, lon 9.61744532, ellipsoidal height 3220.0429 m (project grid E 547560.642, N 5126345.070; orthometric 3169.127).
The antenna delta is 0, so the height is taken as the antenna position.

```sh
D=data/stonex_s80g
stopgo windows $D/project/ronconi.PD
stopgo extract $D/project/ronconi.PD $D/rover/1_2023-06-17-06-40-38.pos --ant-h 0
stopgo static  $D/project/ronconi.PD --rover $D/rover/1_2023-06-17-06-40-38.23O \
    --base $D/base/1_2023-06-17-06-31-45.23O \
    --nav $D/base/1_2023-06-17-06-31-45.23P $D/rover/1_2023-06-17-06-40-38.23P --systems GR
```

Notes
- Receiver tracks only GPS and GLONASS, hence `--systems GR` for the static run.
- Expected: static (30 s windows) fixes 10 of 15 points (4-7, 10, 11, 15-18); 8, 9, 12, 13, 14 stay float.
  The kinematic `.pos` has fixed epochs for all 15, but only some epochs per window at points 4, 6, 7.
- The field coordinates in the `.PD` are SINGLE solutions: not a quality reference.
- Points 1-3 of the original project (deleted, 26 epochs) were removed from the `.PD`.
