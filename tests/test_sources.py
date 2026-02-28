from transfer.sources import detect_source, SourceType

def test_detect_google_drive_file():
    url = "https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms/view"
    assert detect_source(url) == SourceType.GOOGLE_DRIVE

def test_detect_google_drive_folder():
    url = "https://drive.google.com/drive/folders/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74Og"
    assert detect_source(url) == SourceType.GOOGLE_DRIVE

def test_detect_dropbox():
    url = "https://www.dropbox.com/s/abc123/myfile.tif?dl=0"
    assert detect_source(url) == SourceType.DROPBOX

def test_detect_dropbox_folder():
    url = "https://www.dropbox.com/sh/abc123/AABcdef/folder"
    assert detect_source(url) == SourceType.DROPBOX

def test_detect_onedrive():
    url = "https://1drv.ms/u/s!Abc123"
    assert detect_source(url) == SourceType.ONEDRIVE

def test_detect_sharepoint():
    url = "https://contoso.sharepoint.com/sites/team/Shared%20Documents/order.tif"
    assert detect_source(url) == SourceType.ONEDRIVE

def test_detect_unknown():
    url = "https://example.com/file.tif"
    assert detect_source(url) is None


import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from transfer.sources.gdrive import GoogleDriveDownloader

@pytest.fixture
def gdrive():
    return GoogleDriveDownloader()

def test_extract_file_id_from_view_url(gdrive):
    url = "https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms/view"
    assert gdrive.extract_id(url) == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms"

def test_extract_folder_id(gdrive):
    url = "https://drive.google.com/drive/folders/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74Og"
    fid, is_folder = gdrive.extract_id_and_type(url)
    assert fid == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74Og"
    assert is_folder is True

def test_extract_file_id_and_type(gdrive):
    url = "https://drive.google.com/file/d/ABC123/view"
    fid, is_folder = gdrive.extract_id_and_type(url)
    assert fid == "ABC123"
    assert is_folder is False

async def test_download_file_calls_gdown(gdrive, tmp_path):
    with patch("transfer.sources.gdrive.gdown.download") as mock_dl:
        mock_dl.return_value = str(tmp_path / "file.tif")
        paths = await gdrive.download("https://drive.google.com/file/d/ABC/view", tmp_path)
        assert len(paths) == 1
        mock_dl.assert_called_once()
