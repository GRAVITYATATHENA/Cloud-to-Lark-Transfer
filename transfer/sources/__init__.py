from enum import Enum
from urllib.parse import urlparse

class SourceType(Enum):
    GOOGLE_DRIVE = "google_drive"
    DROPBOX = "dropbox"
    ONEDRIVE = "onedrive"

def detect_source(url: str) -> SourceType | None:
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if "drive.google.com" in host or "docs.google.com" in host:
        return SourceType.GOOGLE_DRIVE
    if "dropbox.com" in host:
        return SourceType.DROPBOX
    if "1drv.ms" in host or "onedrive.live.com" in host or "sharepoint.com" in host:
        return SourceType.ONEDRIVE
    return None
