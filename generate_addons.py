#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generator pro addons.xml - aktualizován pro TVStreamCZ repozitář
"""

import os
import hashlib
import xml.etree.ElementTree as ET
from xml.dom import minidom

def generate_addons_xml():
    """Generuje addons.xml ze všech addon.xml souborů v repozitáři."""
    
    print("🔨 Generuji addons.xml pro TVStreamCZ repozitář...")
    
    # Root element
    root = ET.Element('addons')
    
    # Seznam addonů k zahrnutí
    addons_to_include = []
    
    # 1. Repository addon (pokud existuje)
    if os.path.exists('addon.xml'):
        addons_to_include.append(('repository.tvstreamcz', 'addon.xml'))
    
    # 2. Plugin addon
    plugin_path = 'plugin.video.tvstreamcz/addon.xml'
    if os.path.exists(plugin_path):
        addons_to_include.append(('plugin.video.tvstreamcz', plugin_path))
    
    # 3. Automatické hledání dalších addonů
    for item in os.listdir('.'):
        if os.path.isdir(item) and item.startswith(('plugin.', 'script.', 'skin.', 'service.')):
            addon_xml_path = os.path.join(item, 'addon.xml')
            if os.path.exists(addon_xml_path):
                addons_to_include.append((item, addon_xml_path))
    
    # Odstraň duplicity
    addons_to_include = list(dict.fromkeys(addons_to_include))
    
    print(f"Nalezeno {len(addons_to_include)} addonů:")
    
    # Zpracuj každý addon
    for addon_id, addon_xml_path in addons_to_include:
        try:
            # Načti addon.xml
            tree = ET.parse(addon_xml_path)
            addon_element = tree.getroot()
            
            # Přidej do root
            root.append(addon_element)
            
            real_addon_id = addon_element.get('id', addon_id)
            addon_version = addon_element.get('version', 'unknown')
            addon_name = addon_element.get('name', real_addon_id)
            
            print(f"  ✅ {real_addon_id} v{addon_version} ({addon_name})")
            
        except Exception as e:
            print(f"  ❌ Chyba při načítání {addon_xml_path}: {e}")
    
    # Vytvoř krásně formátovaný XML
    rough_string = ET.tostring(root, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="  ", encoding='utf-8').decode('utf-8')
    
    # Odstraň prázdné řádky a xml deklaraci (přidáme vlastní)
    lines = [line for line in pretty_xml.split('\n') if line.strip()]
    if lines and lines[0].startswith('<?xml'):
        lines = lines[1:]  # Odstraň auto-generovanou XML deklaraci
    
    # Přidej vlastní XML deklaraci
    final_lines = ['<?xml version="1.0" encoding="UTF-8"?>'] + lines
    final_xml = '\n'.join(final_lines)
    
    # Ulož addons.xml
    with open('addons.xml', 'w', encoding='utf-8') as f:
        f.write(final_xml)
    
    # Vytvoř MD5 hash
    md5_hash = hashlib.md5(final_xml.encode('utf-8')).hexdigest()
    with open('addons.xml.md5', 'w') as f:
        f.write(md5_hash)
    
    print(f"📄 addons.xml vytvořen ({len(final_lines)} řádků)")
    print(f"🔒 MD5 hash: {md5_hash}")
    
    return True

def create_github_workflow():
    """Vytvoří GitHub Actions workflow."""
    
    os.makedirs('.github/workflows', exist_ok=True)
    
    workflow_content = """name: Build TVStreamCZ Repository

on:
  push:
    branches: [ main ]
    paths: 
      - 'plugin.video.tvstreamcz/**'
      - 'addon.xml'
      - 'generate_addons.py'
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout repository
      uses: actions/checkout@v4
      
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Generate addons.xml
      run: |
        python generate_addons.py
    
    - name: Commit updated files
      run: |
        git config --local user.email "action@github.com"
        git config --local user.name "GitHub Action"
        git add addons.xml addons.xml.md5
        if ! git diff --staged --quiet; then
          git commit -m "Auto-update addons.xml [skip ci]"
          git push
        else
          echo "No changes to commit"
        fi
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
"""
    
    with open('.github/workflows/build.yml', 'w', encoding='utf-8') as f:
        f.write(workflow_content)
    
    print("✅ GitHub Actions workflow vytvořen")

if __name__ == "__main__":
    print("🚀 TVStreamCZ Repository Generator")
    print("=" * 50)
    print(f"📂 Pracovní složka: {os.getcwd()}")
    
    generate_addons_xml()
    create_github_workflow()
    
    print("\n🎯 NÁVOD PRO NAHRÁNI NA GITHUB:")
    print("1. Přejmenuj repository_addon.xml na addon.xml")
    print("2. Přidej ikony (icon.png, fanart.jpg)")
    print("3. Nahraj vše na GitHub:")
    print("   git add .")
    print("   git commit -m 'Setup Kodi repository'")
    print("   git push")
    print("")
    print("🔗 URL PRO INSTALACI DO KODI:")
    print("https://github.com/daker52/TVstreamCZ/archive/refs/heads/main.zip")
    print("")
    print("📦 Repository je připraven!")