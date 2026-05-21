"""Czech subtitle lookup and download from yts-subs.com."""
from __future__ import annotations

import base64
import io
import os
import re
import zipfile
from dataclasses import dataclass
from typing import Callable, List, Optional
from urllib.parse import quote

import requests

_BASE_URL = "https://yts-subs.com"
_CZECH_ROW = re.compile(
    r"<tr[^>]*>.*?<span class=\"sub-lang\">Czech</span>.*?"
    r"href=[\"'](/subtitles/[^\"']+)[\"'].*?"
    r"<span class=\"text-muted\">subtitle</span>\s*([^<]+)</a>.*?"
    r"class=\"uploader-cell\">([^<]*)</td>",
    re.IGNORECASE | re.DOTALL,
)
_RATING_IN_ROW = re.compile(
    r"<td class=\"rating-cell\">\s*<span[^>]*>(\d+)</span>",
    re.IGNORECASE,
)
_DATA_LINK = re.compile(
    r'id="btn-download-subtitle"[^>]+data-link="([^"]+)"',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class YtsMovie:
    imdb_id: str
    title: str
    year: Optional[int]


@dataclass(frozen=True)
class YtsSubtitle:
    release_name: str
    rating: int
    page_url: str
    uploader: str = ""


class YtsSubsClient:
    """Fetch Czech subtitles from yts-subs.com."""

    def __init__(
        self,
        logger: Optional[Callable[[str, int], None]] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self._session = session or requests.Session()
        self._session.headers.setdefault(
            "User-Agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        self._logger = logger

    def _log(self, message: str, level: int = 0) -> None:
        if self._logger:
            self._logger(message, level)

    def find_movie(self, title: str, year: Optional[int] = None) -> Optional[YtsMovie]:
        query = (title or "").strip()
        if not query:
            return None
        try:
            response = self._session.get(
                f"{_BASE_URL}/search/ajax/{quote(query)}",
                timeout=15,
            )
            response.raise_for_status()
            results = response.json()
        except (requests.RequestException, ValueError) as exc:
            self._log(f"YTS-Subs search failed: {exc}")
            return None
        if not isinstance(results, list) or not results:
            return None

        normalized_query = self._normalize(query)
        best: Optional[tuple[int, YtsMovie]] = None
        for entry in results:
            imdb_id = str(entry.get("mov_imdb_code") or "").strip()
            movie_title = str(entry.get("mov_title") or "").strip()
            if not imdb_id or not movie_title:
                continue
            try:
                movie_year = int(entry.get("mov_year") or 0) or None
            except (TypeError, ValueError):
                movie_year = None

            score = 0
            normalized_title = self._normalize(movie_title)
            if normalized_query == normalized_title:
                score += 80
            elif normalized_query in normalized_title or normalized_title in normalized_query:
                score += 45
            if year and movie_year:
                if year == movie_year:
                    score += 60
                elif abs(year - movie_year) <= 1:
                    score += 20
            elif year is None and movie_year:
                score += 5

            candidate = YtsMovie(imdb_id=imdb_id, title=movie_title, year=movie_year)
            if best is None or score > best[0]:
                best = (score, candidate)

        if best and best[0] >= 40:
            return best[1]
        if best:
            return best[1]
        return None

    def list_czech_subtitles(self, imdb_id: str) -> List[YtsSubtitle]:
        imdb_id = (imdb_id or "").strip()
        if not imdb_id.startswith("tt"):
            return []
        try:
            response = self._session.get(
                f"{_BASE_URL}/movie-imdb/{imdb_id}",
                timeout=20,
            )
            response.raise_for_status()
            html = response.text
        except requests.RequestException as exc:
            self._log(f"YTS-Subs movie page failed: {exc}")
            return []

        subtitles: List[YtsSubtitle] = []
        seen_urls: set[str] = set()
        for match in _CZECH_ROW.finditer(html):
            row_html = match.group(0)
            path = match.group(1)
            release_name = match.group(2).strip()
            uploader = match.group(3).strip()
            page_url = f"{_BASE_URL}{path}" if path.startswith("/") else path
            if page_url in seen_urls:
                continue
            seen_urls.add(page_url)
            rating_match = _RATING_IN_ROW.search(row_html)
            rating = int(rating_match.group(1)) if rating_match else 0
            subtitles.append(
                YtsSubtitle(
                    release_name=release_name,
                    rating=rating,
                    page_url=page_url,
                    uploader=uploader,
                )
            )

        if not subtitles:
            for path in dict.fromkeys(
                re.findall(r'href=["\'](/subtitles/[^"\']*-czech[^"\']*)["\']', html, re.IGNORECASE)
            ):
                page_url = f"{_BASE_URL}{path}"
                if page_url in seen_urls:
                    continue
                seen_urls.add(page_url)
                slug = path.rsplit("/", 1)[-1]
                release_name = slug.replace("-czech-yify-", " ").replace("-", " ")
                subtitles.append(
                    YtsSubtitle(release_name=release_name, rating=0, page_url=page_url)
                )

        subtitles.sort(key=lambda item: (-item.rating, item.release_name.lower()))
        return subtitles

    def download_subtitle(self, page_url: str, cache_dir: str) -> Optional[str]:
        page_url = (page_url or "").strip()
        if not page_url:
            return None
        try:
            response = self._session.get(page_url, timeout=20)
            response.raise_for_status()
        except requests.RequestException as exc:
            self._log(f"YTS-Subs subtitle page failed: {exc}")
            return None

        link_match = _DATA_LINK.search(response.text)
        if not link_match:
            self._log("YTS-Subs download link not found on subtitle page")
            return None

        try:
            zip_url = base64.b64decode(link_match.group(1)).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            self._log(f"YTS-Subs invalid download link: {exc}")
            return None

        try:
            zip_response = self._session.get(zip_url, timeout=45)
            zip_response.raise_for_status()
        except requests.RequestException as exc:
            self._log(f"YTS-Subs zip download failed: {exc}")
            return None

        os.makedirs(cache_dir, exist_ok=True)
        slug = page_url.rstrip("/").rsplit("/", 1)[-1]
        try:
            with zipfile.ZipFile(io.BytesIO(zip_response.content)) as archive:
                srt_names = [
                    name
                    for name in archive.namelist()
                    if name.lower().endswith(".srt") and not name.endswith("/")
                ]
                if not srt_names:
                    self._log("YTS-Subs zip contains no .srt file")
                    return None
                srt_name = srt_names[0]
                target_path = os.path.join(cache_dir, f"{slug}.srt")
                with archive.open(srt_name) as source, open(target_path, "wb") as target:
                    target.write(source.read())
                return target_path
        except (zipfile.BadZipFile, OSError) as exc:
            self._log(f"YTS-Subs extract failed: {exc}")
            return None

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.lower())
