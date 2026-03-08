# -*- coding: utf-8 -*-
"""
Builds the Kodi repository structure under repo/.

Run from the root of the addon directory:
    python build_repo.py

After running, upload repo/ to server – Kodi can then install from:
    http://194.182.80.24/kodi-repo/
"""

import hashlib
import os
import shutil
import sys
import zipfile
import xml.etree.ElementTree as ET

# Force UTF-8 output so Czech chars and arrows don't break on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# URL where the repo will be hosted (trailing slash required)
BASE_URL = "http://194.182.80.24/kodi-repo/"

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.join(ROOT, "repo")

# Files/folders to exclude from the plugin zip
EXCLUDE = {
    ".git", ".gitignore", ".venv", "venv", "env", "repo", "__pycache__",
    "build_repo.py",
    # debug / dev files
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
    "create_kodi_zip.py", "check_installation.py",
}


def _should_exclude(rel_path: str) -> bool:
    parts = rel_path.replace("\\", "/").split("/")
    for part in parts:
        if part in EXCLUDE or part == "__pycache__" or part.endswith(".pyc"):
            return True
    return False


def read_addon_version(addon_xml_path: str):
    tree = ET.parse(addon_xml_path)
    root = tree.getroot()
    return root.attrib.get("id"), root.attrib.get("version")


def zip_addon(addon_id: str, src_dir: str, dest_dir: str, version: str) -> str:
    """Zip *src_dir* into *dest_dir*/{addon_id}-{version}.zip."""
    os.makedirs(dest_dir, exist_ok=True)
    zip_name = f"{addon_id}-{version}.zip"
    zip_path = os.path.join(dest_dir, zip_name)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, filenames in os.walk(src_dir):
            # Prune excluded directories in-place
            dirnames[:] = [d for d in dirnames
                           if d not in EXCLUDE and d != "__pycache__"]
            for filename in filenames:
                if filename.endswith(".pyc"):
                    continue
                full_path = os.path.join(dirpath, filename)
                rel_to_parent = os.path.relpath(full_path, os.path.dirname(src_dir))
                if _should_exclude(rel_to_parent):
                    continue
                zf.write(full_path, rel_to_parent)

    print(f"  Created: {zip_path}")
    return zip_path


def build_addons_xml(addons_info: list) -> str:
    """Build addons.xml string from list of (addon_xml_path,) tuples."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<addons>"]
    for addon_xml_path in addons_info:
        tree = ET.parse(addon_xml_path)
        raw = ET.tostring(tree.getroot(), encoding="unicode")
        lines.append("  " + raw)
    lines.append("</addons>")
    return "\n".join(lines)


def md5_of(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def main():
    print("=== Building TVStreamCZ Kodi Repository ===\n")

    # ------------------------------------------------------------------ #
    # 1. Plugin addon zip
    # ------------------------------------------------------------------ #
    plugin_id = "plugin.video.tvstreamcz"
    plugin_xml = os.path.join(ROOT, "addon.xml")
    _, plugin_ver = read_addon_version(plugin_xml)

    plugin_repo_dir = os.path.join(REPO_DIR, plugin_id)
    print(f"[1] Zipping {plugin_id} v{plugin_ver} ...")
    zip_addon(plugin_id, ROOT, plugin_repo_dir, plugin_ver)

    # Copy addon.xml into repo dir (Kodi reads it for the listing)
    shutil.copy2(plugin_xml, os.path.join(plugin_repo_dir, "addon.xml"))
    print(f"  Copied addon.xml → repo/{plugin_id}/addon.xml")

    # ------------------------------------------------------------------ #
    # 2. Repository addon zip
    # ------------------------------------------------------------------ #
    repo_id = "repository.tvstreamcz"
    repo_ver = "1.0.0"
    repo_addon_dir = os.path.join(REPO_DIR, repo_id)
    os.makedirs(repo_addon_dir, exist_ok=True)

    # Write repo addon.xml (generated inline so it survives repo/ wipe)
    repo_addon_xml = os.path.join(repo_addon_dir, "addon.xml")
    repo_xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<addon id="repository.tvstreamcz" name="TVStreamCZ Repository" version="1.0.0"
       provider-name="daker52">
  <extension point="xbmc.addon.repository" name="TVStreamCZ Repository">
    <info compressed="false">{BASE_URL}addons.xml</info>
    <checksum>{BASE_URL}addons.xml.md5</checksum>
    <datadir zip="true">{BASE_URL}</datadir>
    <assets>
      <icon></icon>
    </assets>
  </extension>
  <extension point="xbmc.addon.metadata">
    <summary lang="cs">Repozitář pro addon TVStreamCZ</summary>
    <summary lang="en">Repository for TVStreamCZ addon</summary>
    <description lang="cs">Umožňuje instalaci a automatické aktualizace addonu plugin.video.tvstreamcz.</description>
    <description lang="en">Enables installation and automatic updates of plugin.video.tvstreamcz addon.</description>
    <platform>all</platform>
  </extension>
</addon>'''
    repo_xml_content = repo_xml_content.replace("{BASE_URL}", BASE_URL)
    with open(repo_addon_xml, "w", encoding="utf-8") as f:
        f.write(repo_xml_content)
    print(f"\n[2] Zipping {repo_id} v{repo_ver} ...")
    zip_addon(repo_id, repo_addon_dir, REPO_DIR, repo_ver)

    # ------------------------------------------------------------------ #
    # 3. addons.xml + md5
    # ------------------------------------------------------------------ #
    print("\n[3] Generating addons.xml ...")
    addons_xml_content = build_addons_xml([
        os.path.join(plugin_repo_dir, "addon.xml"),
        repo_addon_xml,
    ])

    addons_xml_path = os.path.join(REPO_DIR, "addons.xml")
    with open(addons_xml_path, "w", encoding="utf-8") as f:
        f.write(addons_xml_content)
    print(f"  Written: {addons_xml_path}")

    addons_md5 = md5_of(addons_xml_content)
    md5_path = os.path.join(REPO_DIR, "addons.xml.md5")
    with open(md5_path, "w", encoding="utf-8") as f:
        f.write(addons_md5)
    print(f"  Written: {md5_path}  ({addons_md5})")

    # ------------------------------------------------------------------ #
    # Done
    # ------------------------------------------------------------------ #
    print("\n=== Hotovo! ===")
    print(f"\nRepozitář je v: {REPO_DIR}")
    print("\nInstallace v Kodi:")
    print("  1. Nastavení → Správce souborů → Přidat zdroj")
    print(f"     URL: {BASE_URL}")
    print("     Název: TVStreamCZ")
    print("  2. Doplňky → Instalovat ze souboru ZIP → TVStreamCZ")
    print(f"     → repository.tvstreamcz-{repo_ver}.zip")
    print("  3. Doplňky → Instalovat z repozitáře → TVStreamCZ Repository")
    print(f"     → Video doplňky → TVStreamCZ")


if __name__ == "__main__":
    main()
