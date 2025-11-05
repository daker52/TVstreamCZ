"""High level catalogue for querying and filtering Webshare content."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import xbmc

from .metadata import MetadataManager
from .parser import MediaItem, parse_media_entry
from .webshare_api import WebshareAPI


class WebshareCatalogue:
    """Compose Webshare search results into Kodi-ready media items."""

    def __init__(self, api: WebshareAPI, metadata: Optional[MetadataManager], settings, logger):
        self._api = api
        self._metadata = metadata
        self._settings = settings
        self._logger = logger or (lambda msg, level=xbmc.LOGINFO: xbmc.log(msg, level))

    def _passes_filters(
        self,
        item: MediaItem,
        media_type: Optional[str],
        letter: Optional[str],
        quality: Optional[str],
        audio: Optional[str],
        subtitles: Optional[str],
        genre: Optional[str],
    ) -> bool:
        # Skip non-movie/tvshow content (trailers, samples, etc.)
        if item.media_type == "other":
            return False
        
        # Skip very small files (likely trailers/samples) when filtering for movies
        # Minimum size: 100MB for movies, 50MB for TV shows
        if media_type == "movie" and item.size is not None:
            min_size = 100 * 1024 * 1024  # 100MB in bytes
            if item.size < min_size:
                return False
        elif media_type == "tvshow" and item.size is not None:
            min_size = 50 * 1024 * 1024  # 50MB in bytes
            if item.size < min_size:
                return False
        
        # Skip files with very short cleaned titles (likely not full movies)
        if media_type == "movie" and len(item.cleaned_title.strip()) < 3:
            return False
            
        if media_type and item.media_type != media_type:
            return False
        if letter:
            letter = letter.lower()
            sort = item.sort_title.lower()
            if letter == "0-9":
                if not sort[:1].isdigit():
                    return False
            elif not sort.startswith(letter):
                return False
        if quality and quality != "any":
            if item.quality != quality:
                # allow UHD to count as HD if requested
                if not (quality == "hd" and item.quality == "uhd"):
                    return False
        if audio and audio != "any":
            if audio not in item.audio_languages:
                return False
        if subtitles and subtitles != "any":
            if subtitles not in item.subtitle_languages:
                return False
        if genre and genre != "any":
            # Try to get genres from metadata first
            genres = []
            if item.metadata and isinstance(item.metadata, dict):
                genres = [g.lower() for g in item.metadata.get("genres", []) if isinstance(g, str)]
            
            # If no genres from metadata, try to guess from title/filename
            if not genres:
                title_lower = item.cleaned_title.lower()
                filename_lower = item.original_name.lower()
                
                # Basic genre detection from title/filename keywords
                genre_keywords = {
                    'action': ['action', 'fight', 'battle', 'war', 'combat'],
                    'comedy': ['comedy', 'funny', 'humor', 'laugh'],
                    'drama': ['drama', 'story', 'life'],
                    'horror': ['horror', 'scary', 'fear', 'terror', 'zombie'],
                    'thriller': ['thriller', 'suspense', 'mystery'],
                    'romance': ['love', 'romance', 'romantic'],
                    'science fiction': ['sci-fi', 'science fiction', 'space', 'future'],
                    'fantasy': ['fantasy', 'magic', 'wizard', 'dragon'],
                    'animation': ['animated', 'cartoon', 'anime'],
                    'documentary': ['documentary', 'docu', 'real story']
                }
                
                for genre_name, keywords in genre_keywords.items():
                    if any(keyword in title_lower or keyword in filename_lower for keyword in keywords):
                        genres.append(genre_name)
            
            # Check if requested genre matches
            if genre.lower() not in genres:
                return False
        return True

    def fetch(
        self,
        media_type: Optional[str] = None,
        query: str = "",
        letter: Optional[str] = None,
        sort: Optional[str] = None,
        quality: Optional[str] = None,
        audio: Optional[str] = None,
        subtitles: Optional[str] = None,
        genre: Optional[str] = None,
        start_offset: int = 0,
        page_size: Optional[int] = None,
    ) -> Tuple[List[MediaItem], int, int, bool]:
        limit = page_size or self._settings.page_size
        gathered: List[MediaItem] = []
        offset = max(0, start_offset)
        total: Optional[int] = None
        default_fetch_size = self._settings.page_size
        while len(gathered) < limit:
            fetch_size = max(default_fetch_size, limit)
            total, files = self._api.search(
                what=query,
                category="video",
                sort=sort,
                limit=fetch_size,
                offset=offset,
            )
            if not files:
                break
            for payload in files:
                item = parse_media_entry(payload, self._logger)
                if self._metadata:
                    self._metadata.enrich(item)
                if self._passes_filters(item, media_type, letter, quality, audio, subtitles, genre):
                    gathered.append(item)
                    if len(gathered) >= limit:
                        break
            offset += len(files)
            if total is not None and offset >= total:
                break
        has_more = bool(total and offset < total)
        return gathered, offset, total or 0, has_more

    def available_genres(self, media_type: str) -> Optional[List[str]]:
        if not self._metadata:
            return None
        return self._metadata.get_genres(media_type)
