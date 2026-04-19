"""
Convert absolute paths to relative paths in HTML files
for Vite build compatibility
"""

import re
from pathlib import Path

FRONTEND_DIR = Path(__file__).parent


def convert_paths_in_file(filepath):
    """Convert /frontend/ paths to relative ./ paths"""
    print(f"📄 Processing: {filepath.name}")

    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    original = content

    # Convert /frontend/css/ to ./css/
    content = re.sub(r'href="/frontend/css/', 'href="./css/', content)

    # Convert /frontend/js/ to ./js/
    content = re.sub(r'src="/frontend/js/', 'src="./js/', content)

    # Convert /frontend/libs/ to ./libs/
    content = re.sub(r'src="/frontend/libs/', 'src="./libs/', content)

    # Convert /frontend/images/ to ./images/
    content = re.sub(r'src="/frontend/images/', 'src="./images/', content)
    content = re.sub(r'href="/frontend/images/', 'href="./images/', content)

    if content != original:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        count = original.count("/frontend/")
        print(f"  ✅ Converted {count} paths to relative")
        return count
    else:
        print("  No changes needed")
        return 0


def main():
    print("🔧 Converting Absolute Paths to Relative Paths")
    print("=" * 50)

    html_files = list(FRONTEND_DIR.glob("*.html"))
    print(f"Found {len(html_files)} HTML files\n")

    total_converted = 0
    files_changed = 0

    for filepath in html_files:
        count = convert_paths_in_file(filepath)
        total_converted += count
        if count > 0:
            files_changed += 1

    print("\n" + "=" * 50)
    print(f"✅ Converted {total_converted} paths in {files_changed} files")


if __name__ == "__main__":
    main()
