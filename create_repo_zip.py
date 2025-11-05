#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vytváří ZIP soubor repozitáře pro Kodi instalaci
"""

import zipfile
import os

def create_repository_zip():
    """Vytvoří ZIP pouze s repository addon soubory."""
    
    zip_name = "repository.tvstreamcz-1.0.0.zip"
    
    print(f"🔧 Vytvářím {zip_name}...")
    
    # Soubory k zahrnutí do ZIP
    files_to_include = [
        ("addon.xml", "addon.xml"),  # Repository metadata
        ("icon.png", "icon.png"),    # Repository ikona
        ("fanart.png", "fanart.png") # Repository pozadí
    ]
    
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for local_file, zip_path in files_to_include:
            if os.path.exists(local_file):
                zipf.write(local_file, zip_path)
                print(f"  ✅ Přidán: {local_file} → {zip_path}")
            else:
                print(f"  ⚠️  Soubor nenalezen: {local_file}")
    
    file_size = os.path.getsize(zip_name) / 1024  # KB
    print(f"📦 {zip_name} vytvořen ({file_size:.1f} KB)")
    
    return zip_name

if __name__ == "__main__":
    print("🚀 Repository ZIP Generator")
    print("=" * 40)
    
    zip_file = create_repository_zip()
    
    print(f"""
🎯 POUŽITÍ:
1. Nahraj {zip_file} na GitHub Releases
2. V Kodi: Add-ons → Install from zip file
3. Zadej URL k release ZIP souboru

🔗 GitHub Release URL bude:
https://github.com/daker52/TVstreamCZ/releases/download/v1.0.0/{zip_file}
""")