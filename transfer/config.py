import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Settings:
    lark_app_id: str = field(default_factory=lambda: os.environ["LARK_APP_ID"])
    lark_app_secret: str = field(default_factory=lambda: os.environ["LARK_APP_SECRET"])
    lark_root_folder_token: str = field(default_factory=lambda: os.environ["LARK_ROOT_FOLDER_TOKEN"])
    google_api_key: str = field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))
    dropbox_app_key: str = field(default_factory=lambda: os.getenv("DROPBOX_APP_KEY", ""))
    dropbox_app_secret: str = field(default_factory=lambda: os.getenv("DROPBOX_APP_SECRET", ""))
    dropbox_refresh_token: str = field(default_factory=lambda: os.getenv("DROPBOX_REFRESH_TOKEN", ""))
    microsoft_client_id: str = field(default_factory=lambda: os.getenv("MICROSOFT_CLIENT_ID", ""))
    microsoft_client_secret: str = field(default_factory=lambda: os.getenv("MICROSOFT_CLIENT_SECRET", ""))
    microsoft_tenant_id: str = field(default_factory=lambda: os.getenv("MICROSOFT_TENANT_ID", ""))
    temp_dir: str = field(default_factory=lambda: os.getenv("TEMP_DIR", "/tmp/transfer-jobs"))
    host: str = field(default_factory=lambda: os.getenv("HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))

try:
    settings = Settings()
except KeyError:
    settings = None  # type: ignore  # populated at runtime via .env
