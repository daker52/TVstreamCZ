#!/usr/bin/env python3
"""Create a properly structured ZIP file for Kodi addon installation."""

import zipfile
import os
from pathlib import Path

def create_kodi_zip():
    """Create ZIP file with correct structure for Kodi addon."""
    zip_name = "TVStreamCZ-KODI-INSTALL.zip"
    
    # Remove existing zip
    if os.path.exists(zip_name):
        os.remove(zip_name)
    
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add root files
        root_files = ['addon.py', 'addon.xml', 'README.md']
        for file in root_files:
            if os.path.exists(file):
                zf.write(file, file)
                print(f"Added: {file}")
        
        # Add resources directory
        resources_dir = Path('resources')
        if resources_dir.exists():
            for file_path in resources_dir.rglob('*'):
                if file_path.is_file():
                    # Use forward slashes for ZIP paths (cross-platform compatibility)
                    arc_path = str(file_path).replace('\\', '/')
                    zf.write(file_path, arc_path)
                    print(f"Added: {arc_path}")
    
    print(f"\nZIP file created: {zip_name}")
    
    # Verify ZIP structure
    print("\nZIP contents:")
    with zipfile.ZipFile(zip_name, 'r') as zf:
        for name in sorted(zf.namelist()):
            print(f"  {name}")

if __name__ == "__main__":
    create_kodi_zip()