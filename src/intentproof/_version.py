from importlib.metadata import PackageNotFoundError, version

try:
    VERSION = version("intentproof-sdk")
except PackageNotFoundError:
    VERSION = "0.0.0"
