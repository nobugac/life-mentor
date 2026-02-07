#!/usr/bin/env python3
"""Install Obsidian front-end files into a vault.

Default vault path: /Users/sean/workspace/life/note
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def copy_file(src: Path, dst: Path, force: bool) -> None:
    if dst.exists() and not force:
        print(f"[skip] {dst}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"[write] {dst}")


def copy_tree(src_dir: Path, dst_dir: Path, force: bool) -> None:
    for path in src_dir.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(src_dir)
        copy_file(path, dst_dir / rel, force)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install LifeMentor Obsidian front-end")
    parser.add_argument(
        "--vault",
        default="/Users/sean/workspace/life/note",
        help="Target Obsidian vault path",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files",
    )
    parser.add_argument(
        "--install-plugin",
        action="store_true",
        help="Install Life Mentor Bridge plugin into .obsidian/plugins",
    )
    args = parser.parse_args()

    vault = Path(args.vault).expanduser()
    if not vault.exists():
        print(f"Vault not found: {vault}")
        return 1

    root = Path(__file__).resolve().parents[1]
    template_root = root / "obsidian_frontend"

    life_mentor_src = template_root / "LifeMentor"
    if not life_mentor_src.exists():
        print(f"Template not found: {life_mentor_src}")
        return 1

    copy_tree(life_mentor_src, vault / "LifeMentor", args.force)

    css_src = template_root / ".obsidian" / "snippets" / "lifementor-native.css"
    if css_src.exists():
        copy_file(css_src, vault / ".obsidian" / "snippets" / "lifementor-native.css", args.force)

    if args.install_plugin:
        plugin_src = root.parent / "obsidian-plugin" / "life-mentor-bridge"
        plugin_dst = vault / ".obsidian" / "plugins" / "life-mentor-bridge"
        if plugin_src.exists():
            copy_tree(plugin_src, plugin_dst, args.force)
        else:
            print(f"Plugin source not found: {plugin_src}")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
