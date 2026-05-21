# -*- coding: utf-8 -*-
"""
Sestaví Kodi repozitář do složky repo/.

Použití:
    python build_repo.py
    python build_repo.py --base-url https://raw.githubusercontent.com/daker52/TVstreamCZ/main/repo/

Po sestavení nahrajte obsah repo/ na web (GitHub push stačí pro raw URL).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import zipfile
import xml.etree.ElementTree as ET

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Výchozí veřejná URL (GitHub raw) – změňte přes --base-url
DEFAULT_BASE_URL = "https://raw.githubusercontent.com/daker52/TVstreamCZ/main/repo/"

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.join(ROOT, "repo")
REPO_ADDON_VERSION = "1.0.1"

EXCLUDE = {
    ".git", ".gitignore", ".venv", "venv", "env", "repo", "__pycache__",
    "build_repo.py", ".github",
    "debug_ajax.py", "debug_film_detail.py", "debug_html.py",
    "debug_kodi_import.py", "debug_sledujfilmy.html", "debug_sledujfilmy.py",
    "detect_kodi_python.py", "enable_sledujfilmy.py", "fix_numpy.py",
    "FIX_PYTHON38.md", "get_full_url.py", "get_stream_url.py",
    "INSTALL_ALL.bat", "install_chromedriver.py", "INSTALL_DEPENDENCIES.md",
    "install_for_new_kodi.py", "install_selenium3.py", "install_sledujfilmy.bat",
    "install_to_kodi.py", "playwright_debug.html",
    "resolve_direct_link.py", "show_stream_url.py",
    "sledujfilmy_ajax.html", "sledujfilmy_debug.html",
    "sledujfilmy_film_detail.html", "SLEDUJFILMY_INSTALACE.md",
    "sledujfilmy_player.html", "SLEDUJFILMY_README.md",
    "temp_sdilej.html", "test_film_search.py", "test_import.py",
    "test_kodi_import.py", "test_minimal_import.py", "test_sledujfilmy.py",
    "test_turnstile_new.py", "test_turnstile.py", "TROUBLESHOOTING.md",
    "uninstall_selenium4.py", "check_installation.py",
    "create_kodi_zip.py",
}


def _should_exclude(rel_path: str) -> bool:
    parts = rel_path.replace("\\", "/").split("/")
    for part in parts:
        if part in EXCLUDE or part == "__pycache__" or part.endswith(".pyc"):
            return True
    return False


def read_addon_meta(addon_xml_path: str) -> tuple[str, str]:
    tree = ET.parse(addon_xml_path)
    root = tree.getroot()
    return root.attrib["id"], root.attrib["version"]


def zip_addon(addon_id: str, src_dir: str, dest_dir: str, version: str) -> str:
    os.makedirs(dest_dir, exist_ok=True)
    zip_name = f"{addon_id}-{version}.zip"
    zip_path = os.path.join(dest_dir, zip_name)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, filenames in os.walk(src_dir):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE and d != "__pycache__"]
            for filename in filenames:
                if filename.endswith(".pyc"):
                    continue
                full_path = os.path.join(dirpath, filename)
                rel_to_parent = os.path.relpath(full_path, os.path.dirname(src_dir))
                if _should_exclude(rel_to_parent):
                    continue
                zf.write(full_path, rel_to_parent)

    print(f"  ZIP: {zip_path}")
    return zip_path


def build_addons_xml(addon_xml_paths: list[str]) -> bytes:
    lines = [b'<?xml version="1.0" encoding="UTF-8"?>', b"<addons>"]
    for path in addon_xml_paths:
        tree = ET.parse(path)
        raw = ET.tostring(tree.getroot(), encoding="utf-8")
        lines.append(b"  " + raw)
    lines.append(b"</addons>")
    return b"\n".join(lines) + b"\n"


def write_repository_addon(repo_addon_dir: str, base_url: str) -> str:
    os.makedirs(repo_addon_dir, exist_ok=True)
    repo_addon_xml = os.path.join(repo_addon_dir, "addon.xml")
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<addon id="repository.tvstreamcz" name="TVStreamCZ Repository" version="{REPO_ADDON_VERSION}"
       provider-name="daker52">
  <extension point="xbmc.addon.repository" name="TVStreamCZ Repository">
    <dir>
      <info compressed="false">{base_url}addons.xml</info>
      <checksum>{base_url}addons.xml.md5</checksum>
      <datadir zip="true">{base_url}</datadir>
    </dir>
  </extension>
  <extension point="xbmc.addon.metadata">
    <summary lang="cs_CZ">Repozitář doplňků TVStreamCZ</summary>
    <summary lang="en_GB">TVStreamCZ add-ons repository</summary>
    <description lang="cs_CZ">Instalace a aktualizace doplňků TVStreamCZ a YTS-Subs CZ pro Kodi.</description>
    <description lang="en_GB">Install and update TVStreamCZ and YTS-Subs CZ add-ons for Kodi.</description>
    <platform>all</platform>
  </extension>
</addon>
"""
    with open(repo_addon_xml, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    return repo_addon_xml


def discover_extra_addons() -> list[tuple[str, str]]:
    """Volitelné doplňky ve stejné nadřazené složce (např. Roaming addons)."""
    candidates = []
    parent = os.path.dirname(ROOT)
    for addon_id, folder in (
        ("service.subtitles.ytssubscz", "service.subtitles.ytssubscz"),
    ):
        src = os.path.join(parent, folder)
        xml_path = os.path.join(src, "addon.xml")
        if os.path.isfile(xml_path):
            candidates.append((addon_id, src))
    return candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Kodi repository in repo/")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("KODI_REPO_BASE_URL", DEFAULT_BASE_URL),
        help="Public HTTP(S) URL of repo/ folder, must end with /",
    )
    args = parser.parse_args()
    base_url = args.base_url.strip()
    if not base_url.endswith("/"):
        base_url += "/"

    print("=== TVStreamCZ Kodi Repository ===\n")
    print(f"Base URL: {base_url}\n")

    if os.path.isdir(REPO_DIR):
        shutil.rmtree(REPO_DIR)
    os.makedirs(REPO_DIR)

    addon_xml_paths: list[str] = []

    # --- plugin.video.tvstreamcz ---
    plugin_id = "plugin.video.tvstreamcz"
    plugin_xml = os.path.join(ROOT, "addon.xml")
    _, plugin_ver = read_addon_meta(plugin_xml)
    plugin_repo_dir = os.path.join(REPO_DIR, plugin_id)
    print(f"[1] {plugin_id} v{plugin_ver}")
    os.makedirs(plugin_repo_dir, exist_ok=True)
    zip_addon(plugin_id, ROOT, REPO_DIR, plugin_ver)
    shutil.copy2(plugin_xml, os.path.join(plugin_repo_dir, "addon.xml"))
    addon_xml_paths.append(os.path.join(plugin_repo_dir, "addon.xml"))

    # --- volitelné doplňky (YTS-Subs CZ vedle v addons/) ---
    for addon_id, src_dir in discover_extra_addons():
        addon_xml = os.path.join(src_dir, "addon.xml")
        _, version = read_addon_meta(addon_xml)
        dest = os.path.join(REPO_DIR, addon_id)
        print(f"[+] {addon_id} v{version}")
        os.makedirs(dest, exist_ok=True)
        zip_addon(addon_id, src_dir, REPO_DIR, version)
        shutil.copy2(addon_xml, os.path.join(dest, "addon.xml"))
        addon_xml_paths.append(os.path.join(dest, "addon.xml"))

    # --- repository.tvstreamcz ---
    repo_id = "repository.tvstreamcz"
    repo_addon_dir = os.path.join(REPO_DIR, repo_id)
    print(f"\n[2] {repo_id} v{REPO_ADDON_VERSION}")
    repo_addon_xml = write_repository_addon(repo_addon_dir, base_url)
    zip_addon(repo_id, repo_addon_dir, REPO_DIR, REPO_ADDON_VERSION)
    addon_xml_paths.append(repo_addon_xml)

    # --- addons.xml + md5 ---
    print("\n[3] addons.xml")
    addons_xml_bytes = build_addons_xml(addon_xml_paths)
    addons_xml_path = os.path.join(REPO_DIR, "addons.xml")
    with open(addons_xml_path, "wb") as handle:
        handle.write(addons_xml_bytes)

    addons_md5 = hashlib.md5(addons_xml_bytes).hexdigest()
    with open(os.path.join(REPO_DIR, "addons.xml.md5"), "wb") as handle:
        handle.write(addons_md5.encode("ascii"))

    print(f"  MD5: {addons_md5}")

    # Návod pro Kodi
    index_path = os.path.join(REPO_DIR, "index.html")
    with open(index_path, "w", encoding="utf-8") as handle:
        handle.write(
            f"""<!DOCTYPE html>
<html lang="cs"><head><meta charset="utf-8"><title>TVStreamCZ Kodi Repo</title></head>
<body>
<h1>TVStreamCZ Kodi Repository</h1>
<p>URL zdroje pro Kodi: <code>{base_url}</code></p>
<ol>
<li>Nastavení → Správce souborů → Přidat zdroj → výše uvedená URL</li>
<li>Doplňky → ikona krabice → Instalovat ze souboru → zdroj TVStreamCZ →
<code>repository.tvstreamcz-{REPO_ADDON_VERSION}.zip</code></li>
<li>Doplňky → Instalovat z repozitáře → TVStreamCZ Repository</li>
</ol>
</body></html>
"""
        )

    print("\n=== Hotovo ===")
    print(f"Složka: {REPO_DIR}")
    print("\n--- Instalace v Kodi ---")
    print("1. Nastavení → Správce souborů → Přidat zdroj")
    print(f"   Protokol: HTTP(s)   URL: {base_url}")
    print("   Název: TVStreamCZ (libovolný)")
    print("2. Doplňky → Instalovat ze souboru (ZIP) → Procházet → TVStreamCZ")
    print(f"   → repository.tvstreamcz-{REPO_ADDON_VERSION}.zip")
    print("3. Doplňky → Instalovat z repozitáře → TVStreamCZ Repository")
    print("   → Video doplňky / Služby / Titulky podle dopňku")
    print("\nPro GitHub: commit + push složky repo/, pak použijte výše uvedenou URL.")


if __name__ == "__main__":
    main()
