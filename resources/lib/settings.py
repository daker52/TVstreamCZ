"""Helpers for reading add-on settings and shared configuration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import xbmcaddon


@dataclass(frozen=True)
class AddonSettings:
    """Immutable snapshot of the user-configurable settings."""

    username: str
    password: str
    keep_logged_in: bool
    default_quality: str
    default_audio: str
    default_subtitles: str
    page_size: int
    metadata_provider: str
    tmdb_api_key: str
    metadata_language: str
    metadata_region: str
    csfd_user_agent: str
    download_type: str
    force_https: bool

    @classmethod
    def load(cls, addon: Optional[xbmcaddon.Addon] = None) -> "AddonSettings":
        addon = addon or xbmcaddon.Addon()
        quality_options = ("any", "hd", "uhd", "sd")
        audio_options = ("any", "cz", "sk", "en")
        provider_options = ("tmdb_first", "csfd_first", "tmdb_only", "csfd_only", "none")
        download_options = ("video_stream", "file_download")

        def _get_raw(key: str) -> str:
            try:
                # First try the generic getSetting method
                value = addon.getSetting(key)
                return value if value is not None else ""
            except (TypeError, AttributeError, RuntimeError):
                return ""

        def _get_string(key: str, default: str = "") -> str:
            value = _get_raw(key)
            return (value or default).strip()

        def _get_bool(key: str, default: bool = False) -> bool:
            try:
                # Try the bool-specific method first
                return addon.getSettingBool(key)
            except (TypeError, AttributeError, RuntimeError):
                # Fall back to string parsing
                raw = _get_raw(key)
                if not raw:
                    return default
                return raw.lower() in ("true", "1", "yes")

        def _get_int(key: str, default: int = 0) -> int:
            try:
                # Try the int-specific method first
                return addon.getSettingInt(key)
            except (TypeError, AttributeError, RuntimeError):
                # Fall back to string parsing
                raw = _get_raw(key)
                if raw is None or raw == "":
                    return default
                try:
                    return int(raw)
                except (ValueError, TypeError):
                    return default

        def _get_enum(key: str, values: tuple[str, ...], default_index: int = 0) -> str:
            index = _get_int(key, default_index)
            if not 0 <= index < len(values):
                index = default_index
            return values[index]

        username = _get_string("username")
        password = _get_string("password")
        keep_logged_in = _get_bool("keep_logged_in", True)
        default_quality = _get_enum("default_quality", quality_options)
        default_audio = _get_enum("default_audio", audio_options)
        default_subtitles = _get_enum("default_subtitles", audio_options)
        page_size = max(20, min(100, _get_int("page_size", 40)))
        metadata_provider = _get_enum("metadata_provider", provider_options)
        tmdb_api_key = _get_string("tmdb_api_key", "6406b0cf7f63de64d61ca724f3174716")
        metadata_language = _get_string("metadata_language", "cs-CZ")
        metadata_region = _get_string("metadata_region", "CZ")
        csfd_user_agent = _get_string("csfd_user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        download_type = _get_enum("download_type", download_options)
        force_https = _get_bool("force_https", True)
        return cls(
            username=username.strip(),
            password=password,
            keep_logged_in=keep_logged_in,
            default_quality=default_quality.lower(),
            default_audio=default_audio.lower(),
            default_subtitles=default_subtitles.lower(),
            page_size=page_size,
            metadata_provider=metadata_provider,
            tmdb_api_key=tmdb_api_key.strip(),
            metadata_language=metadata_language.strip(),
            metadata_region=metadata_region.strip(),
            csfd_user_agent=csfd_user_agent.strip(),
            download_type=download_type,
            force_https=force_https,
        )
