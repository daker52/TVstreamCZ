# -*- coding: utf-8 -*-
"""Prehraj.to search and streaming API for Kodi.

Allows searching for videos on prehraj.to and extracting stream URLs.
Search URL format:  https://prehraj.to/hledej/{query}
Video detail URL:   https://prehraj.to/{title-slug}/{hex-id}
"""
import re
import xbmc

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class PrehrajtoItem:
    """Represents a single video result from prehraj.to."""

    def __init__(self, title="", url="", duration="", quality="", size_str="", thumbnail=""):
        self.title = title
        self.url = url          # Full URL to detail page, e.g. https://prehraj.to/celisti-1975/4b588ebd6ec85dd6
        self.duration = duration  # e.g. "02:03:56"
        self.quality = quality    # e.g. "HD", "4K"
        self.size_str = size_str  # e.g. "5.45 GB"
        self.thumbnail = thumbnail


class PrehrajtoAPI:
    """API wrapper for prehraj.to – no login required for search."""

    BASE_URL = "https://prehraj.to"
    SEARCH_URL = "https://prehraj.to/hledej/{query}"

    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "cs,sk;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Referer": "https://prehraj.to/",
        "DNT": "1",
        "Connection": "keep-alive",
    }

    def __init__(self, logger=None):
        self._logger = logger or (lambda msg, level=xbmc.LOGINFO: xbmc.log(msg, level))
        if REQUESTS_AVAILABLE:
            import requests as _requests
            self._session = _requests.Session()
            self._session.headers.update(self._HEADERS)
        else:
            self._session = None
            self._logger("requests library not available for prehrajto_api", xbmc.LOGWARNING)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(self, query):
        """Search prehraj.to for *query*.

        Returns a list of :class:`PrehrajtoItem` objects.
        """
        if not self._session:
            self._logger("Prehraj.to: requests not available", xbmc.LOGERROR)
            return []

        # Encode the query – prehraj.to uses the raw query in the path
        # Spaces and special chars are URL-encoded (%20 etc.)
        from urllib.parse import quote
        encoded = quote(query, safe='')
        url = self.SEARCH_URL.format(query=encoded)
        self._logger(f"Prehraj.to search: {url}", xbmc.LOGINFO)

        try:
            resp = self._session.get(url, timeout=20)
            resp.raise_for_status()
            items = self._parse_search_results(resp.text)
            self._logger(
                f"Prehraj.to: '{query}' -> {len(items)} výsledků", xbmc.LOGINFO
            )
            return items
        except Exception as exc:
            self._logger(f"Prehraj.to search chyba: {exc}", xbmc.LOGERROR)
            return []

    def get_stream_url(self, video_url):
        """Try to extract a direct/playable video URL from the detail page.

        Returns a URL string or *None* if extraction failed.
        """
        if not self._session:
            return None

        self._logger(f"Prehraj.to: načítám stream z {video_url}", xbmc.LOGINFO)
        try:
            resp = self._session.get(video_url, timeout=20)
            resp.raise_for_status()
            stream_url = self._extract_stream_url(resp.text, video_url)
            if stream_url:
                self._logger(f"Prehraj.to: stream nalezen: {stream_url[:80]}", xbmc.LOGINFO)
            else:
                self._logger(
                    "Prehraj.to: stream nenalezen – stránka vyžaduje přihlášení nebo JS",
                    xbmc.LOGWARNING,
                )
            return stream_url
        except Exception as exc:
            self._logger(f"Prehraj.to: chyba při získávání streamu: {exc}", xbmc.LOGERROR)
            return None

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_search_results(self, html):
        """Parse HTML from prehraj.to search results page.

        Results look like (in the page source):
            <a href="/celisti-1975/4b588ebd6ec85dd6">02:03:56 HD 5.45 GB Čelisti 1975</a>
        """
        results = []
        seen = set()

        # Match anchor tags pointing at video pages: /slug/hexid
        # The hex ID is at least 8 hex characters long.
        pattern = re.compile(
            r'<a[^>]+href="(/[a-z0-9][a-z0-9\-]*/[0-9a-f]{8,})"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )

        # Pages we want to skip (nav/footer links with similar URL style)
        _SKIP_PATHS = (
            "/hledej/", "/profil/", "/jak-na-to", "/podminky",
            "/faq", "/kontakt", "/nahlasit", "/navrhy", "/google-tv",
            "/android-app", "/ochrana", "/partner",
        )

        for m in pattern.finditer(html):
            slug_path = m.group(1)
            link_content = m.group(2)

            if slug_path in seen:
                continue
            if any(slug_path.startswith(skip) for skip in _SKIP_PATHS):
                continue

            seen.add(slug_path)

            # Strip HTML tags from link text
            clean = re.sub(r"<[^>]+>", " ", link_content)
            clean = re.sub(r"\s+", " ", clean).strip()

            if not clean or len(clean) < 3:
                continue

            # ---- Extract structured metadata from link text ----
            duration = ""
            quality = ""
            size_str = ""

            # Duration: HH:MM:SS or H:MM:SS
            dur_m = re.search(r"\b(\d{1,2}:\d{2}:\d{2})\b", clean)
            if dur_m:
                duration = dur_m.group(1)
                clean = clean.replace(duration, " ").strip()

            # Quality: 4K / UHD / FullHD / HD / SD / CAM
            qual_m = re.search(r"\b(4K|UHD|FullHD|FHD|HD|SD|CAM)\b", clean, re.IGNORECASE)
            if qual_m:
                quality = qual_m.group(1).upper()
                clean = clean.replace(qual_m.group(0), " ").strip()

            # File size: "5.45 GB", "1.59 GB", "17.56 GB", "800 MB"
            size_m = re.search(r"(\d+(?:[.,]\d+)?\s*(?:GB|MB|TB))", clean, re.IGNORECASE)
            if size_m:
                size_str = size_m.group(1)
                clean = clean.replace(size_m.group(0), " ").strip()

            # Remove leftover standalone numbers (e.g. episode markers like "1 " "2 ")
            clean = re.sub(r"^\s*\d+\s+", "", clean)
            clean = re.sub(r"\s+", " ", clean).strip()

            # Fall back to humanised slug if nothing useful in link text
            if not clean:
                slug_parts = slug_path.strip("/").split("/")
                clean = slug_parts[0].replace("-", " ").title() if slug_parts else slug_path

            results.append(
                PrehrajtoItem(
                    title=clean,
                    url=f"{self.BASE_URL}{slug_path}",
                    duration=duration,
                    quality=quality,
                    size_str=size_str,
                )
            )

        return results

    # ------------------------------------------------------------------

    _STREAM_PATTERNS = [
        # <source src="...mp4">
        r'<source[^>]+src=["\']([^"\']+\.(?:mp4|mkv|avi|m3u8|webm)[^"\']*)["\']',
        # JSON-like: "src":"https://..."
        r'"src"\s*:\s*"(https?://[^"]+\.(?:mp4|mkv|avi|m3u8|webm)[^"]*)"',
        # JS player: file: "..."
        r'file\s*:\s*["\']([^"\']+\.(?:mp4|mkv|m3u8)[^"\']*)["\']',
        # Generic "url": "https://..."
        r'"url"\s*:\s*"(https?://[^"]+\.(?:mp4|mkv|avi|m3u8)[^"]*)"',
        # data-file / data-src attributes
        r'data-file=["\']([^"\']+)["\']',
        r'data-src=["\']([^"\']+\.(?:mp4|mkv|m3u8|avi)[^"\']*)["\']',
        r'data-video=["\']([^"\']+)["\']',
        # JS variable assignments
        r'videoUrl\s*=\s*["\']([^"\']+)["\']',
        r'streamUrl\s*=\s*["\']([^"\']+)["\']',
        r'playUrl\s*=\s*["\']([^"\']+)["\']',
        # href pointing to CDN/storage/download
        r'href=["\'](https?://[^"\']+\.(?:mp4|mkv|avi)[^"\']*)["\']',
        r'href=["\']((?:https?://[^"\']*|/[^"\']*(?:download|storage|cdn)[^"\']*\.(?:mp4|mkv|avi))[^"\']*)["\']',
    ]

    def _extract_stream_url(self, html, page_url):
        """Try each pattern in :attr:`_STREAM_PATTERNS` and return first match."""
        for pat in self._STREAM_PATTERNS:
            m = re.search(pat, html, re.IGNORECASE)
            if m:
                url = m.group(1)
                if not url.startswith("http"):
                    url = f"{self.BASE_URL}{url}"
                return url
        return None
