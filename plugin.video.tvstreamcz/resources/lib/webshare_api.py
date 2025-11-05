"""Wrapper around the Webshare HTTP API."""
from __future__ import annotations

import hashlib
import time
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

import requests
import xbmc

from .md5crypt import md5_crypt


class WebshareError(Exception):
    """Generic Webshare API error."""

    def __init__(self, message: str, code: Optional[str] = None):
        super().__init__(message)
        self.code = code


class WebshareAuthError(WebshareError):
    """Raised when authentication fails."""


class WebshareAPI:
    BASE_URL = "https://webshare.cz/api"
    DEFAULT_HEADERS = {
        "Accept": "text/xml; charset=UTF-8",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "User-Agent": "Kodi-TVStreamCZ/0.1.0",
    }

    def __init__(self, logger=None):
        self._session = requests.Session()
        self._session.headers.update(self.DEFAULT_HEADERS)
        self._token: Optional[str] = None
        self._token_verified = False
        self._token_checked_at: float = 0.0
        self._logger = logger or (lambda msg, level=xbmc.LOGINFO: xbmc.log(msg, level))

    @property
    def token(self) -> Optional[str]:
        return self._token

    def set_token(self, token: Optional[str]) -> None:
        self._token = token
        self._token_verified = False
        if token:
            self._session.cookies.set("wst", token, domain="webshare.cz")
        else:
            self._session.cookies.pop("wst", None)

    def _parse_xml(self, payload: str) -> ET.Element:
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise WebshareError(f"Invalid XML response: {exc}") from exc
        status = root.findtext("status")
        if status != "OK":
            code = root.findtext("code")
            message = root.findtext("message") or status or "Unknown error"
            if code and code.startswith("LOGIN"):
                raise WebshareAuthError(message, code)
            raise WebshareError(message, code)
        return root

    def _post(self, endpoint: str, data: Optional[Dict[str, object]] = None, require_token: bool = False) -> ET.Element:
        payload = {k: str(v) for k, v in (data or {}).items() if v is not None}
        if require_token:
            self.ensure_logged_in()
            if self._token:
                payload.setdefault("wst", self._token)
        try:
            response = self._session.post(f"{self.BASE_URL}{endpoint}", data=payload, timeout=15)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise WebshareError(f"HTTP request failed: {exc}") from exc
        return self._parse_xml(response.text)

    def _fetch_salt(self, username: str) -> Optional[str]:
        try:
            root = self._post("/salt/", {"username_or_email": username})
        except WebshareError as exc:
            self._logger(f"Unable to fetch salt: {exc}", xbmc.LOGWARNING)
            return None
        return root.findtext("salt")

    def _hash_password(self, username: str, password: str) -> Optional[str]:
        salt = self._fetch_salt(username)
        if not salt:
            return None
        digest = md5_crypt(password, salt)
        return hashlib.sha1(digest.encode("utf-8")).hexdigest()

    def login(self, username: str, password: str, keep_logged_in: bool = True) -> str:
        if not username or not password:
            raise WebshareAuthError("Credentials are missing.")
        hashed = self._hash_password(username, password)
        strategies = []
        if hashed:
            strategies.append((hashed, True))
        strategies.append((password, False))
        last_error: Optional[Exception] = None
        for pwd, is_hashed in strategies:
            data = {
                "username_or_email": username,
                "password": pwd,
                "keep_logged_in": 1 if keep_logged_in else 0,
            }
            try:
                root = self._post("/login/", data)
                token = root.findtext("token")
                if not token:
                    raise WebshareAuthError("Authentication token missing in response.")
                self.set_token(token)
                self._token_verified = True
                return token
            except WebshareAuthError as exc:
                last_error = exc
                continue
            except WebshareError as exc:
                last_error = exc
                break
        raise WebshareAuthError(str(last_error) if last_error else "Login failed.")

    def ensure_logged_in(self) -> None:
        if not self._token:
            raise WebshareAuthError("Not authenticated.")
        now = time.time()
        if self._token_verified and now - self._token_checked_at < 600:
            return
        try:
            # Avoid recursion: do not require token check for /session/
            self._post("/session/", {}, require_token=False)
            self._token_verified = True
            self._token_checked_at = now
        except WebshareError as exc:
            self._logger(f"Session token invalid, clearing it: {exc}", xbmc.LOGINFO)
            self.set_token(None)
            raise WebshareAuthError("Session expired.") from exc

    def search(self, what: str = "", category: str = "video", sort: Optional[str] = None, limit: int = 40, offset: int = 0) -> Tuple[int, List[Dict[str, str]]]:
        data: Dict[str, object] = {
            "what": what or "",
            "category": category,
            "limit": max(1, min(100, limit)),
            "offset": max(0, offset),
        }
        if sort:
            data["sort"] = sort
        root = self._post("/search/", data)
        total = int(root.findtext("total", "0") or 0)
        files: List[Dict[str, str]] = []
        for node in root.findall("file"):
            entry = {child.tag: child.text or "" for child in list(node)}
            files.append(entry)
        return total, files

    def file_info(self, ident: str) -> Dict[str, str]:
        root = self._post("/file_info/", {"ident": ident}, require_token=True)
        return {child.tag: child.text or "" for child in list(root) if child.tag != "status"}

    def file_link(self, ident: str, download_type: str = "video_stream", password: Optional[str] = None, force_https: bool = True) -> str:
        data: Dict[str, object] = {
            "ident": ident,
            "download_type": download_type,
            "force_https": 1 if force_https else 0,
        }
        if password:
            data["password"] = password
        root = self._post("/file_link/", data, require_token=True)
        link = root.findtext("link")
        if not link:
            raise WebshareError("Webshare did not return a playback link.")
        return link

    def logout(self) -> None:
        if not self._token:
            return
        try:
            self._post("/logout/", {}, require_token=True)
        except WebshareError:
            pass
        finally:
            self.set_token(None)
