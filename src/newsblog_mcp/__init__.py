"""NewsBlog Composer MCP."""
from importlib.metadata import PackageNotFoundError, version as _version

try:  # the installed package is the single source of truth for the version
    __version__ = _version("newsblog-composer-mcp")
except PackageNotFoundError:  # running from a source tree with nothing installed
    __version__ = "0.0.0+dev"
