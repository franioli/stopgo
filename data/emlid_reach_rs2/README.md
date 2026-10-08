# Emlid Reach RS2+ sample dataset (Ventina, 2025-09-14)

Stop-and-go survey with an Emlid Reach RS2+ rover (GPS+GLO+GAL+BDS, dual frequency), 7 points averaged for
1-6 min each (antenna height 1.934 m), processed against the SONP Spin3 CORS (about 13 km baseline).
The survey was collected with Emlid Flow; `stopgo` reads its point export directly.

| Path | Content |
|---|---|
| `project/ventina.csv` | Emlid Flow point export: names, averaging start/end (local time, UTC+02:00), samples, antenna height, field SINGLE solutions |
| `rover/Reach_raw_20250914092007.25O` | Rover RINEX 3.03 observations, 09:20-11:53 GPST, **decimated from 5 Hz to 1 Hz**. **Not tracked in git (too large)** |
| `rover/Reach_raw_20250914092007.25P` | Rover mixed navigation |
| `rover/Reach_raw_20250914092007.pos` | Kinematic solution at 5 Hz (RTKLIB `.pos`, GPST, llh) from Emlid Studio 1.9 against SONP |
| `base/sonp257j00.25o` | SONP 1 Hz observations, trimmed to 09:15-11:59 GPST. **Not tracked in git (too large)** |
| `base/sonp257j00.25{n,g,l,f}` | SONP broadcast navigation, whole day |
| `reference/ventina_corrected.csv` | Emlid Studio's own stop-and-go result (post-processed points, all FIX), to check `stopgo` against |

The base antenna position is the `APPROX POSITION XYZ` plus the antenna delta H (0.05 m) of the SONP RINEX header;
`stopgo static` reads it automatically. The untracked RINEX files must be copied in separately.

```sh
D=data/emlid_reach_rs2
stopgo windows $D/project/ventina.csv
stopgo extract $D/project/ventina.csv $D/rover/Reach_raw_20250914092007.pos
stopgo static  $D/project/ventina.csv --rover $D/rover/Reach_raw_20250914092007.25O \
    --base $D/base/sonp257j00.25o --nav $D/base/sonp257j00.25{n,g,l,f} $D/rover/Reach_raw_20250914092007.25P
```

Notes
- Unlike the Stonex S999 `.pos`, this `.pos` is at antenna level: `h - 1.934` equals the reference ground height,
  so the default antenna height is correct (no `--ant-h 0`).
- `extract` reproduces `reference/ventina_corrected.csv` to within 1 mm (horizontal) and 0.5 mm (height) at all 7 points.
- `static` fixes 6 of 7 points (1003 stays float). Horizontally it agrees with the reference to 2-14 mm,
  but ground heights are 7-14 cm below it (a similar 4-8 cm below the kinematic solution is seen in the S999 sample,
  both against SONP; the S80G sample with a local base shows no such offset).
  Cause not identified: estimating the zenith delay (`--opt pos1-tropopt=est-ztd`) makes it worse on these short windows.
- Emlid's point 1008 (surveyed after the end of the rover log) was removed from `project/` and `reference/`.
- The field coordinates in the export are SINGLE solutions: not a quality reference.
- Removed from the original export: the first Reach session (no points), the real-time `.LLH` solutions, the SBAS
  `.25B` logs and the `_events.pos` files.
