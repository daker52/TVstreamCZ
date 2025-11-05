"""Parsing utilities for Webshare media items."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Pattern, Tuple

_TOKEN_SPLIT = re.compile(r"[\s._\-\[\](){}]+")
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_SEASON_EPISODE_RE = re.compile(r"[Ss](\d{1,2})[\s._-]*[Ee](\d{1,2})")
_ALT_SEASON_EPISODE_RE = re.compile(r"\b(\d{1,2})x(\d{2})\b")
_QUALITY_PATTERNS = (
    ("uhd", re.compile(r"(?i)(2160p|4k|uhd|dolby\s*vision|hdr)"), 3),
    ("hd", re.compile(r"(?i)(1080p|720p|hd|webrip|bluray|bdrip|brrip)"), 2),
    ("sd", re.compile(r"(?i)(576p|480p|dvdrip|dvd|tvrip|xvid|hdtv|cam|workprint|ts)") , 1),
)
_LANGUAGE_MAP: Dict[str, Pattern[str]] = {
    "cz": re.compile(r"(?i)\b(cz|ces|cze|czech|czdab|czdub|czaudio|czsound|cz\s*dabing|cz\s*dub)\b"),
    "sk": re.compile(r"(?i)\b(sk|slk|slovak|skdab|skdub|sk\s*dabing|sk\s*dub)\b"),
    "en": re.compile(r"(?i)\b(en|eng|english|en\s*audio)\b"),
}
_SUBTITLE_MAP: Dict[str, Pattern[str]] = {
    "cz": re.compile(r"(?i)(cz\s*tit|tit\s*cz|cz\s*subs|czsub|cztitl|cztitulky)"),
    "sk": re.compile(r"(?i)(sk\s*tit|tit\s*sk|sk\s*subs|sktit|sktitulky)"),
    "en": re.compile(r"(?i)(en\s*tit|tit\s*en|en\s*subs|engsub|eng\s*subs|english\s*subs)"),
}
_REMOVE_TOKENS = re.compile(
    r"(?i)\b(720p|1080p|2160p|4k|uhd|hdr|webrip|web-dl|webdl|bluray|bdrip|brrip|x264|x265|h264|h265|hevc|dvdrip|dvdr|hdtv|aac|dts|truehd|atmos|remux|multi|cz|sk|eng|en|dd5\.?1|dd\d|exclusive|proper|repack|nf|nfwebrip|ws|hmax|amzn|pal|ntsc)\b"
)
_ARTICLES = ("the ", "a ", "an ", "der ", "die ", "das ", "le ", "la ", "los ", "las ", "el ")


@dataclass
class MediaItem:
    """Normalized representation of a Webshare media entry."""

    ident: str
    original_name: str
    extension: Optional[str]
    size: Optional[int]
    preview_image: Optional[str]
    preview_strip: Optional[str]
    preview_count: Optional[int]
    votes_positive: Optional[int]
    votes_negative: Optional[int]
    password_protected: bool
    media_type: str
    cleaned_title: str
    sort_title: str
    guessed_year: Optional[int] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    quality: Optional[str] = None
    quality_score: int = 0
    audio_languages: List[str] = field(default_factory=list)
    subtitle_languages: List[str] = field(default_factory=list)
    metadata: Dict[str, object] = field(default_factory=dict)

    def apply_metadata(self, data: Dict[str, object]) -> None:
        """Merge fetched metadata into the item."""
        if not data:
            return
        self.metadata.update(data)
        self.metadata.setdefault("title", self.cleaned_title)
        self.metadata.setdefault("year", self.guessed_year)


def tokenize(name: str) -> List[str]:
    return [token for token in _TOKEN_SPLIT.split(name) if token]


def detect_season_episode(name: str) -> Tuple[Optional[int], Optional[int]]:
    match = _SEASON_EPISODE_RE.search(name)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = _ALT_SEASON_EPISODE_RE.search(name)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None, None


def detect_year(name: str) -> Optional[int]:
    match = _YEAR_RE.search(name)
    if match:
        return int(match.group(0))
    return None


def detect_quality(name: str) -> Tuple[Optional[str], int]:
    best: Optional[str] = None
    score = 0
    for label, pattern, value in _QUALITY_PATTERNS:
        if pattern.search(name):
            best = label
            score = value
            break
    return best, score


def detect_languages(tokens: List[str], combined: str, patterns: Dict[str, Pattern[str]]) -> List[str]:
    found: List[str] = []
    lower_combined = combined.lower()
    for lang, pattern in patterns.items():
        if pattern.search(lower_combined):
            found.append(lang)
            continue
        for token in tokens:
            if pattern.search(token.lower()):
                found.append(lang)
                break
    return found


def clean_title(name: str) -> str:
    work = name.replace("_", " ").replace(".", " ").replace("-", " ")
    work = _REMOVE_TOKENS.sub(" ", work)
    work = _SEASON_EPISODE_RE.sub(" ", work)
    work = _ALT_SEASON_EPISODE_RE.sub(" ", work)
    work = _YEAR_RE.sub(" ", work)
    work = re.sub(r"\b\d{1,2}of\d{1,2}\b", " ", work, flags=re.I)
    work = re.sub(r"\s+", " ", work).strip()
    return work or name


def make_sort_title(title: str) -> str:
    lower = title.lower()
    for article in _ARTICLES:
        if lower.startswith(article):
            return lower[len(article) :].strip() or lower
    return lower


def classify_media_type(name: str) -> str:
    """Classify media type with comprehensive TV show detection."""
    
    # Check for explicit season/episode patterns first
    season, episode = detect_season_episode(name)
    if season is not None or episode is not None:
        return "tvshow"
    
    # Extended TV show patterns
    tv_patterns = [
        r"[Ss]\d{1,2}[Ee]\d{1,2}",  # S01E01, s1e1
        r"\d+x\d+",                  # 1x01, 2x05
        r"[Ss]ér[ií]e?\s*\d+",      # Série 1, serie 1, sérii 1
        r"[Ss]eason\s*\d+",         # Season 1
        r"[Ee]p\.?\s*\d+",          # Ep.1, Episode 1
        r"[Ee]pisode\s*\d+",        # Episode 1
        r"\b[Ss]\d{1,2}\b",         # S1, S01 (standalone)
        r"\b[Ee]\d{1,2}\b",         # E1, E01 (standalone)
        r"díl\s*\d+",               # díl 1, díl 12
        r"část\s*\d+",              # část 1
    ]
    
    # Check all TV patterns
    for pattern in tv_patterns:
        if re.search(pattern, name, re.IGNORECASE):
            return "tvshow"
    
    # Filter out trailers, samples, and other non-movie content
    if re.search(r"(?i)(trailer|teaser|sample|preview|promo|making[\s_-]?of|behind[\s_-]?the[\s_-]?scenes|extras?|bonus|featurette|deleted[\s_-]?scene|outtake|interview|soundtrack|ost|music[\s_-]?video|documentary|doc|featureset|commercial|ad)", name):
        return "other"
    
    # Additional filtering for short clips (likely not full movies)
    if re.search(r"(?i)\b(clip|short|segment|excerpt|fragment|demo|test|rip)\b", name):
        return "other"
    
    # Filter out obvious non-content files
    if re.search(r"(?i)\b(readme|nfo|txt|sub|srt|idx|info|cover|artwork|poster)\b", name):
        return "other"
    
    # Filter out partial downloads or incomplete files
    if re.search(r"(?i)(part\d+|cd\d+|disc\d+|\bpt\d+)", name) and not re.search(r"(?i)(movie|film)", name):
        return "other"
        
    return "movie"


def parse_media_entry(data: Dict[str, str], logger=None) -> MediaItem:
    name = data.get("name", "").strip()
    ident = data.get("ident", "").strip()
    extension = data.get("type") or None
    size = int(data.get("size", "0")) if data.get("size") else None
    preview_image = data.get("img") or None
    preview_strip = data.get("stripe") or None
    preview_count = int(data.get("stripe_count", "0")) if data.get("stripe_count") else None
    votes_positive = int(data.get("positive_votes", "0")) if data.get("positive_votes") else None
    votes_negative = int(data.get("negative_votes", "0")) if data.get("negative_votes") else None
    password_protected = data.get("password", "0") == "1"

    media_type = classify_media_type(name)
    season, episode = detect_season_episode(name)
    
    # Debug logging if available
    if logger and media_type == "tvshow":
        logger(f"TV SHOW detected: '{name}' -> {media_type}, S{season}E{episode}", level=2)  # LOGINFO
    guessed_year = detect_year(name)
    quality, quality_score = detect_quality(name)

    tokens = tokenize(name)
    combined = " ".join(tokens)
    audio_languages = detect_languages(tokens, combined, _LANGUAGE_MAP)
    subtitle_languages = detect_languages(tokens, combined, _SUBTITLE_MAP)

    cleaned = clean_title(name)
    sort_title = make_sort_title(cleaned)

    return MediaItem(
        ident=ident,
        original_name=name,
        extension=extension,
        size=size,
        preview_image=preview_image,
        preview_strip=preview_strip,
        preview_count=preview_count,
        votes_positive=votes_positive,
        votes_negative=votes_negative,
        password_protected=password_protected,
        media_type=media_type,
        cleaned_title=cleaned,
        sort_title=sort_title,
        guessed_year=guessed_year,
        season=season,
        episode=episode,
        quality=quality,
        quality_score=quality_score,
        audio_languages=audio_languages,
        subtitle_languages=subtitle_languages,
    )
