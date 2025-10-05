"""Version information for nimbletools-core-operator."""

import importlib.metadata

try:
    __version__ = importlib.metadata.version("nimbletools-core-operator")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.1.0+dev"
