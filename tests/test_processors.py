import pytest
from pathlib import Path
from transfer.processors import ProcessingPipeline

async def test_pipeline_passes_through_unknown_extension(tmp_path):
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"PDF content")
    pipeline = ProcessingPipeline()
    result = await pipeline.process(test_file)
    assert result == test_file

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
