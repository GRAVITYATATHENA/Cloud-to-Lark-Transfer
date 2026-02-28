import time
from pathlib import Path
import httpx

LARK_BASE = "https://open.larksuite.com/open-apis"
CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB chunks for large file upload

class LarkClient:
    def __init__(self, app_id: str, app_secret: str, root_folder_token: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.root_folder_token = root_folder_token
        self._token: str | None = None
        self._token_expiry: float = 0

    async def get_access_token(self) -> str:
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{LARK_BASE}/auth/v3/tenant_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
            )
            resp.raise_for_status()
            data = resp.json()
            if data["code"] != 0:
                raise RuntimeError(f"LARK auth failed: {data}")
            self._token = data["tenant_access_token"]
            self._token_expiry = time.time() + data["expire"]
            return self._token

    async def _headers(self) -> dict:
        return {"Authorization": f"Bearer {await self.get_access_token()}"}

    async def list_folder(self, folder_token: str) -> list[dict]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{LARK_BASE}/drive/v1/files",
                params={"folder_token": folder_token},
                headers=await self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            if data["code"] != 0:
                raise RuntimeError(f"LARK list folder failed: {data}")
            return data["data"]["files"]

    async def create_folder(self, parent_token: str, name: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{LARK_BASE}/drive/v1/files/create_folder",
                json={"name": name, "folder_token": parent_token},
                headers=await self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            if data["code"] != 0:
                raise RuntimeError(f"LARK create folder failed: {data}")
            return data["data"]

    async def ensure_folder(self, parent_token: str, name: str) -> str:
        """Return token of named subfolder, creating it if it doesn't exist."""
        items = await self.list_folder(parent_token)
        for item in items:
            if item.get("name") == name and item.get("type") == "folder":
                return item["token"]
        result = await self.create_folder(parent_token, name)
        return result["token"]

    async def upload_file(self, folder_token: str, file_path: Path) -> str:
        """Upload a file to a LARK folder. Returns the file token."""
        size = file_path.stat().st_size
        if size <= 20 * 1024 * 1024:
            return await self._upload_small(folder_token, file_path)
        return await self._upload_large(folder_token, file_path, size)

    async def _upload_small(self, folder_token: str, file_path: Path) -> str:
        headers = await self._headers()
        async with httpx.AsyncClient() as client:
            with open(file_path, "rb") as f:
                resp = await client.post(
                    f"{LARK_BASE}/drive/v1/medias/upload_all",
                    headers=headers,
                    data={
                        "file_name": file_path.name,
                        "parent_type": "explorer",
                        "parent_node": folder_token,
                        "size": str(file_path.stat().st_size),
                    },
                    files={"file": (file_path.name, f, "application/octet-stream")},
                )
            resp.raise_for_status()
            data = resp.json()
            if data["code"] != 0:
                raise RuntimeError(f"LARK upload failed: {data}")
            return data["data"]["file_token"]

    async def _upload_large(self, folder_token: str, file_path: Path, size: int) -> str:
        headers = await self._headers()
        async with httpx.AsyncClient(timeout=None) as client:
            # Step 1: prepare
            prep = await client.post(
                f"{LARK_BASE}/drive/v1/medias/upload_prepare",
                headers=headers,
                json={
                    "file_name": file_path.name,
                    "parent_type": "explorer",
                    "parent_node": folder_token,
                    "size": size,
                    "block_size": CHUNK_SIZE,
                },
            )
            prep.raise_for_status()
            prep_data = prep.json()
            if prep_data["code"] != 0:
                raise RuntimeError(f"LARK upload_prepare failed: {prep_data}")
            upload_id = prep_data["data"]["upload_id"]
            block_num = prep_data["data"]["block_num"]

            # Step 2: upload parts
            with open(file_path, "rb") as f:
                for seq in range(block_num):
                    chunk = f.read(CHUNK_SIZE)
                    part_resp = await client.post(
                        f"{LARK_BASE}/drive/v1/medias/upload_part",
                        headers=headers,
                        data={"upload_id": upload_id, "seq": str(seq), "size": str(len(chunk))},
                        files={"file": (file_path.name, chunk, "application/octet-stream")},
                    )
                    part_resp.raise_for_status()
                    if part_resp.json()["code"] != 0:
                        raise RuntimeError(f"LARK upload_part failed: {part_resp.json()}")

            # Step 3: finish
            finish = await client.post(
                f"{LARK_BASE}/drive/v1/medias/upload_finish",
                headers=headers,
                json={"upload_id": upload_id, "block_num": block_num},
            )
            finish.raise_for_status()
            finish_data = finish.json()
            if finish_data["code"] != 0:
                raise RuntimeError(f"LARK upload_finish failed: {finish_data}")
            return finish_data["data"]["file_token"]
