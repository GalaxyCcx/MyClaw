from __future__ import annotations

import argparse
import shutil
from pathlib import Path


DEFAULT_EXTENSION_ID = "bjfgambnhccakkhmkepdoekmckoijdlc"


INJECT_FN = (
    "function zq(){const h=async d=>{try{const s=await pd.getValue();"
    "if(!s)return;if(d.sourceTabId!==s)return;await pd.setValue(d.tabId)}catch(_){}};"
    "chrome.webNavigation.onCreatedNavigationTarget.addListener(h);"
    "return ()=>chrome.webNavigation.onCreatedNavigationTarget.removeListener(h)}"
)

MARKER = "chrome.webNavigation.onCreatedNavigationTarget.addListener"


def _default_store_root() -> Path:
    local = Path.home() / "AppData" / "Local"
    return local / "Google" / "Chrome" / "User Data" / "Default" / "Extensions"


def _latest_version_dir(ext_root: Path) -> Path:
    versions = [p for p in ext_root.iterdir() if p.is_dir()]
    if not versions:
        raise RuntimeError(f"No version directories found under: {ext_root}")
    versions.sort(key=lambda p: p.name)
    return versions[-1]


def _patch_background_js(background_js: Path) -> None:
    text = background_js.read_text(encoding="utf-8")
    if MARKER in text:
        return

    old_list = "const t=[iH(),NO(),$q(),Dq(),CO()];"
    new_list = "const t=[iH(),NO(),$q(),Dq(),zq(),CO()];"
    if old_list not in text:
        raise RuntimeError("Cannot locate Uq() hook list in background.js")
    text = text.replace(old_list, new_list, 1)

    anchor = "const Fq=Ke(()=>{zj.setTag(\"page\",\"background\"),Uq(),Bq()})"
    if anchor not in text:
        raise RuntimeError("Cannot locate injection anchor in background.js")
    text = text.replace(anchor, f"{INJECT_FN}{anchor}", 1)

    background_js.write_text(text, encoding="utf-8")


def _patch_manifest(manifest_path: Path) -> None:
    import json

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data.pop("update_url", None)
    # Remove fixed key to avoid colliding with store-installed extension ID.
    data.pop("key", None)
    name = str(data.get("name") or "Browser MCP")
    if "Patched Local" not in name:
        data["name"] = f"{name} (Patched Local)"
    manifest_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=3) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare patched unpacked Browser MCP extension.")
    parser.add_argument("--extension-id", default=DEFAULT_EXTENSION_ID, help="Chrome extension id")
    parser.add_argument(
        "--store-root",
        default=str(_default_store_root()),
        help="Chrome extensions root directory",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parent.parent / "output" / "browsermcp-extension-patched"),
        help="Output directory for unpacked patched extension",
    )
    args = parser.parse_args()

    store_root = Path(args.store_root)
    ext_root = store_root / args.extension_id
    if not ext_root.exists():
        raise RuntimeError(f"Extension id directory not found: {ext_root}")

    src_dir = _latest_version_dir(ext_root)
    out_dir = Path(args.output_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(src_dir, out_dir)

    background_js = out_dir / "background.js"
    if not background_js.exists():
        raise RuntimeError(f"background.js not found in copied extension: {background_js}")
    _patch_background_js(background_js)

    manifest = out_dir / "manifest.json"
    if manifest.exists():
        _patch_manifest(manifest)

    print(f"Patched extension prepared at: {out_dir}")
    print("Next steps:")
    print("1) Open chrome://extensions")
    print("2) Enable Developer mode")
    print("3) Disable store Browser MCP extension")
    print(f"4) Load unpacked: {out_dir}")


if __name__ == "__main__":
    main()
