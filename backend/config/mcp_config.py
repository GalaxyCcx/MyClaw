"""MCP configuration - persisted to JSON, overrides .env for runtime toggles."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
MCP_CONFIG_FILE = CONFIG_DIR / "mcp.json"

# Known MCPs that can be enabled/disabled
KNOWN_MCPs = [
    {
        "id": "mcp-chrome",
        "name": "MCP Chrome",
        "description": "通过 Chrome 扩展操作浏览器，支持企业内网登录、页面读取、表单填写",
        "env_key": "MCP_CHROME_ENABLED",
    },
]


def _load_config() -> dict:
    """Load MCP config from file. Falls back to .env if file missing."""
    if MCP_CONFIG_FILE.exists():
        try:
            data = json.loads(MCP_CONFIG_FILE.read_text(encoding="utf-8"))
            return data.get("mcps", {})
        except Exception as e:
            logger.warning("Failed to load MCP config: %s", e)
    return {}


def _save_config(mcps: dict) -> None:
    """Save MCP config to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    MCP_CONFIG_FILE.write_text(
        json.dumps({"mcps": mcps}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def is_mcp_enabled(mcp_id: str) -> bool:
    """Check if MCP is enabled. Config file overrides .env."""
    config = _load_config()
    if mcp_id in config and "enabled" in config[mcp_id]:
        return bool(config[mcp_id]["enabled"])

    # Fallback to env
    for mcp in KNOWN_MCPs:
        if mcp["id"] == mcp_id:
            env_val = os.getenv(mcp["env_key"], "false")
            return env_val.lower() in ("true", "1", "yes")
    return False


def set_mcp_enabled(mcp_id: str, enabled: bool) -> None:
    """Set MCP enabled state and persist."""
    config = _load_config()
    if mcp_id not in config:
        config[mcp_id] = {}
    config[mcp_id]["enabled"] = enabled
    _save_config(config)


def list_mcps() -> list[dict]:
    """List all known MCPs with their current enabled state."""
    config = _load_config()
    result = []
    for mcp in KNOWN_MCPs:
        mcp_id = mcp["id"]
        enabled = config.get(mcp_id, {}).get("enabled")
        if enabled is None:
            enabled = os.getenv(mcp["env_key"], "false").lower() in ("true", "1", "yes")
        result.append({
            "id": mcp_id,
            "name": mcp["name"],
            "description": mcp["description"],
            "enabled": bool(enabled),
        })
    return result
