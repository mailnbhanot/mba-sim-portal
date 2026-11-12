from .registry import all_games, get, register  # noqa: F401

# Every game module imports and registers itself here. To add a game, create a folder
# games/<your_game>/ (see games/base.py and README.md) and add one import line below.
from . import rural_marketing  # noqa: F401,E402
