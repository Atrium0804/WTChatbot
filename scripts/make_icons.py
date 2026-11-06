"""Genereer de PWA-iconen voor de chat-UI uit app/static/wielie.jpg.

Output (wordt gecommit): app/static/icons/
  - icon-192.png            manifest-icon (purpose "any")
  - icon-512.png            manifest-icon (purpose "any")
  - icon-maskable-512.png   maskable: mascotte binnen de 80%-veilige zone op clubblauw
  - apple-touch-icon.png    180x180, ondoorzichtig (iOS rondt zelf de hoeken af)
  - favicon-32.png          browser-tabblad

Run vanuit de repo-root:  python scripts/make_icons.py
Vereist Pillow (zie requirements.txt). Alleen regenereren als wielie.jpg wijzigt.
"""

from pathlib import Path

from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE = BASE_DIR / "app" / "static" / "wielie.jpg"
OUTPUT_DIR = BASE_DIR / "app" / "static" / "icons"

ACCENT = (0x03, 0x3E, 0xC2)  # --accent uit app/static/index.html
MASKABLE_SAFE_ZONE = 0.8  # Android maskable: content binnen 80% van de diameter


def resize_cover(img: Image.Image, size: int) -> Image.Image:
    """Schaal het vierkante bronbeeld om een size x size vlak volledig te vullen."""
    return img.resize((size, size), Image.LANCZOS)


def make_maskable(img: Image.Image, size: int, background: tuple[int, int, int]) -> Image.Image:
    """Mascotte gecentreerd binnen de veilige zone op een effen achtergrond."""
    canvas = Image.new("RGB", (size, size), background)
    content = resize_cover(img, int(size * MASKABLE_SAFE_ZONE))
    offset = (size - content.width) // 2
    canvas.paste(content, (offset, offset))
    return canvas


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(f"Bronafbeelding niet gevonden: {SOURCE}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    src = Image.open(SOURCE).convert("RGB")

    outputs = {
        "icon-192.png": resize_cover(src, 192),
        "icon-512.png": resize_cover(src, 512),
        "icon-maskable-512.png": make_maskable(src, 512, ACCENT),
        "apple-touch-icon.png": resize_cover(src, 180),
        "favicon-32.png": resize_cover(src, 32),
    }
    for name, img in outputs.items():
        img.save(OUTPUT_DIR / name, "PNG")
        print(f"  {OUTPUT_DIR / name} ({img.width}x{img.height})")


if __name__ == "__main__":
    main()
