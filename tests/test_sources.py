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
