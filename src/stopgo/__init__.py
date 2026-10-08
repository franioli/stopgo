"""Stop-and-go GNSS post-processing with RTKLIB and Stonex/Emlid surveys."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("stopgo")
except PackageNotFoundError:  # running from a source tree that is not installed
    __version__ = "unknown"

from . import cli, emlid, processing, rtklib, stonex

__all__ = ["__version__", "cli", "emlid", "processing", "rtklib", "stonex"]
