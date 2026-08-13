"""Client for the mybk /api REST surface.

Wires the same headers the live /app/js/main.js sets on every AJAX call:
  Authorization: <raw jwt>   (no Bearer prefix — matches production JS)
  Accept / Accept-Language / Content-Type: application/json
  Origin + Referer: https://mybk.hcmut.edu.vn
Envelope: {"code": "200", "data": ..., "msg": ...} — code is a string.

Two quirks are handled here so callers never see them:
  - responses may carry a UTF-8 BOM (served by the Struts/DKMH stack)
  - the portal appends a literal `null` query param to fight caches; the
    helpers append it for GET calls automatically.
"""

from __future__ import annotations

import json
from typing import Any

import requests

BASE = "https://mybk.hcmut.edu.vn"


class ApiError(RuntimeError):
    def __init__(self, code: str, msg: str):
        super().__init__(f"API error {code}: {msg}")
        self.code = code
        self.msg = msg


def _decode(text: str) -> Any:
    text = text.lstrip("\ufeff")  # DKMH stack serves a BOM
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ApiError("?", f"non-JSON response: {text[:200]!r}") from e


class MyBK:
    def __init__(self, session: requests.Session, jwt: str, use_bearer: bool = False):
        self._s = session
        self._jwt = jwt
        self._auth = f"Bearer {jwt}" if use_bearer else jwt

    def _headers(self) -> dict:
        return {
            "Authorization": self._auth,
            "Accept": "application/json",
            "Accept-Language": "vi",
            "Content-Type": "application/json",
            "Origin": BASE,
            "Referer": f"{BASE}/app/",
        }

    def call(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        data: Any = None,
        anti_cache: bool = True,
    ) -> Any:
        """Call /api/<path>; returns the `data` field of a 200 envelope."""
        if (method.upper() == "GET") and anti_cache and params is not None:
            params = {**params, "null": ""}  # literal ?null suffix
        url = f"{BASE}/api/{path.lstrip('/')}"
        r = self._s.request(method, url, params=params, json=data, headers=self._headers(), timeout=30)
        r.raise_for_status()
        payload = _decode(r.text)
        code = str(payload.get("code"))
        if code in ("200", "400"):  # 400 carries business data too, keep it for the caller
            return payload.get("data")
        if code == "401":
            raise ApiError(code, payload.get("msg", "unauthorized — token expired?"))
        msg = payload.get("msg", "")
        raise ApiError(code, msg)

    def get(self, path: str, params: dict | None = None) -> Any:
        return self.call("GET", path, params=params, data=None)

    def post(self, path: str, params: dict | None = None, data: Any = None) -> Any:
        return self.call("POST", path, params=params, data=data)


class _Media(MyBK):
    """Son of MyBK: file/media share shortcuts (not used by the planner core
    but useful for avatar/photo fetch if you ever need it)."""

    def share(self, category: str, media_id: Any, size: str = "original") -> str:
        return self.get(f"media/share/find/{category}/{media_id}/{size}/v1")


# keep a plain alias so callers can build a media-capable client
def new_media_client(session, jwt):
    return _Media(session, jwt)