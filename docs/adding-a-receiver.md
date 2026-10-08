# Adding support for another receiver

`stopgo` only needs one thing from a survey: **when each point was occupied**. A reader turns the controller's
export into a table of occupations; everything else (`windows`, `extract`, `static`) is receiver-independent.
`stopgo.stonex` (SQLite project) and `stopgo.emlid` (CSV export) are the two reference implementations.

## 1. Write a reader

Create `src/stopgo/<vendor>.py` with `read_occupations(path: Path) -> pd.DataFrame`, one row per point:

| Column | Required | Meaning |
|---|---|---|
| `name` | yes | point name (string) |
| `t0_utc`, `t1_utc` | yes | start and end of the occupation, **naive UTC** `datetime64` |
| `ant_h` | yes | antenna height [m], the value to subtract from the solution height to reach the ground |
| `n_logged` | yes | number of epochs logged (shown by `stopgo windows`) |
| `field_lat`, `field_lon`, `field_h` | optional | the controller's own coordinates (ellipsoidal height); all three enable the `d2d_field`/`dh_field` checks |
| `code` | optional | point code |

```python
def read_occupations(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    return pd.DataFrame({
        "name": df["Point"].astype(str),
        "t0_utc": pd.to_datetime(df["Start"]),   # convert any local time zone to UTC first
        "t1_utc": pd.to_datetime(df["End"]),
        "n_logged": df["Epochs"],
        "ant_h": df["AntHeight"],
    }).sort_values("t0_utc").reset_index(drop=True)
```

Points to check against your receiver's data:
- **Time system.** Controllers log UTC or local time; `stopgo` converts UTC to GPST by adding the leap seconds
  (18 s, `--leap` to change). A wrong offset shifts every window and shows up as empty or unfixed points.
- **Antenna height.** Make sure it is the height the solution refers to. Check on a real point: if the kinematic
  `.pos` was already reduced to the ground by the processing software, run `extract` with `--ant-h 0`
  (the Stonex S999 sample is an example, the Emlid one is not).
- **Heights.** `field_h` must be ellipsoidal, like the RTKLIB output. Orthometric heights make `dh_field` meaningless.
- **Deleted or test points.** Drop them in the reader (Stonex: `DeleteSign = 0`).
- **No averaging windows exported?** Derive them from whatever the receiver does log (per-epoch records with a
  point id, event marks, point-collection start/stop times).

## 2. Register it

In `src/stopgo/cli.py`, add the file extension to the `readers` dict of `_read_survey`, and import the module in
`src/stopgo/__init__.py`. Dispatch is by extension, so if the new export is also a `.csv`, look at the header
columns instead of the suffix.

## 3. Test and document

- Add `tests/test_<vendor>.py` with a tiny inline fixture (see `tests/test_emlid.py`): column names, UTC
  conversion, sort order. Add one CLI test that `windows` accepts the file.
- Add a sample under `data/<receiver>/` following the existing layout (`project/`, `rover/`, `base/`, a README with
  the exact commands). Keep it small: a few points, RINEX trimmed to the survey span, and a rover `.pos` so
  `extract` works without RTKLIB. Large RINEX files go in `.gitignore`.
- Compare `extract` and `static` with the vendor's own post-processed coordinates if it provides them (the Emlid
  sample ships `reference/ventina_corrected.csv`); this catches time-offset and antenna-height mistakes quickly.

Nothing else changes: `processing.py` and `rtklib.py` are receiver-independent.
