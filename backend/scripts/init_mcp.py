"""Initialize browser transport config for start.bat."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure backend is on path
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from config.mcp_config import set_mcp_enabled

if __name__ == "__main__":
    transport = (os.getenv("BROWSER_TRANSPORT", "native_extension") or "native_extension").strip().lower()
    if transport == "legacy_mcp":
        set_mcp_enabled("browser-mcp", True)
        print("Browser MCP enabled (legacy_mcp mode).")
    else:
        set_mcp_enabled("browser-mcp", False)
        print("Browser MCP disabled (native_extension mode).")
