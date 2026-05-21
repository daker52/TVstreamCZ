# -*- coding: utf-8 -*-
"""
Sestaví Kodi repozitář do složky repo/ a kopii pro GitHub Pages (docs/repo/).

Použití:
    python build_repo.py
    python build_repo.py --base-url https://daker52.github.io/TVstreamCZ/repo/

Po pushi zapněte GitHub Pages: Settings → Pages → main, folder /docs
V Kodi použijte Pages URL (ne raw.githubusercontent.com).
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

# GitHub Pages umí výpis složky pro Kodi; raw.githubusercontent.com ne (Unable to connect).
DEFAULT_BASE_URL = "https://daker52.github.io/TVstreamCZ/repo/"
RAW_BASE_URL = "https://raw.githubusercontent.com/daker52/TVstreamCZ/main/repo/"

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.join(ROOT, "repo")
DOCS_REPO_DIR = os.path.join(ROOT, "docs", "repo")
REPO_ADDON_VERSION = "1.0.2"
# Stahování doplňků přes raw (spolehlivé na TV); Pages jen pro procházení složky v Kodi.
REPO_META_BASE_URL = RAW_BASE_URL

EXCLUDE = {
    ".git", ".gitignore", ".venv", "venv", "env", "repo", "docs", "__pycache__",
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


def write_kodi_index_html(target_dir: str, base_url: str) -> None:
    """HTML výpis souborů ve formátu, který Kodi umí procházet."""
    entries = []
    for name in sorted(os.listdir(target_dir)):
        full = os.path.join(target_dir, name)
        if os.path.isfile(full):
            entries.append(name)
    lines = ['<a href="../">../</a>']
    for name in entries:
        lines.append(f'<a href="{name}">{name}</a>')
    pre_block = "\n".join(lines)
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Index of /repo/</title></head>
<body><h1>TVStreamCZ Kodi Repository</h1>
<p>URL pro Kodi: <code>{base_url}</code></p>
<pre>
{pre_block}
</pre>
</body></html>
"""
    with open(os.path.join(target_dir, "index.html"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(html)
    print(f"  index.html ({len(entries)} souborů)")


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
    parser = argparse.ArgumentParser(description="Build Kodi repository in repo/ and docs/repo/")
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
    repo_addon_xml = write_repository_addon(repo_addon_dir, REPO_META_BASE_URL)
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

    write_kodi_index_html(REPO_DIR, base_url)

    # Kopie pro GitHub Pages (docs/repo/) – Kodi umí procházet tuto URL
    print("\n[4] GitHub Pages → docs/repo/")
    if os.path.isdir(os.path.join(ROOT, "docs")):
        shutil.rmtree(os.path.join(ROOT, "docs"))
    os.makedirs(DOCS_REPO_DIR, exist_ok=True)
    for name in os.listdir(REPO_DIR):
        src = os.path.join(REPO_DIR, name)
        dst = os.path.join(DOCS_REPO_DIR, name)
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
    with open(os.path.join(ROOT, "docs", ".nojekyll"), "w", encoding="utf-8") as handle:
        handle.write("")
    pages_url = DEFAULT_BASE_URL
    write_kodi_index_html(DOCS_REPO_DIR, pages_url)

    print("\n=== Hotovo ===")
    print(f"Složka repo/:  {REPO_DIR}")
    print(f"Složka Pages: {DOCS_REPO_DIR}")
    print("\n--- Instalace v Kodi (použijte GitHub Pages URL) ---")
    print("1. GitHub → Settings → Pages → Source: main, folder /docs")
    print("2. Nastavení → Správce souborů → Přidat zdroj")
    print(f"   URL: {pages_url}")
    print("   (U raw.githubusercontent.com Kodi ukáže Unable to connect – to je normální.)")
    print("3. Doplňky → Instalovat ze souboru → TVStreamCZ →")
    print(f"   repository.tvstreamcz-{REPO_ADDON_VERSION}.zip")
    print("4. Doplňky → Instalovat z repozitáře → TVStreamCZ Repository")
    print(f"\nPřímý odkaz na repozitář (ZIP): {RAW_BASE_URL}repository.tvstreamcz-{REPO_ADDON_VERSION}.zip")


if __name__ == "__main__":
    main()
