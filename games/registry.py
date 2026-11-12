"""Registry of games. A tournament stores the key of the game it plays."""
_REGISTRY = {}


def register(game):
    _REGISTRY[game.key] = game
    return game


def get(key):
    if key not in _REGISTRY:
        raise KeyError(f"Unknown game: {key}")
    return _REGISTRY[key]


def all_games():
    return list(_REGISTRY.values())
