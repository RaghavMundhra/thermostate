"""The version of ThermoState."""
from typing import Tuple

__version_info__ = (1, 1, 1, "dev0")  # type: Tuple[int, int, int, str]
__version__ = ".".join([str(v) for v in __version_info__ if str(v)])
