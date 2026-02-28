import base64
from pathlib import Path
import httpx

class OneDriveDownloader:

    def __init__(self, client_id: str, client_secret: str, tenant_id: str = "common"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self._token: str | None = None

    def encode_sharing_url(self, url: str) -> str:
        """Encode a sharing URL as a base64url string for the Graph API."""
        b64 = base64.urlsafe_b64encode(url.encode()).rstrip(b"=").decode()
        return f"u!{b64}"

    async def _get_token(self) -> str:
        if self._token:
            return self._token
        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        async with httpx.AsyncClient() as client:
            resp = await client.post(token_url, data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "https://graph.microsoft.com/.default",
            })
            resp.raise_for_status()
            self._token = resp.json()["access_token"]
            return self._token

    async def download(self, url: str, dest_dir: Path) -> list[Path]:
        dest_dir.mkdir(parents=True, exist_ok=True)
        token = await self._get_token()
        encoded = self.encode_sharing_url(url)
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient(follow_redirects=True, timeout=None) as client:
            meta_resp = await client.get(
                f"https://graph.microsoft.com/v1.0/shares/{encoded}/driveItem",
                headers=headers,
            )
            meta_resp.raise_for_status()
            meta = meta_resp.json()

            if "folder" in meta:
                return await self._download_folder(meta, dest_dir, client, headers)

            download_url = meta.get("@microsoft.graph.downloadUrl")
            filename = meta.get("name", "download")
            dest_path = dest_dir / filename

            async with client.stream("GET", download_url) as resp:
                resp.raise_for_status()
                with open(dest_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(8 * 1024 * 1024):
                        f.write(chunk)

            return [dest_path]

    async def _download_folder(self, folder_meta: dict, dest_dir: Path,
                                client: httpx.AsyncClient, headers: dict) -> list[Path]:
        children_url = folder_meta.get("@microsoft.graph.downloadUrl") or \
                       f"https://graph.microsoft.com/v1.0/drives/{folder_meta['parentReference']['driveId']}" \
                       f"/items/{folder_meta['id']}/children"
        resp = await client.get(children_url, headers=headers)
        resp.raise_for_status()
        items = resp.json().get("value", [])
        paths = []
        for item in items:
            if "file" in item:
                dl_url = item.get("@microsoft.graph.downloadUrl")
                dest_path = dest_dir / item["name"]
                async with client.stream("GET", dl_url) as r:
                    r.raise_for_status()
                    with open(dest_path, "wb") as f:
                        async for chunk in r.aiter_bytes(8 * 1024 * 1024):
                            f.write(chunk)
                paths.append(dest_path)
        return paths
