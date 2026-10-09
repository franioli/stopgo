# stopgo

Post-process GNSS **stop-and-go** surveys: continuous rover observations with short static occupations on
survey points. `stopgo` reads the occupation windows from the survey controller, runs (or reads) an
[RTKLIB](https://www.rtklib.com/) solution, and returns one coordinate per point.

Supported surveys: Stonex Cube-a projects (`.PD`) and Emlid Flow point exports (`.csv`).

## Install

Requires Python >= 3.10. The `static` command also needs RTKLIB's `rnx2rtkp`, which `uv` cannot install:

- **Linux / macOS**: build the [demo5 fork](https://github.com/rtklibexplorer/RTKLIB) with
  `cd RTKLIB/app/consapp/rnx2rtkp/gcc && make && sudo make install`
  (Debian/Ubuntu also offer an older build: `sudo apt install rtklib`).
- **Windows**: download a release from the [demo5 releases](https://github.com/rtklibexplorer/RTKLIB/releases)
  and add the folder containing `rnx2rtkp.exe` to your `PATH`.
- Or point to any binary with `--exe /path/to/rnx2rtkp`. If it is missing, `stopgo static` stops with these hints.

`windows` and `extract` do not need RTKLIB. Developed and tested with `rnx2rtkp ver.EX 2.5.1`.

```sh
uv tool install git+https://github.com/franioli/stopgo   # the `stopgo` command
# or, from a clone
uv sync && uv run stopgo --help
```

## Usage

```sh
stopgo windows survey.PD                          # occupation windows in GPST
stopgo extract survey.PD kinematic.pos            # average a kinematic .pos inside each window
stopgo static  survey.PD --rover rover.obs --base base.obs --nav base.nav rover.nav
```

`survey` is a Stonex `.PD` or an Emlid `.csv`. `static` reads the base position from the base RINEX header unless
you pass `--base-pos`. Shared options: `--points`, `--trim`, `--ant-h`, `--leap`, `-o out.csv`.

The full guide (every option, RTKLIB settings, output columns, Python API, troubleshooting) is in
[docs/usage.md](docs/usage.md). RTKLIB parameters, `convbin` conversions and RINEX trimming/merging are in
[docs/rtklib-guide.md](docs/rtklib-guide.md).

## Other receivers

See [docs/adding-a-receiver.md](docs/adding-a-receiver.md) for how to add a survey reader.

## Sample data

`data/` holds one small survey per receiver (Stonex S999, Stonex S80G, Emlid Reach RS2+), each with a README
listing the files and the exact commands. Large RINEX files are not tracked in git.

## Development

```sh
uv sync
uv run pytest
```

## License

MIT, see [LICENSE](LICENSE).
