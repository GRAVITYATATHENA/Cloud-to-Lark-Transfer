import re
from pathlib import Path
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
import httpx

class DropboxDownloader:

    def make_direct_url(self, url: str) -> str:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query, keep_blank_values=True)
        qs["dl"] = ["1"]
        new_query = "&".join(f"{k}={v[0]}" for k, v in qs.items())
        return urlunparse(parsed._replace(query=new_query))

    def extract_filename(self, url: str) -> str:
        path = urlparse(url).path
        return path.split("/")[-1] or "download"

    async def download(self, url: str, dest_dir: Path) -> list[Path]:
        dest_dir.mkdir(parents=True, exist_ok=True)
        direct_url = self.make_direct_url(url)
        filename = self.extract_filename(url)
        dest_path = dest_dir / filename

        async with httpx.AsyncClient(follow_redirects=True, timeout=None) as client:
            async with client.stream("GET", direct_url) as response:
                response.raise_for_status()
                with open(dest_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8 * 1024 * 1024):
                        f.write(chunk)

        return [dest_path]
