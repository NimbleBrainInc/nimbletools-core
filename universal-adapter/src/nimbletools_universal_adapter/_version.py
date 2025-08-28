"""Version information for nimbletools-universal-adapter."""

import importlib.metadata

try:
    __version__ = importlib.metadata.version("nimbletools-universal-adapter")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.1.0+dev"
