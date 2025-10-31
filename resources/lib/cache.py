"""Simple file-based caching utility using shelve.

This module provides a persistent, expiring cache for arbitrary data.
It's designed to reduce network requests and speed up addon performance.
"""
import os
import shelve
import time
from contextlib import closing

import xbmc
import xbmcaddon

# --- Constants ---
CACHE_DIR_NAME = "cache"
CACHE_FILE_NAME = "tvstreamcz_cache"

# --- Globals ---
_ADDON = None
_ADDON_PROFILE = None
_CACHE_PATH = None


def _get_addon():
    """Get the addon instance, caching it for performance."""
    global _ADDON
    if _ADDON is None:
        _ADDON = xbmcaddon.Addon()
    return _ADDON

def _get_addon_profile():
    """Get the addon profile directory, creating it if it doesn't exist."""
    global _ADDON_PROFILE
    if _ADDON_PROFILE is None:
        try:
            profile = _get_addon().getAddonInfo('profile')
            # In older Kodi, profile might be a translatable path
            profile = xbmc.translatePath(profile)
            if not os.path.exists(profile):
                os.makedirs(profile)
            _ADDON_PROFILE = profile
        except (AttributeError, RuntimeError) as e:
            xbmc.log(f"[TVStreamCZ] Error getting addon profile: {e}", xbmc.LOGERROR)
            # Fallback to a temporary directory if profile is not available
            import tempfile
            _ADDON_PROFILE = tempfile.gettempdir()
    return _ADDON_PROFILE

def _get_cache_path():
    """Get the full path to the cache directory."""
    global _CACHE_PATH
    if _CACHE_PATH is None:
        profile_dir = _get_addon_profile()
        cache_dir = os.path.join(profile_dir, CACHE_DIR_NAME)
        if not os.path.exists(cache_dir):
            try:
                os.makedirs(cache_dir)
            except OSError as e:
                xbmc.log(f"[TVStreamCZ] Error creating cache directory: {e}", xbmc.LOGERROR)
                # Fallback to profile dir if sub-directory creation fails
                cache_dir = profile_dir
        _CACHE_PATH = os.path.join(cache_dir, CACHE_FILE_NAME)
    return _CACHE_PATH

def get(key: str):
    """Retrieve an item from the cache if it exists and has not expired."""
    try:
        cache_path = _get_cache_path()
        with closing(shelve.open(cache_path, 'r')) as shelf:
            if key in shelf:
                data = shelf[key]
                expires = data.get('expires')
                if expires is not None and time.time() < expires:
                    return data.get('value')
    except Exception as e:
        xbmc.log(f"[TVStreamCZ] Cache GET failed for key '{key}': {e}", xbmc.LOGWARNING)
    return None

def set(key: str, value, expiration_minutes: int = 60):
    """Save an item to the cache with an expiration time."""
    if value is None:
        return

    try:
        cache_path = _get_cache_path()
        with closing(shelve.open(cache_path, 'c')) as shelf:
            shelf[key] = {
                'value': value,
                'expires': time.time() + (expiration_minutes * 60)
            }
    except Exception as e:
        xbmc.log(f"[TVStreamCZ] Cache SET failed for key '{key}': {e}", xbmc.LOGWARNING)

def clear():
    """Clear the entire cache."""
    try:
        cache_path = _get_cache_path()
        with closing(shelve.open(cache_path, 'n')) as shelf:
            pass # Opening with 'n' flag truncates the file
        xbmc.log("[TVStreamCZ] Cache cleared.", xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f"[TVStreamCZ] Failed to clear cache: {e}", xbmc.LOGWARNING)