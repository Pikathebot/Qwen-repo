import os
from pathlib import Path
from PIL import Image, ImageDraw

def generate_ico():
    assets_dir = Path("d:/JARVIS/desktop/assets")
    assets_dir.mkdir(parents=True, exist_ok=True)
    ico_path = assets_dir / "jarvis.ico"
    png_path = assets_dir / "jarvis.png"

    # Create high-res 256x256 icon
    size = 256
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Outer circle cyan/blue
    draw.ellipse([(12, 12), (size - 12, size - 12)], outline=(0, 180, 255, 255), width=16)
    # Inner circle
    draw.ellipse([(48, 48), (size - 48, size - 48)], fill=(10, 30, 60, 240), outline=(0, 220, 255, 255), width=8)
    # Glowing center core
    draw.ellipse([(88, 88), (size - 88, size - 88)], fill=(0, 210, 255, 255))
    # Bright center dot
    draw.ellipse([(112, 112), (size - 112, size - 112)], fill=(255, 255, 255, 255))

    image.save(png_path, format="PNG")
    image.save(ico_path, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print(f"Generated {ico_path} and {png_path}")

if __name__ == "__main__":
    generate_ico()
