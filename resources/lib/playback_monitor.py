"""Track playback position and persist watch history for TVStreamCZ."""
from __future__ import annotations

import datetime
import json
from typing import Any, Dict, Optional

import xbmc
import xbmcaddon
import xbmcgui

_ACTIVE: Dict[str, Any] = {}
_PENDING: Optional[Dict[str, Any]] = None
_MIN_PERCENT = 3.0
_MIN_SECONDS = 45
_RESUME_MAX_PERCENT = 90.0


class PlaybackMonitor(xbmc.Monitor):
    """Background service that saves progress when playback stops."""

    def __init__(self) -> None:
        super().__init__()
        self._addon = xbmcaddon.Addon()
        self._logger = lambda msg, level=xbmc.LOGDEBUG: xbmc.log(f"[TVStreamCZ] {msg}", level)

    def onPlayBackStarted(self) -> None:
        global _PENDING
        player = xbmc.Player()
        try:
            if not player.isPlayingVideo():
                return
            path = player.getPlayingFile() or ""
        except RuntimeError:
            return
        if _PENDING:
            _PENDING["started"] = True
            if path:
                _ACTIVE[path] = dict(_PENDING)
        if path and path in _ACTIVE:
            _ACTIVE[path]["started"] = True

    def onPlayBackStopped(self) -> None:
        self._flush_active_session()

    def onPlayBackEnded(self) -> None:
        self._flush_active_session()

    def _flush_active_session(self) -> None:
        global _PENDING
        player = xbmc.Player()
        try:
            path = player.getPlayingFile() or ""
        except RuntimeError:
            path = ""
        session = _ACTIVE.pop(path, None) if path else None
        if not session and _PENDING and _PENDING.get("started"):
            session = dict(_PENDING)
            _PENDING = None
        if not session and _ACTIVE:
            session = next(iter(_ACTIVE.values()))
            _ACTIVE.clear()
        if not session:
            return
        try:
            position = float(player.getTime())
            total = float(player.getTotalTime())
        except RuntimeError:
            position = session.get("position", 0)
            total = session.get("total", 0)
        if total <= 0:
            total = session.get("total", 0) or 0
        if position <= 0:
            position = session.get("position", 0) or 0
        percent = (position / total * 100.0) if total > 0 else 0.0
        if percent < _MIN_PERCENT and position < _MIN_SECONDS:
            return
        self._save_watch_entry(session["ident"], session.get("meta", {}), position, total, percent)

    @classmethod
    def register_playback(cls, addon: xbmcaddon.Addon, ident: str, meta: Dict[str, Any]) -> None:
        """Register a new playback session before resolving stream URL."""
        global _PENDING
        _PENDING = {
            "ident": ident,
            "meta": dict(meta),
            "addon_id": addon.getAddonInfo("id"),
            "started": False,
        }

    def _save_watch_entry(
        self,
        ident: str,
        meta: Dict[str, Any],
        position: float,
        total: float,
        percent: float,
    ) -> None:
        now = datetime.datetime.now().isoformat()
        item_data = {
            "ident": ident,
            "title": meta.get("title") or meta.get("context_title") or f"Video {ident[:8]}",
            "media_type": meta.get("media_type", "movie"),
            "play_date": now,
            "last_watched": now,
            "year": meta.get("year") or meta.get("context_year"),
            "thumb": meta.get("thumb"),
            "poster": meta.get("poster"),
            "plot": meta.get("plot"),
            "season": meta.get("season"),
            "episode": meta.get("episode"),
            "series_name": meta.get("series_name") or meta.get("tvshowtitle"),
            "context_title": meta.get("context_title") or meta.get("title"),
            "context_year": meta.get("context_year") or meta.get("year"),
            "position": position,
            "total": total,
            "percent": round(percent, 1),
            "resume_position": position if percent < _RESUME_MAX_PERCENT else 0,
            "resume_time": position,
        }
        for extra_key in (
            "source",
            "video_url",
            "originaltitle",
            "imdb",
            "movie_title",
            "display_title",
        ):
            value = meta.get(extra_key)
            if value:
                item_data[extra_key] = value

        recent = self._load_json("recent_items")
        recent = [x for x in recent if x.get("ident") != ident]
        recent.insert(0, item_data)
        self._addon.setSetting("recent_items", json.dumps(recent[:30]))

        frequent = self._load_json("frequent_items")
        found = False
        for entry in frequent:
            if entry.get("ident") == ident:
                entry["play_count"] = entry.get("play_count", 0) + 1
                entry["last_played"] = now
                entry["title"] = item_data["title"]
                found = True
                break
        if not found:
            copy = dict(item_data)
            copy["play_count"] = 1
            frequent.append(copy)
        frequent.sort(key=lambda x: x.get("play_count", 0), reverse=True)
        self._addon.setSetting("frequent_items", json.dumps(frequent[:50]))

        if _MIN_PERCENT <= percent < _RESUME_MAX_PERCENT:
            resume = self._load_json("resume_items")
            resume = [x for x in resume if x.get("ident") != ident]
            resume.insert(0, item_data)
            self._addon.setSetting("resume_items", json.dumps(resume[:25]))
        elif percent >= _RESUME_MAX_PERCENT:
            resume = self._load_json("resume_items")
            resume = [x for x in resume if x.get("ident") != ident]
            self._addon.setSetting("resume_items", json.dumps(resume))

        self._logger(
            f"Historie uložena: {item_data['title']} ({percent:.0f} %)",
            xbmc.LOGINFO,
        )

    def _load_json(self, key: str) -> list:
        try:
            raw = self._addon.getSetting(key) or "[]"
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, TypeError):
            return []


def run_service() -> None:
    """Entry point for xbmc.service extension."""
    monitor = PlaybackMonitor()
    monitor.waitForAbort()
