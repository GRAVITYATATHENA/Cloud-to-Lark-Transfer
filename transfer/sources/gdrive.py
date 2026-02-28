import re
from pathlib import Path
import gdown
from urllib.parse import urlparse, parse_qs

class GoogleDriveDownloader:

    def extract_id(self, url: str) -> str:
        # /file/d/{id}/view or /file/d/{id}
        m = re.search(r"/file/d/([^/?#]+)", url)
        if m:
            return m.group(1)
        # open?id={id}
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if "id" in qs:
            return qs["id"][0]
        raise ValueError(f"Cannot extract file ID from: {url}")

    def extract_id_and_type(self, url: str) -> tuple[str, bool]:
        # /drive/folders/{id}
        m = re.search(r"/drive/folders/([^/?#]+)", url)
        if m:
            return m.group(1), True
        return self.extract_id(url), False

    async def download(self, url: str, dest_dir: Path) -> list[Path]:
        dest_dir.mkdir(parents=True, exist_ok=True)
        file_id, is_folder = self.extract_id_and_type(url)

        if is_folder:
            output = str(dest_dir)
            gdown.download_folder(
                id=file_id,
                output=output,
                quiet=False,
                use_cookies=False,
            )
            return list(dest_dir.iterdir())
        else:
            output_path = str(dest_dir / f"{file_id}_download")
            result = gdown.download(id=file_id, output=output_path, quiet=False)
            return [Path(result)] if result else []
