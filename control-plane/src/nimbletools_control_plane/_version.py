"""Version information for nimbletools-control-plane."""

import importlib.metadata

try:
    __version__ = importlib.metadata.version("nimbletools-control-plane")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.1.0+dev"
