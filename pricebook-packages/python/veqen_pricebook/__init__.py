"""Load the installed, dated price-book snapshot without network access."""
import json
from importlib.resources import files


def load() -> dict:
    """Return an independent copy. Token rates are USD per million tokens."""
    return json.loads(files(__package__).joinpath("prices.json").read_text(encoding="utf-8"))
