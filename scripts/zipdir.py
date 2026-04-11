"""
zipdir.py — Cross-platform directory zipper used by deploy scripts.

Usage:
    python scripts/zipdir.py <source_dir> <output_zip>
"""
import sys
import os
import zipfile
from pathlib import Path

source = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()

with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(source):
        # Skip __pycache__ and .pyc files
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for file in files:
            if file.endswith(".pyc"):
                continue
            abs_path = Path(root) / file
            arcname = abs_path.relative_to(source)
            zf.write(abs_path, arcname)

size_kb = output.stat().st_size // 1024
print(f"Created {output} ({size_kb} KB, {len(zf.namelist())} files)")
