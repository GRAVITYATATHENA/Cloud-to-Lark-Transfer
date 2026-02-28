import pytest
from pathlib import Path
from transfer.processors import ProcessingPipeline

async def test_pipeline_passes_through_unknown_extension(tmp_path):
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"PDF content")
    pipeline = ProcessingPipeline()
    result = await pipeline.process(test_file)
    assert result == test_file

from PIL import Image

def make_tiff_with_alpha(path: Path):
    """Create a simple RGBA TIFF to simulate a layered file."""
    img = Image.new("RGBA", (10, 10), (255, 0, 0, 128))
    img.save(path, format="TIFF")

async def test_flatten_tiff_removes_alpha(tmp_path):
    from transfer.processors.tiff import flatten_tiff
    src = tmp_path / "layered.tif"
    make_tiff_with_alpha(src)

    result = await flatten_tiff(src)

    out_img = Image.open(result)
    assert out_img.mode == "RGB"

async def test_flatten_tiff_output_path(tmp_path):
    from transfer.processors.tiff import flatten_tiff
    src = tmp_path / "input.tif"
    make_tiff_with_alpha(src)

    result = await flatten_tiff(src)
    assert result.parent == src.parent
    assert result != src

async def test_flatten_tiff_rgb_passthrough(tmp_path):
    from transfer.processors.tiff import flatten_tiff
    src = tmp_path / "flat.tif"
    img = Image.new("RGB", (10, 10), (100, 100, 100))
    img.save(src, format="TIFF")

    result = await flatten_tiff(src)
    out_img = Image.open(result)
    assert out_img.mode == "RGB"

async def test_pipeline_calls_processor_for_tiff(tmp_path, monkeypatch):
    from transfer.processors import ProcessingPipeline
    test_file = tmp_path / "test.tif"
    test_file.write_bytes(b"fake tiff")
    output_file = tmp_path / "test_processed.tif"
    output_file.write_bytes(b"processed")

    async def fake_process(path):
        return output_file

    pipeline = ProcessingPipeline()
    monkeypatch.setitem(pipeline.processors, ".tif", fake_process)
    result = await pipeline.process(test_file)
    assert result == output_file
