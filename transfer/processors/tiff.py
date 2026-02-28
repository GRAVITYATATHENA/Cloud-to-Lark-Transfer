from pathlib import Path
from PIL import Image
import asyncio

async def flatten_tiff(path: Path) -> Path:
    """
    Flatten a TIFF file by compositing any alpha channel onto a white background
    and converting to RGB. Runs in a thread pool to avoid blocking the event loop.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _flatten_sync, path)

def _flatten_sync(path: Path) -> Path:
    img = Image.open(path)
    if img.mode == "RGB":
        # Already flat — save a copy so the pipeline always returns a new file
        out_path = path.with_name(path.stem + "_flat" + path.suffix)
        img.save(out_path, format="TIFF", compression="tiff_lzw")
        return out_path

    # Composite onto white background
    background = Image.new("RGB", img.size, (255, 255, 255))
    if img.mode in ("RGBA", "LA", "PA"):
        background.paste(img, mask=img.split()[-1])  # use alpha as mask
    else:
        background.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])

    out_path = path.with_name(path.stem + "_flat" + path.suffix)
    background.save(out_path, format="TIFF", compression="tiff_lzw")
    return out_path
