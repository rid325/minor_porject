"""Signed Cloudinary operations for encrypted raw document assets."""

from hashlib import sha256
import os
import re
from time import time
from urllib.parse import unquote, urlsplit

import httpx


class CloudinaryStorageError(RuntimeError):
    pass


class CloudinaryStorage:
    def __init__(self):
        try:
            credentials = urlsplit(os.getenv("CLOUDINARY_URL", "").strip())
        except ValueError as exc:
            raise CloudinaryStorageError("Configure Cloudinary credentials on the server.") from exc
        cloud = credentials.hostname or ""
        if credentials.scheme != "cloudinary" or not re.fullmatch(r"[a-z0-9_-]+", cloud) or not (
            credentials.username and credentials.password
        ):
            raise CloudinaryStorageError("Configure Cloudinary credentials on the server.")
        self.endpoint = f"https://api.cloudinary.com/v1_1/{cloud}/raw"
        self.key = unquote(credentials.username)
        self.secret = unquote(credentials.password)

    def _signed(self, asset, **fields):
        params = {"public_id": asset, "timestamp": str(int(time())), "type": "authenticated", **fields}
        unsigned = "&".join(f"{key}={value}" for key, value in sorted(params.items()))
        signature = sha256((unsigned + self.secret).encode()).hexdigest()
        return {**params, "api_key": self.key, "signature": signature}

    def put(self, asset, encrypted):
        try:
            response = httpx.post(
                self.endpoint + "/upload", data=self._signed(asset, overwrite="false", backup="false"),
                files={"file": (asset.rsplit("/", 1)[-1], encrypted, "application/octet-stream")}, timeout=30,
            )
            response.raise_for_status()
            result = response.json()
            if result["public_id"] != asset or result["type"] != "authenticated" or result["resource_type"] != "raw":
                raise ValueError("Unexpected Cloudinary asset response.")
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise CloudinaryStorageError("Cloud storage could not save the document. Try again.") from exc

    def get(self, asset):
        try:
            response = httpx.get(
                self.endpoint + "/download",
                params=self._signed(asset, expires_at=str(int(time()) + 60)), timeout=30,
                follow_redirects=True,
            )
            response.raise_for_status()
            return response.content
        except httpx.HTTPError as exc:
            raise CloudinaryStorageError("Cloud storage could not read the document. Try again.") from exc

    def delete(self, asset):
        try:
            response = httpx.post(self.endpoint + "/destroy", data=self._signed(asset), timeout=30)
            response.raise_for_status()
            if response.json()["result"] not in {"ok", "not found"}:
                raise ValueError("Unexpected Cloudinary deletion result.")
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise CloudinaryStorageError("Cloud storage could not delete the document. Try again.") from exc
