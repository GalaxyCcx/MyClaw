"""Initialize MCP config - enable mcp-chrome by default for start.bat."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure backend is on path
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from config.mcp_config import set_mcp_enabled

if __name__ == "__main__":
    set_mcp_enabled("mcp-chrome", True)
    print("MCP Chrome enabled.")
