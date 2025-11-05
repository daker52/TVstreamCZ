"""Kodi routing layer for the TVStreamCZ add-on."""
from __future__ import annotations

import sys
import urllib.parse
import datetime
from typing import Dict, Optional

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

# Monkey-patch for older addons using xbmc.translatePath
if not hasattr(xbmc, 'translatePath'):
    xbmc.translatePath = xbmcvfs.translatePath

from .catalogue import WebshareCatalogue
from .metadata import MetadataManager
from .settings import AddonSettings
from .webshare_api import WebshareAPI, WebshareAuthError, WebshareError


class Plugin:
    def show_metadata_tv_category(self) -> None:
        """Show TV shows from a specific category."""
        category = self.params.get("category", "popular")
        page = int(self.params.get("page", "1"))
        if not self.metadata or not self.metadata.has_providers():
            self.notify("Metadata poskytovatelé nejsou k dispozici", level=xbmc.LOGWARNING)
            return
        method_map = {
            "popular": "get_popular_tv_shows",
            "top_rated": "get_top_rated_tv_shows",
            "airing_today": "get_airing_today_tv_shows",
            "on_the_air": "get_on_the_air_tv_shows"
        }
        method_name = method_map.get(category)
        if not method_name:
            return
        method = getattr(self.metadata, method_name, None)
        if not method:
            return
        try:
            shows = method(page)
            if not shows:
                self.notify("Žádné seriály nenalezeny", level=xbmc.LOGINFO)
                return
            self._show_metadata_content_list(shows, "tvshow", category, page)
        except Exception as e:
            self._logger(f"Error fetching TV shows category {category}: {e}", xbmc.LOGERROR)
            self.notify("Chyba při načítání seriálů", level=xbmc.LOGERROR)
    def __init__(self) -> None:
        self.addon = xbmcaddon.Addon()
        self.handle = int(sys.argv[1])
        self.base_url = sys.argv[0]
        self.params = dict(urllib.parse.parse_qsl(sys.argv[2][1:])) if len(sys.argv) > 2 else {}
        self.dialog = xbmcgui.Dialog()
        self._logger = lambda msg, level=xbmc.LOGDEBUG: xbmc.log(f"[TVStreamCZ] {msg}", level)
        
        # Load settings with error handling
        try:
            self.settings = AddonSettings.load(self.addon)
            self._logger("Settings loaded successfully")
        except Exception as e:
            self._logger(f"Failed to load settings: {str(e)}", xbmc.LOGERROR)
            # Create a minimal notification about the error
            xbmcgui.Dialog().notification("TVStreamCZ", "Settings loading error", xbmcgui.NOTIFICATION_ERROR)
            raise
        
        self.api = WebshareAPI(logger=self._logger)
        token = ""
        try:
            # Use the generic getSetting method for compatibility
            token = self.addon.getSetting("session_token") or ""
            self._logger(f"Session token loaded: {'Yes' if token else 'No'}")
        except (TypeError, AttributeError, RuntimeError) as e:
            self._logger(f"Failed to load session token: {str(e)}", xbmc.LOGWARNING)
            token = ""
        if token:
            self.api.set_token(token)
        self.metadata = MetadataManager(self.settings, self._logger) if self.settings.metadata_provider != "none" else None
        self.catalogue = WebshareCatalogue(self.api, self.metadata, self.settings, self._logger)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def build_url(self, query: Dict[str, object]) -> str:
        return f"{self.base_url}?{urllib.parse.urlencode(query)}"

    def notify(self, message: str, heading: Optional[str] = None, level: int = xbmc.LOGINFO) -> None:
        heading = heading or self.addon.getAddonInfo("name")
        self.dialog.notification(heading, message, xbmcgui.NOTIFICATION_INFO, 4500)
        self._logger(message, level)

    def _localized(self, string_id: int) -> str:
        return self.addon.getLocalizedString(string_id)

    def _ensure_credentials(self) -> bool:
        if not self.settings.username or not self.settings.password:
            self.notify(self._localized(32008), level=xbmc.LOGWARNING)
            return False
        return True

    def _ensure_session(self) -> bool:
        if not self._ensure_credentials():
            return False
        try:
            self.api.ensure_logged_in()
            return True
        except WebshareAuthError:
            try:
                token = self.api.login(self.settings.username, self.settings.password, self.settings.keep_logged_in)
            except WebshareError as exc:
                self.notify(str(exc), level=xbmc.LOGWARNING)
                return False
            try:
                # Use the generic setSetting method for compatibility
                self.addon.setSetting("session_token", token or "")
            except (TypeError, AttributeError, RuntimeError):
                pass  # Token saving failed, but continue
            return True
        except WebshareError as exc:
            self.notify(str(exc), level=xbmc.LOGWARNING)
            return False

    def _detect_dubbing(self, name: str) -> str:
        """Detect dubbing language from filename or title."""
        if not name or not isinstance(name, str):  # Handle None or non-string values
            return ""
        
        # Replace dots and underscores with spaces for better matching
        name_lower = name.lower().replace('.', ' ').replace('_', ' ')
        cz_keywords = ["cz dab", "cz dabing", "cz dub", "cz audio", "cz zvuk", "cz zvuky", "cesky dabing", "český dabing", "cz-dab", "cz dab"]
        en_keywords = ["en dab", "en dub", "en audio", "en zvuk", "anglicky dabing", "anglický dabing", "en-dub", "en dub"]
        for kw in cz_keywords:
            if kw in name_lower:
                return "CZ dabing"
        for kw in en_keywords:
            if kw in name_lower:
                return "EN dabing"
        return ""

    def _get_seasonal_query(self, season: str) -> str:
        """Generate search query for seasonal content."""
        seasonal_keywords = {
            "spring": ["jaro", "jarní", "spring", "easter", "velikonoce", "květen", "duben", "březen"],
            "summer": ["léto", "letní", "summer", "dovolená", "prázdniny", "červen", "červenec", "srpen"],  
            "autumn": ["podzim", "podzimní", "autumn", "fall", "září", "říjen", "listopad", "halloween"],
            "winter": ["zima", "zimní", "winter", "vánoce", "christmas", "prosinec", "leden", "únor", "sníh"]
        }
        
        keywords = seasonal_keywords.get(season, [])
        if keywords:
            # Use first few keywords for search
            return " OR ".join(keywords[:3])
        return ""

    def _create_list_item(self, item, media_type: Optional[str], is_playable: bool = True) -> xbmcgui.ListItem:
        label = item.metadata.get("title") if item.metadata else item.cleaned_title
        if not label:
            label = item.cleaned_title
        suffix_parts = []
        if item.season is not None and item.episode is not None:
            suffix_parts.append(f"S{item.season:02d}E{item.episode:02d}")
        if item.quality and isinstance(item.quality, str):
            suffix_parts.append(item.quality.upper())
        if item.audio_languages:
            suffix_parts.append("/".join(code.upper() for code in item.audio_languages if code and isinstance(code, str)))
        # Dabing detection
        dubbing = self._detect_dubbing(getattr(item, 'filename', label))
        if dubbing:
            suffix_parts.append(dubbing)
        if suffix_parts:
            label = f"{label} [{' | '.join(suffix_parts)}]"
        list_item = xbmcgui.ListItem(label=label)
        info: Dict[str, object] = {
            "title": item.metadata.get("title") if item.metadata else item.cleaned_title,
            "originaltitle": item.metadata.get("originaltitle") if item.metadata else item.cleaned_title,
            "plot": item.metadata.get("plot") if item.metadata else None,
            "year": item.metadata.get("year") if item.metadata else item.guessed_year,
            "genre": item.metadata.get("genres") if item.metadata else None,
            "rating": item.metadata.get("rating") if item.metadata else None,
            "votes": item.metadata.get("votes") if item.metadata else None,
            "country": item.metadata.get("country") if item.metadata else None,
            "size": item.size,
        }
        if media_type == "movie":
            info["mediatype"] = "movie"
        elif media_type == "tvshow":
            info["mediatype"] = "episode" if item.season is not None else "tvshow"
            if item.season is not None:
                info["season"] = item.season
            if item.episode is not None:
                info["episode"] = item.episode
            if item.metadata and item.metadata.get("title"):
                info["tvshowtitle"] = item.metadata.get("title")
        list_item.setInfo("video", {k: v for k, v in info.items() if v})
        art: Dict[str, str] = {}
        poster = None
        if item.metadata:
            poster = item.metadata.get("poster")
            if poster:
                art["poster"] = poster
                art["thumb"] = poster
            fanart = item.metadata.get("fanart")
            if fanart:
                art["fanart"] = fanart
        if not poster and item.preview_image:
            art["thumb"] = item.preview_image
        list_item.setArt(art)
        if is_playable:
            list_item.setProperty("IsPlayable", "true")
            list_item.setProperty("SupportsRandomAccess", "false")
            list_item.setProperty("CanPause", "true")
            list_item.setProperty("CanSeek", "true")
        return list_item

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------
    def run(self) -> None:
        action = self.params.get("action")
        self._logger(f"Plugin run() called with action: {action}, params: {self.params}", xbmc.LOGINFO)
        if action == "browse":
            self.show_browse()
        elif action == "media_root":
            self.show_media_root(self.params.get("media_type"))
        elif action == "alphabet":
            self.show_alphabet(self.params.get("media_type"))
        elif action == "genres":
            self.show_genres(self.params.get("media_type"))
        elif action == "quality_menu":
            self.show_quality_menu(self.params.get("media_type"))
        elif action == "audio_menu":
            self.show_audio_menu(self.params.get("media_type"))
        elif action == "subtitle_menu":
            self.show_subtitle_menu(self.params.get("media_type"))
        elif action == "filters":
            self.show_filters_menu(self.params.get("media_type"))
        elif action == "search":
            self.show_search(self.params.get("media_type"))
        elif action == "show_series":
            self.show_series_list()
        elif action == "show_seasons":
            self.show_seasons(self.params.get("series_name"))
        elif action == "show_episodes":
            self.show_episodes(self.params.get("series_name"), self.params.get("season"))
        elif action == "show_metadata_seasons":
            self.show_metadata_seasons()
        elif action == "show_metadata_episodes":
            self.show_metadata_episodes()
        elif action == "search_and_play_episode":
            self.search_and_play_episode()
        elif action == "metadata_categories":
            self.show_metadata_categories()
        elif action == "metadata_movies":
            self.show_metadata_movies()
        elif action == "metadata_tvshows":
            self.show_metadata_tvshows()
        elif action == "metadata_movie_category":
            self.show_metadata_movie_category()
        elif action == "metadata_tv_category":
            self.show_metadata_tv_category()
        elif action == "metadata_genre_movies":
            self.show_metadata_genre_movies()
        elif action == "metadata_genre_tvshows":
            self.show_metadata_genre_tvshows()
        elif action == "metadata_content":
            self.show_metadata_content()
        elif action == "seasonal_content":
            self.show_seasonal_content()
        elif action == "show_history":
            self.show_history()
        elif action == "show_recent":
            self.show_recent_history()
        elif action == "show_frequent":
            self.show_frequent_history()
        elif action == "show_favorites":
            self.show_favorites()
        elif action == "show_resume":
            self.show_resume_points()
        elif action == "show_stats":
            self.show_playback_stats()
        elif action == "clear_history":
            self.clear_history()
        elif action == "add_favorite":
            self.add_to_favorites()
        elif action == "quick_movie_search":
            self.quick_movie_search()
        elif action == "show_info":
            self.show_info()
        elif action == "show_settings":
            self.show_settings()
        elif action == "check_updates":
            self.check_updates()
        elif action == "play":
            self._logger("SUCCESS: 'play' action recognized, calling play_item()", xbmc.LOGINFO)
            self.play_item()
        else:
            self._logger(f"WARNING: Unknown action '{action}', showing root menu", xbmc.LOGWARNING)
            self.show_root()

    def show_root(self) -> None:
        xbmcplugin.setPluginCategory(self.handle, self.addon.getAddonInfo("name"))
        xbmcplugin.setContent(self.handle, "videos")
        entries = [
            ("FILMY", {"action": "metadata_movies"}),
            ("SERIÁLY", {"action": "metadata_tvshows"}),
            ("HISTORIE PŘEHRÁVÁNÍ (v přípravě)", {"action": "show_history"}),
            ("VÝBĚR DLE ROČNÍHO OBDOBÍ", {"action": "seasonal_content"}),
            ("INFORMACE", {"action": "show_info"}),
            ("NASTAVENÍ PLUGINU", {"action": "show_settings"}),
            ("AKTUALIZACE", {"action": "check_updates"}),
            (self._localized(32006), {"action": "search"}),
        ]
        for label, query in entries:
            url = self.build_url(query)
            item = xbmcgui.ListItem(label=label)
            xbmcplugin.addDirectoryItem(self.handle, url, item, isFolder=True)
        xbmcplugin.endOfDirectory(self.handle)

    def show_media_root(self, media_type: Optional[str]) -> None:
        if not media_type:
            self.show_root()
            return
        xbmcplugin.setPluginCategory(self.handle, self._localized(32000 if media_type == "movie" else 32001))
        xbmcplugin.setContent(self.handle, "videos")
        items = [
            (self._localized(32023), {"action": "browse", "media_type": media_type, "sort": "recent"}),
            (self._localized(32002), {"action": "browse", "media_type": media_type}),
            (self._localized(32003), {"action": "alphabet", "media_type": media_type}),
            (self._localized(32004), {"action": "genres", "media_type": media_type}),
            (self._localized(32027), {"action": "filters", "media_type": media_type}),
            (self._localized(32006), {"action": "search", "media_type": media_type}),
        ]
        for label, params in items:
            url = self.build_url(params)
            xbmcplugin.addDirectoryItem(self.handle, url, xbmcgui.ListItem(label=label), isFolder=True)
        xbmcplugin.endOfDirectory(self.handle)

    def show_alphabet(self, media_type: Optional[str]) -> None:
        if not media_type:
            self.show_root()
            return
        xbmcplugin.setPluginCategory(self.handle, self._localized(32003))
        xbmcplugin.setContent(self.handle, "videos")
        letters = [chr(code) for code in range(ord("A"), ord("Z") + 1)] + ["0-9"]
        for letter in letters:
            params = {
                "action": "browse",
                "media_type": media_type,
                "letter": letter,
            }
            url = self.build_url(params)
            xbmcplugin.addDirectoryItem(self.handle, url, xbmcgui.ListItem(label=letter), isFolder=True)
        xbmcplugin.endOfDirectory(self.handle)

    def show_filters_menu(self, media_type: Optional[str]) -> None:
        if not media_type:
            self.show_root()
            return
        xbmcplugin.setPluginCategory(self.handle, self._localized(32027))
        xbmcplugin.setContent(self.handle, "videos")
        entries = [
            (self._localized(32028), {"action": "quality_menu", "media_type": media_type}),
            (self._localized(32011), {"action": "audio_menu", "media_type": media_type}),
            (self._localized(32012), {"action": "subtitle_menu", "media_type": media_type}),
        ]
        for label, params in entries:
            url = self.build_url(params)
            xbmcplugin.addDirectoryItem(self.handle, url, xbmcgui.ListItem(label=label), isFolder=True)
        xbmcplugin.endOfDirectory(self.handle)

    def show_quality_menu(self, media_type: Optional[str]) -> None:
        if not media_type:
            self.show_root()
            return
        xbmcplugin.setPluginCategory(self.handle, self._localized(32013))
        xbmcplugin.setContent(self.handle, "videos")
        options = [
            (self._localized(32036), "any"),
            (self._localized(32037), "hd"),
            (self._localized(32038), "uhd"),
            (self._localized(32039), "sd"),
        ]
        for label, quality in options:
            params = {
                "action": "browse",
                "media_type": media_type,
            }
            if quality:
                params["quality"] = quality
            url = self.build_url(params)
            xbmcplugin.addDirectoryItem(self.handle, url, xbmcgui.ListItem(label=label), isFolder=True)
        xbmcplugin.endOfDirectory(self.handle)

    def show_audio_menu(self, media_type: Optional[str]) -> None:
        if not media_type:
            self.show_root()
            return
        xbmcplugin.setPluginCategory(self.handle, self._localized(32011))
        xbmcplugin.setContent(self.handle, "videos")
        options = [
            (self._localized(32041), "any"),
            (self._localized(32014), "cz"),
            (self._localized(32016), "sk"),
            (self._localized(32015), "en"),
        ]
        for label, audio in options:
            params = {"action": "browse", "media_type": media_type}
            if audio:
                params["audio"] = audio
            url = self.build_url(params)
            xbmcplugin.addDirectoryItem(self.handle, url, xbmcgui.ListItem(label=label), isFolder=True)
        xbmcplugin.endOfDirectory(self.handle)

    def show_subtitle_menu(self, media_type: Optional[str]) -> None:
        if not media_type:
            self.show_root()
            return
        xbmcplugin.setPluginCategory(self.handle, self._localized(32012))
        xbmcplugin.setContent(self.handle, "videos")
        options = [
            (self._localized(32041), "any"),
            (self._localized(32014), "cz"),
            (self._localized(32016), "sk"),
            (self._localized(32015), "en"),
        ]
        for label, subs in options:
            params = {"action": "browse", "media_type": media_type}
            if subs:
                params["subtitles"] = subs
            url = self.build_url(params)
            xbmcplugin.addDirectoryItem(self.handle, url, xbmcgui.ListItem(label=label), isFolder=True)
        xbmcplugin.endOfDirectory(self.handle)

    def show_genres(self, media_type: Optional[str]) -> None:
        if not media_type:
            self.show_root()
            return
            
        # Try to get genres from metadata provider first
        genres = None
        if self.metadata and self.metadata.has_providers():
            genres = self.catalogue.available_genres(media_type)
            
        # If no metadata provider or no genres from metadata, use basic genre list
        if not genres:
            # Basic genre list for movies and TV shows
            if media_type == "movie":
                genres = ["Action", "Adventure", "Animation", "Comedy", "Crime", "Documentary", 
                         "Drama", "Family", "Fantasy", "History", "Horror", "Music", "Mystery", 
                         "Romance", "Science Fiction", "Thriller", "War", "Western"]
            elif media_type == "tvshow":
                genres = ["Action & Adventure", "Animation", "Comedy", "Crime", "Documentary", 
                         "Drama", "Family", "Kids", "Mystery", "News", "Reality", "Sci-Fi & Fantasy", 
                         "Soap", "Talk", "War & Politics", "Western"]
            else:
                genres = ["Action", "Comedy", "Drama", "Horror", "Thriller"]
                
        if not genres:
            self.notify("No genres available", level=xbmc.LOGINFO)
            xbmcplugin.endOfDirectory(self.handle)
            return
        xbmcplugin.setPluginCategory(self.handle, self._localized(32004))
        xbmcplugin.setContent(self.handle, "videos")
        for genre in genres:
            params = {"action": "browse", "media_type": media_type, "genre": genre.lower()}
            url = self.build_url(params)
            xbmcplugin.addDirectoryItem(self.handle, url, xbmcgui.ListItem(label=genre), isFolder=True)
        xbmcplugin.endOfDirectory(self.handle)

    def show_search(self, media_type: Optional[str]) -> None:
        query = self.dialog.input(self._localized(32007))
        if not query:
            return
        
        # For TV shows, try metadata-first approach
        if media_type == "tvshow" or not media_type:
            # First try to find TV series via metadata
            if self.metadata and self.metadata.has_providers():
                self._logger(f"Trying metadata-first search for: '{query}'", xbmc.LOGINFO)
                try:
                    series_data = self.metadata.search_tv_series(query)
                    if series_data and series_data.get('seasons'):
                        seasons_count = len(series_data.get('seasons', []))
                        self._logger(f"✅ Found TV series via metadata: '{series_data.get('name')}' with {seasons_count} seasons", xbmc.LOGINFO)
                        
                        # Store series data for later use
                        self.params = {
                            "action": "show_metadata_seasons", 
                            "series_name": series_data.get('name', query),
                            "series_id": series_data.get('id'),
                            "original_query": query
                        }
                        self.show_metadata_seasons()
                        return
                    else:
                        self._logger(f"❌ No metadata found for '{query}' - falling back to Webshare", xbmc.LOGINFO)
                except Exception as e:
                    self._logger(f"❌ Metadata search failed for '{query}': {e}", xbmc.LOGWARNING)
            else:
                self._logger(f"No metadata providers available - using Webshare directly", xbmc.LOGINFO)
        
        # Fallback to original Webshare search
        self._logger(f"Using Webshare search for: {query}", xbmc.LOGINFO)
        self.params = {"action": "browse", "query": query}
        if media_type:
            self.params["media_type"] = media_type
        self.show_browse()

    def show_browse(self) -> None:
        media_type = self.params.get("media_type")
        query = self.params.get("query", "")
        
        self._logger(f"show_browse: media_type={media_type}, query={query}", xbmc.LOGINFO)
        
        # If no media_type specified but we have a query, check what type of content we found
        if not media_type and query:
            self._logger("Detecting content type from search results", xbmc.LOGINFO)
            # Quick fetch to determine content type
            test_items, _, _, _ = self.catalogue.fetch(
                query=query,
                start_offset=0,
                page_size=10
            )
            # If most items are TV shows, treat as TV content
            if test_items:
                tv_count = sum(1 for item in test_items if item.media_type == "tvshow")
                self._logger(f"Found {len(test_items)} items, {tv_count} are TV shows", xbmc.LOGINFO)
                if tv_count >= len(test_items) / 2:  # More than half are TV shows
                    media_type = "tvshow"
                    self.params["media_type"] = "tvshow"
                    self._logger("Detected as TV content, redirecting to series list", xbmc.LOGINFO)
        
        # For TV shows, redirect to structured series list ONLY if no direct query specified
        if media_type == "tvshow" and not query:
            self._logger("Redirecting to show_series_list (no query)", xbmc.LOGINFO)
            self.show_series_list()
            return
            
        letter = self.params.get("letter")
        quality = self.params.get("quality") or self.settings.default_quality
        audio = self.params.get("audio") or self.settings.default_audio
        subtitles = self.params.get("subtitles") or self.settings.default_subtitles
        genre = self.params.get("genre")
        sort = self.params.get("sort")
        query = self.params.get("query") or ""
        seasonal = self.params.get("seasonal")
        offset = int(self.params.get("offset", "0"))
        
        # Handle seasonal content search
        if seasonal:
            query = self._get_seasonal_query(seasonal)
        # Optimize page size for direct searches
        page_size = 20  # Default page size
        if query and offset == 0:  # Direct search, first page
            if media_type == "movie":
                page_size = 15  # Smaller for movies for faster loading
            
        xbmcplugin.setPluginCategory(self.handle, self._localized(32000 if media_type == "movie" else 32001))
        if media_type == "movie":
            xbmcplugin.setContent(self.handle, "movies")
        elif media_type == "tvshow":
            xbmcplugin.setContent(self.handle, "episodes")
        else:
            xbmcplugin.setContent(self.handle, "videos")
        items, next_offset, total, has_more = self.catalogue.fetch(
            media_type=media_type,
            query=query,
            letter=letter,
            sort=sort,
            quality=quality if quality != "any" else None,
            audio=audio if audio != "any" else None,
            subtitles=subtitles if subtitles != "any" else None,
            genre=genre,
            start_offset=offset,
            page_size=page_size,
        )
        if not items:
            xbmcplugin.endOfDirectory(self.handle)
            if offset == 0:
                self.notify(self._localized(32020), level=xbmc.LOGINFO)
            return
        # If only a few items found and it's a direct search, show as directory for user choice
        if query and len(items) <= 12 and not has_more:
            # For small result sets, show as regular directory so user can see all options
            pass  # Continue to show directory listing below
            
        for item in items:
            ident = getattr(item, "ident", None)
            if not ident:
                continue  # skip items without ident
            list_item = self._create_list_item(item, media_type)
            
            # Add context information for history tracking
            play_params = {
                "action": "play", 
                "ident": ident, 
                "media_type": media_type
            }
            
            # Add title and other metadata for history
            if hasattr(item, 'metadata') and item.metadata:
                title = item.metadata.get("title")
                year = item.metadata.get("year")
            elif hasattr(item, 'cleaned_title'):
                title = item.cleaned_title
                year = getattr(item, 'guessed_year', None)
            else:
                title = str(item)
                year = None
                
            if title:
                play_params["context_title"] = title
            if year:
                play_params["context_year"] = year
            if hasattr(item, 'season') and item.season:
                play_params["season"] = item.season
            if hasattr(item, 'episode') and item.episode:
                play_params["episode"] = item.episode
            
            url = self.build_url(play_params)
            xbmcplugin.addDirectoryItem(self.handle, url, list_item, isFolder=False)
        if has_more:
            params = {
                "action": "browse",
                "media_type": media_type,
                "query": query,
                "letter": letter,
                "genre": genre,
                "sort": sort,
                "offset": next_offset,
            }
            if quality is not None:
                params["quality"] = quality
            if audio is not None:
                params["audio"] = audio
            if subtitles is not None:
                params["subtitles"] = subtitles
            params = {k: v for k, v in params.items() if v not in (None, "")}
            next_url = self.build_url(params)
            xbmcplugin.addDirectoryItem(
                self.handle,
                next_url,
                xbmcgui.ListItem(label=self._localized(32010)),
                isFolder=True,
            )
        xbmcplugin.endOfDirectory(self.handle)

    def play_item(self) -> None:
        ident = self.params.get("ident")
        self._logger(f"play_item called with ident: {ident}", xbmc.LOGINFO)
        self._resolve_and_play(ident)

    def _resolve_and_play(self, ident: str) -> None:
        self._logger(f"_resolve_and_play called with ident: {ident}", xbmc.LOGINFO)
        if not ident:
            self._logger("ERROR: Missing file identifier - ident is None or empty", xbmc.LOGERROR)
            self.notify("Missing file identifier", level=xbmc.LOGWARNING)
            xbmcplugin.setResolvedUrl(self.handle, False, xbmcgui.ListItem())
            return
        if not self._ensure_session():
            self._logger("ERROR: Session ensure failed - authentication problem", xbmc.LOGERROR)
            xbmcplugin.setResolvedUrl(self.handle, False, xbmcgui.ListItem())
            return
        try:
            link = self.api.file_link(
                ident,
                download_type=self.settings.download_type,
                force_https=self.settings.force_https,
            )
        except WebshareError as exc:
            self._logger(f"ERROR: WebshareError when getting file link: {exc}", xbmc.LOGERROR)
            self.notify(str(exc), level=xbmc.LOGWARNING)
            xbmcplugin.setResolvedUrl(self.handle, False, xbmcgui.ListItem())
            return
        self._logger(f"SUCCESS: Got file link: {link}", xbmc.LOGINFO)
        list_item = xbmcgui.ListItem(path=link)
        list_item.setProperty("IsPlayable", "true")
        
        # Record to history before playing
        try:
            self._record_playback_history(ident)
        except Exception as e:
            self._logger(f"Warning: Failed to record history: {e}", xbmc.LOGWARNING)
        
        self._logger("SUCCESS: Calling setResolvedUrl with success=True", xbmc.LOGINFO)
        xbmcplugin.setResolvedUrl(self.handle, True, list_item)
        self._logger("SUCCESS: setResolvedUrl completed", xbmc.LOGINFO)

    def show_series_list(self) -> None:
        """Show list of TV series - optimized for search."""
        query = self.params.get("query") or ""
        
        if query:
            # Direct search mode - show one result per series found
            self._show_search_series_results(query)
        else:
            # Browse mode - show popular/recent series
            self._show_browse_series_list()
    
    def _show_search_series_results(self, query: str) -> None:
        """Show series matching the search query."""
        self._logger(f"_show_search_series_results: query={query}", xbmc.LOGINFO)
        
        # Quick search for series
        items, _, _, _ = self.catalogue.fetch(
            media_type="tvshow",
            query=query,
            start_offset=0,
            page_size=50  # Smaller initial fetch
        )
        
        self._logger(f"Fetched {len(items) if items else 0} TV items for query: {query}", xbmc.LOGINFO)
        
        if not items:
            xbmcplugin.endOfDirectory(self.handle)
            self.notify("Žádné seriály nenalezeny", level=xbmc.LOGINFO)
            return
        
        # Extract unique series names
        series_names = set()
        series_examples = {}
        
        for item in items:
            # Clean series name
            series_name = self._extract_series_name(item.cleaned_title)
            self._logger(f"Item: '{item.cleaned_title}' -> series: '{series_name}'", xbmc.LOGINFO)
            
            if series_name and series_name.lower() not in [s.lower() for s in series_names]:
                series_names.add(series_name)
                series_examples[series_name] = item
        
        self._logger(f"Found {len(series_names)} unique series: {list(series_names)}", xbmc.LOGINFO)
        
        if not series_names:
            xbmcplugin.endOfDirectory(self.handle)
            self.notify("Žádné seriály nenalezeny", level=xbmc.LOGINFO)
            return
            
        # Show found series as playable items instead of empty directory
        xbmcplugin.setPluginCategory(self.handle, f"Nalezené seriály ({len(series_names)})")
        xbmcplugin.setContent(self.handle, "episodes")
        
        for series_name in sorted(series_names):
            example_item = series_examples.get(series_name)
            if example_item:
                list_item = self._create_list_item(example_item, "tvshow", is_playable=False)
                list_item.setLabel(f"{series_name} - ukázka")
                url = self.build_url({
                    "action": "show_seasons", 
                    "series_name": series_name
                })
                xbmcplugin.addDirectoryItem(self.handle, url, list_item, isFolder=True)
        
        xbmcplugin.endOfDirectory(self.handle)
    
    def _show_browse_series_list(self) -> None:
        """Show series list for browsing (without specific query)."""
        # For browsing, we need to be more careful about loading
        self.notify("Pro rychlejší výsledky použijte vyhledávání", level=xbmc.LOGINFO)
        xbmcplugin.endOfDirectory(self.handle)
    
    def _extract_series_name(self, title: str) -> str:
        """Extract clean series name from title."""
        # Remove common season/episode patterns
        import re
        
        # Remove patterns like "S01E01", "1x01", "Series 1", etc.
        patterns = [
            r'\s*-?\s*S\d+E\d+.*$',  # S01E01...
            r'\s*-?\s*\d+x\d+.*$',   # 1x01...  
            r'\s*-?\s*[Ss]ér[ií]e?\s*\d+.*$',  # Série 1...
            r'\s*-?\s*[Ss]eason\s*\d+.*$',     # Season 1...
            r'\s*-?\s*S\d+.*$',      # S1, S01...
            r'\s*-?\s*\(\d{4}\).*$', # (2020)...
            r'\s*-?\s*E\d+.*$',      # E01...
            r'\s*-?\s*ep\s*\d+.*$',  # ep01...
            r'\s*-?\s*díl\s*\d+.*$', # díl 1...
        ]
        
        clean_title = title
        for pattern in patterns:
            clean_title = re.sub(pattern, '', clean_title, flags=re.IGNORECASE)
        
        return clean_title.strip()

    def show_seasons(self, series_name: str) -> None:
        """Show seasons for a specific TV series using metadata."""
        self._logger(f"show_seasons called with series_name='{series_name}'", xbmc.LOGINFO)
        
        if not series_name:
            self._logger("No series_name provided, returning to series list", xbmc.LOGWARNING)
            self.show_series_list()
            return
        
        xbmcplugin.setPluginCategory(self.handle, series_name)
        xbmcplugin.setContent(self.handle, "seasons")
        
        # Try to get series info from metadata if available
        seasons_info = None
        if self.metadata and self.metadata.has_providers():
            try:
                # Search for series metadata
                metadata_result = self.metadata.search_tv_series(series_name)
                if metadata_result:
                    seasons_info = metadata_result.get('seasons', [])
            except Exception as e:
                self._logger(f"Failed to get metadata for {series_name}: {e}", xbmc.LOGWARNING)
        
        # If we have metadata seasons info, use it
        if seasons_info and len(seasons_info) > 0:
            for season_info in seasons_info:
                season_num = season_info.get('season_number', 1)
                episode_count = season_info.get('episode_count', 0)
                season_label = f"Série {season_num}"
                
                list_item = xbmcgui.ListItem(label=season_label)
                list_item.setInfo('video', {
                    'title': season_label,
                    'season': season_num,
                    'mediatype': 'season',
                    'plot': f'Série {season_num} - {episode_count} epizod' if episode_count else f'Série {season_num}'
                })
                
                # Try to get season poster
                if season_info.get('poster_path'):
                    list_item.setArt({'thumb': f"https://image.tmdb.org/t/p/w500{season_info['poster_path']}"})
                
                url = self.build_url({
                    "action": "show_episodes",
                    "series_name": series_name,
                    "season": season_num
                })
                xbmcplugin.addDirectoryItem(self.handle, url, list_item, isFolder=True)
        else:
            # Fallback: discover seasons by searching for episodes
            discovered_seasons = self._discover_seasons(series_name)
            
            if not discovered_seasons:
                # If no seasons found, add default season 1
                discovered_seasons = [1]
            
            for season_num in sorted(discovered_seasons):
                season_label = f"Série {season_num}"
                list_item = xbmcgui.ListItem(label=season_label)
                list_item.setInfo('video', {
                    'title': season_label,
                    'season': season_num,
                    'mediatype': 'season'
                })
                
                url = self.build_url({
                    "action": "show_episodes", 
                    "series_name": series_name,
                    "season": season_num
                })
                xbmcplugin.addDirectoryItem(self.handle, url, list_item, isFolder=True)
        
        xbmcplugin.endOfDirectory(self.handle)
    
    def _discover_seasons(self, series_name: str) -> list:
        """Discover available seasons by doing a quick search."""
        # Quick search to find what seasons exist
        query_terms = [series_name, f"{series_name} S01", f"{series_name} série"]
        seasons_found = set()
        
        for term in query_terms:
            try:
                items, _, _, _ = self.catalogue.fetch(
                    media_type="tvshow",
                    query=term,
                    start_offset=0,
                    page_size=20  # Small sample
                )
                
                for item in items:
                    if self._extract_series_name(item.cleaned_title).lower() == series_name.lower():
                        if item.season:
                            seasons_found.add(item.season)
                        else:
                            # Try to extract season from title
                            import re
                            season_match = re.search(r'[Ss]\s*(\d+)', item.cleaned_title)
                            if season_match:
                                seasons_found.add(int(season_match.group(1)))
                            else:
                                seasons_found.add(1)  # Default season 1
                        
                if len(seasons_found) >= 3:  # Found enough, stop searching
                    break
                    
            except Exception as e:
                self._logger(f"Error discovering seasons for {series_name}: {e}", xbmc.LOGWARNING)
                continue
        
        return list(seasons_found) if seasons_found else [1]

    def show_episodes(self, series_name: str, season: str) -> None:
        """Show episodes for a specific season - optimized search."""
        if not series_name or not season:
            self.show_series_list()
            return
            
        season_num = int(season) if season else 1
        
        xbmcplugin.setPluginCategory(self.handle, f"{series_name} - Série {season_num}")
        xbmcplugin.setContent(self.handle, "episodes")
        
        # Targeted search for this specific season
        episodes = self._search_season_episodes(series_name, season_num)
        
        if not episodes:
            xbmcplugin.endOfDirectory(self.handle)
            self.notify(f"Žádné epizody nenalezeny pro {series_name} Série {season_num}", level=xbmc.LOGINFO)
            return
        
        # Sort episodes by episode number
        episodes.sort(key=lambda x: x.episode or 0)
        
        # Show episodes
        for item in episodes:
            episode_label = self._format_episode_label(item, season_num)
            list_item = self._create_list_item(item, "tvshow")
            list_item.setLabel(episode_label)
            list_item.setInfo('video', {
                'title': episode_label,
                'season': season_num,
                'episode': item.episode or 0,
                'mediatype': 'episode'
            })
            
            # Add context information for history tracking
            play_params = {
                "action": "play", 
                "ident": item.ident, 
                "media_type": "tvshow",
                "context_title": f"{series_name} - {episode_label}",
                "season": season_num,
                "episode": item.episode or 0
            }
            
            # Add year if available
            if hasattr(item, 'metadata') and item.metadata and item.metadata.get("year"):
                play_params["context_year"] = item.metadata.get("year")
            elif hasattr(item, 'guessed_year') and item.guessed_year:
                play_params["context_year"] = item.guessed_year
            
            url = self.build_url(play_params)
            xbmcplugin.addDirectoryItem(self.handle, url, list_item, isFolder=False)
        
        xbmcplugin.endOfDirectory(self.handle)
    
    def _search_season_episodes(self, series_name: str, season_num: int) -> list:
        """Search for episodes of specific season using targeted queries."""
        episodes = []
        
        # Different search patterns for finding episodes
        search_patterns = [
            f"{series_name} S{season_num:02d}",     # "Series S01"
            f"{series_name} S{season_num}",         # "Series S1" 
            f"{series_name} série {season_num}",    # "Series série 1"
            f"{series_name} season {season_num}",   # "Series season 1"
        ]
        
        found_items = set()  # Track items by ident to avoid duplicates
        
        for pattern in search_patterns:
            try:
                items, _, _, _ = self.catalogue.fetch(
                    media_type="tvshow",
                    query=pattern,
                    start_offset=0,
                    page_size=50
                )
                
                for item in items:
                    # Check if this item belongs to our series and season
                    if (item.ident not in found_items and 
                        self._item_matches_series_season(item, series_name, season_num)):
                        episodes.append(item)
                        found_items.add(item.ident)
                        
            except Exception as e:
                self._logger(f"Error searching for {pattern}: {e}", xbmc.LOGWARNING)
                continue
                
            # If we found enough episodes, we can stop
            if len(episodes) >= 20:
                break
        
        return episodes
    
    def _item_matches_series_season(self, item, series_name: str, season_num: int) -> bool:
        """Check if an item matches the specified series and season."""
        # Extract series name from item
        item_series = self._extract_series_name(item.cleaned_title)
        
        # Check series name match (case insensitive)
        if item_series.lower() != series_name.lower():
            return False
        
        # Check season match
        if item.season and item.season == season_num:
            return True
            
        # Try to extract season from title if item.season is not set
        import re
        season_patterns = [
            rf'[Ss]\s*{season_num:02d}',  # S01, s01
            rf'[Ss]\s*{season_num}',      # S1, s1
            rf'[Ss]ér[ií]e?\s*{season_num}',  # série 1, serie 1
            rf'[Ss]eason\s*{season_num}',     # season 1
        ]
        
        for pattern in season_patterns:
            if re.search(pattern, item.cleaned_title, re.IGNORECASE):
                return True
                
        return False
    
    def _format_episode_label(self, item, season_num: int) -> str:
        """Format episode label for display."""
        if item.episode:
            return f"Epizoda {item.episode}"
        
        # Try to extract episode number from title
        import re
        ep_match = re.search(r'[Ee]\s*(\d+)', item.cleaned_title)
        if ep_match:
            return f"Epizoda {ep_match.group(1)}"
        
        # Try to extract from SxxExx pattern
        se_match = re.search(rf'S\s*{season_num:02d}?\s*E\s*(\d+)', item.cleaned_title, re.IGNORECASE)
        if se_match:
            return f"Epizoda {se_match.group(1)}"
            
        # Fallback to cleaned title
        return item.cleaned_title
    
    def show_metadata_seasons(self) -> None:
        """Show seasons based on metadata (not Webshare files)."""
        series_name = self.params.get("series_name", "")
        series_id = self.params.get("series_id")
        original_query = self.params.get("original_query", "")
        
        self._logger(f"show_metadata_seasons: series={series_name}, id={series_id}", xbmc.LOGINFO)
        
        if not series_name:
            return
            
        # Get series data from metadata
        if self.metadata and self.metadata.has_providers():
            series_data = self.metadata.search_tv_series(series_name)
            if not series_data:
                # Fallback to Webshare search
                self._logger("No metadata found, falling back to Webshare", xbmc.LOGINFO)
                self.params = {"action": "browse", "query": original_query, "media_type": "tvshow"}
                self.show_browse()
                return
                
            seasons = series_data.get('seasons', [])
            if not seasons:
                self._logger("No seasons found in metadata", xbmc.LOGWARNING)
                return
                
            xbmcplugin.setPluginCategory(self.handle, series_name)
            xbmcplugin.setContent(self.handle, "seasons")
            
            # Show seasons from metadata
            for season_info in seasons:
                season_num = season_info.get('season_number', 1)
                episode_count = season_info.get('episode_count', 0)
                season_name = season_info.get('name', f"Série {season_num}")
                
                list_item = xbmcgui.ListItem(label=season_name)
                list_item.setInfo('video', {
                    'title': season_name,
                    'season': season_num,
                    'mediatype': 'season',
                    'plot': f'{season_name} - {episode_count} epizod' if episode_count else season_name
                })
                
                # Add season poster if available
                if season_info.get('poster_path'):
                    list_item.setArt({'thumb': f"https://image.tmdb.org/t/p/w500{season_info['poster_path']}"})
                elif series_data.get('poster_path'):
                    list_item.setArt({'thumb': f"https://image.tmdb.org/t/p/w500{series_data['poster_path']}"})
                
                url = self.build_url({
                    "action": "show_metadata_episodes",
                    "series_name": series_name,
                    "series_id": series_id or series_data.get('id'),
                    "season": season_num,
                    "original_query": original_query,
                    "csfd_url": series_data.get('csfd_url', '')
                })
                xbmcplugin.addDirectoryItem(self.handle, url, list_item, isFolder=True)
            
        xbmcplugin.endOfDirectory(self.handle)
    
    def show_metadata_episodes(self) -> None:
        """Show episodes based on metadata, with Webshare search on click."""
        series_name = self.params.get("series_name", "")
        series_id = self.params.get("series_id")
        season = int(self.params.get("season", "1"))
        original_query = self.params.get("original_query", "")
        csfd_url = self.params.get("csfd_url", "")
        
        self._logger(f"show_metadata_episodes: series={series_name}, season={season}", xbmc.LOGINFO)
        
        if not series_name or not series_id:
            return
            
        # Get episode data from metadata
        if self.metadata and self.metadata.has_providers():
            episodes = None
            
            # Try to get episodes from appropriate provider
            for provider in self.metadata._providers:
                if provider.name == "csfd" and csfd_url:
                    # Use ČSFD-specific method for getting episodes
                    episodes = provider.get_csfd_season_episodes(int(series_id), season, csfd_url)
                    if episodes:
                        self._logger(f"Got {len(episodes)} episodes from ČSFD", xbmc.LOGINFO)
                        break
                else:
                    # Use standard TMDb method
                    episodes = provider.get_season_episodes(int(series_id), season)
                    if episodes:
                        self._logger(f"Got {len(episodes)} episodes from {provider.name}", xbmc.LOGINFO)
                        break
            
            # Fallback to generic metadata method
            if not episodes:
                episodes = self.metadata.get_season_episodes(int(series_id), season)
            
            if not episodes:
                self._logger("No episodes found in metadata", xbmc.LOGWARNING)
                # Fallback to Webshare search for this season
                season_query = f"{original_query} S{season:02d}"
                self.params = {"action": "browse", "query": season_query, "media_type": "tvshow"}
                self.show_browse()
                return
                
            xbmcplugin.setPluginCategory(self.handle, f"{series_name} - Série {season}")
            xbmcplugin.setContent(self.handle, "episodes")
            
            # Show episodes from metadata
            for episode_info in episodes:
                episode_num = episode_info.get('episode_number', 1)
                episode_name = episode_info.get('name', f"Epizoda {episode_num}")
                episode_plot = episode_info.get('overview', '')
                
                display_name = f"{episode_num}. {episode_name}"
                
                list_item = xbmcgui.ListItem(label=display_name)
                list_item.setInfo('video', {
                    'title': episode_name,
                    'episode': episode_num,
                    'season': season,
                    'mediatype': 'episode',
                    'plot': episode_plot,
                    'tvshowtitle': series_name
                })

                # Add episode thumbnail if available
                if episode_info.get('still_path'):
                    list_item.setArt({'thumb': f"https://image.tmdb.org/t/p/w500{episode_info['still_path']}"})

                # When clicked, search Webshare for this specific episode
                episode_query = f"{original_query} S{season:02d}E{episode_num:02d}"
                url = self.build_url({
                    "action": "search_and_play_episode",
                    "query": episode_query,
                    "series_name": series_name,
                    "season": season,
                    "episode": episode_num
                })
                list_item.setProperty("IsPlayable", "true")
                xbmcplugin.addDirectoryItem(self.handle, url, list_item, isFolder=False)
            
        xbmcplugin.endOfDirectory(self.handle)
    
    def search_and_play_episode(self) -> None:
        """Search Webshare for specific episode and show stream selection dialog."""
        query = self.params.get("query", "")
        series_name = self.params.get("series_name", "")
        season = self.params.get("season", "")
        episode = self.params.get("episode", "")
        
        self._logger(f"search_and_play_episode: {query}", xbmc.LOGINFO)
        
        if not query:
            xbmcplugin.setResolvedUrl(self.handle, False, xbmcgui.ListItem())
            return
        
        # Search with exact episode pattern
        items, _, _, _ = self.catalogue.fetch(
            query=query,
            start_offset=0,
            page_size=50
        )
        
        if not items:
            # Try broader search without episode number
            broader_query = f"{series_name} S{season}"
            self._logger(f"No exact matches, trying broader search: {broader_query}", xbmc.LOGINFO)
            items, _, _, _ = self.catalogue.fetch(
                query=broader_query,
                start_offset=0,
                page_size=50
            )
        
        if not items:
            self.notify(f"Epizoda S{season}E{episode} nenalezena", level=xbmc.LOGINFO)
            xbmcplugin.setResolvedUrl(self.handle, False, xbmcgui.ListItem())
            return
        
        # If only one item, play it directly
        if len(items) == 1:
            self._play_item(items[0])
        else:
            # Multiple items - pick the best quality one
            best_item = self._select_best_stream(items)
            if best_item:
                self._play_item(best_item)
            else:
                # Fallback to first item
                self._play_item(items[0])
    
    def _show_stream_selection(self, items, title="Vyberte stream"):
        """Show stream selection dialog with quality info."""
        try:
            from .stream_selector import StreamSelectorDialog
            
            # Convert catalogue items to stream format
            streams = []
            for item in items:
                stream_info = {
                    'name': item.original_name,  # MediaItem uses original_name, not name
                    'size': getattr(item, 'size', 0),
                    'ident': item.ident,
                    'item': item  # Keep reference to original item
                }
                streams.append(stream_info)
            
            # Show selection dialog
            selector = StreamSelectorDialog(streams)
            selected_stream = selector.show_selection_dialog()
            
            if selected_stream:
                # Play selected stream
                item = selected_stream['item']
                self._play_item(item)
            else:
                # User cancelled - set invalid resolved URL like in stream-cinema-2
                xbmcplugin.setResolvedUrl(self.handle, False, xbmcgui.ListItem())
                
        except ImportError:
            # Fallback to regular directory if stream_selector not available
            self._logger("StreamSelectorDialog not available, showing as directory", xbmc.LOGWARNING)
            self._show_items_as_directory(items)
        except Exception as e:
            self._logger(f"Error in stream selection: {e}", xbmc.LOGERROR)
            # On error, also set invalid resolved URL
            xbmcplugin.setResolvedUrl(self.handle, False, xbmcgui.ListItem())
    
    def _select_best_stream(self, items):
        """Select the best quality stream from available items."""
        if not items:
            return None
        
        # Score items by quality and other factors
        scored_items = []
        for item in items:
            score = 0
            
            # Quality scoring
            quality = getattr(item, 'quality', '').lower() if hasattr(item, 'quality') and item.quality else ''
            if '2160' in quality or '4k' in quality or 'uhd' in quality:
                score += 100
            elif '1080' in quality or 'fhd' in quality:
                score += 80
            elif '720' in quality or 'hd' in quality:
                score += 60
            else:
                score += 40  # SD or unknown
            
            # Size scoring (prefer reasonable sizes - not too small, not too large)
            size = getattr(item, 'size', 0) if hasattr(item, 'size') else 0
            if size > 0:
                size_gb = size / (1024 * 1024 * 1024)
                if 2 <= size_gb <= 15:  # Good range for movies/episodes
                    score += 20
                elif 1 <= size_gb < 2:  # Small but acceptable
                    score += 10
                elif size_gb > 15:  # Large files
                    score += 5
            
            # Audio languages scoring (prefer CZ)
            audio_langs = getattr(item, 'audio_languages', []) if hasattr(item, 'audio_languages') else []
            if audio_langs and 'cz' in [lang.lower() for lang in audio_langs if lang]:
                score += 30
            
            scored_items.append((score, item))
        
        # Sort by score (highest first) and return best item
        scored_items.sort(key=lambda x: x[0], reverse=True)
        return scored_items[0][1] if scored_items else items[0]

    def _play_item(self, item):
        """Play media item using the standard plugin method (bez rekurze)."""
        ident = getattr(item, "ident", None)
        self._logger(f"[_play_item] ident={ident}", xbmc.LOGDEBUG)
        
        if not ident:
            self.notify("Missing file identifier", level=xbmc.LOGWARNING)
            xbmcplugin.setResolvedUrl(self.handle, False, xbmcgui.ListItem())
            return
            
        if not self._ensure_session():
            xbmcplugin.setResolvedUrl(self.handle, False, xbmcgui.ListItem())
            return
            
        try:
            link = self.api.file_link(
                ident,
                download_type=self.settings.download_type,
                force_https=self.settings.force_https,
            )
            self._logger(f"Got stream URL: {link}", xbmc.LOGINFO)
            list_item = xbmcgui.ListItem(path=link)
            list_item.setProperty("IsPlayable", "true")
            xbmcplugin.setResolvedUrl(self.handle, True, list_item)
        except Exception as exc:
            self._logger(f"Error getting stream link: {exc}", xbmc.LOGERROR)
            self.notify(str(exc), level=xbmc.LOGWARNING)
            xbmcplugin.setResolvedUrl(self.handle, False, xbmcgui.ListItem())
    
    def _show_stream_selection_for_browse(self, items, query):
        """Show stream selection for browse results (fallback to directory if selection fails)."""
        try:
            from .stream_selector import StreamSelectorDialog
            
            # Convert items to stream format
            streams = []
            for item in items:
                stream_info = {
                    'name': item.original_name,  # MediaItem uses original_name
                    'size': getattr(item, 'size', 0),
                    'ident': item.ident,
                    'item': item
                }
                streams.append(stream_info)
            
            # Show selection dialog
            selector = StreamSelectorDialog(streams)
            selected_stream = selector.show_selection_dialog()
            
            if selected_stream:
                # Play selected stream
                item = selected_stream['item']
                self._play_item(item)
            else:
                # User cancelled - show as regular directory
                self._show_items_as_directory(items)
                
        except ImportError:
            # Fallback to regular directory if stream_selector not available
            self._show_items_as_directory(items)
        except Exception as e:
            self._logger(f"Error in stream selection: {e}", xbmc.LOGERROR)
            self._show_items_as_directory(items)
    
    def _show_items_as_directory(self, items):
        """Show items as regular Kodi directory."""
        media_type = self.params.get("media_type", "movie")
        
        for item in items:
            ident = getattr(item, "ident", None)
            if not ident:
                continue  # skip items without ident
            list_item = self._create_list_item(item, media_type)
            
            # Add context information for history tracking
            play_params = {
                "action": "play", 
                "ident": ident, 
                "media_type": media_type
            }
            
            # Add title and other metadata for history
            if hasattr(item, 'metadata') and item.metadata:
                title = item.metadata.get("title")
                year = item.metadata.get("year")
            elif hasattr(item, 'cleaned_title'):
                title = item.cleaned_title
                year = getattr(item, 'guessed_year', None)
            else:
                title = str(item)
                year = None
                
            if title:
                play_params["context_title"] = title
            if year:
                play_params["context_year"] = year
            if hasattr(item, 'season') and item.season:
                play_params["season"] = item.season
            if hasattr(item, 'episode') and item.episode:
                play_params["episode"] = item.episode
            
            url = self.build_url(play_params)
            xbmcplugin.addDirectoryItem(self.handle, url, list_item, isFolder=False)
            
        xbmcplugin.endOfDirectory(self.handle)

    # Metadata-based browsing methods
    def show_metadata_categories(self) -> None:
        """Show main metadata categories menu."""
        xbmcplugin.setPluginCategory(self.handle, "Kategorie")
        xbmcplugin.setContent(self.handle, "videos")
        
        entries = [
            ("Filmy", {"action": "metadata_movies"}),
            ("Seriály", {"action": "metadata_tvshows"}),
        ]
        
        for label, query in entries:
            url = self.build_url(query)
            item = xbmcgui.ListItem(label=label)
            xbmcplugin.addDirectoryItem(self.handle, url, item, isFolder=True)
        
        xbmcplugin.endOfDirectory(self.handle)

    def show_metadata_movies(self) -> None:
        """Show movie categories menu."""
        xbmcplugin.setPluginCategory(self.handle, "Filmy - Kategorie")
        xbmcplugin.setContent(self.handle, "videos")
        
        entries = [
            ("Populární filmy", {"action": "metadata_movie_category", "category": "popular"}),
            ("Nejlépe hodnocené", {"action": "metadata_movie_category", "category": "top_rated"}),
            ("V kinech", {"action": "metadata_movie_category", "category": "now_playing"}),
            ("Připravované", {"action": "metadata_movie_category", "category": "upcoming"}),
            ("Podle žánru", {"action": "metadata_genre_movies"}),
        ]
        
        for label, query in entries:
            url = self.build_url(query)
            item = xbmcgui.ListItem(label=label)
            xbmcplugin.addDirectoryItem(self.handle, url, item, isFolder=True)
        
        xbmcplugin.endOfDirectory(self.handle)

    def show_metadata_tvshows(self) -> None:
        """Show TV show categories menu."""
        xbmcplugin.setPluginCategory(self.handle, "Seriály - Kategorie")
        xbmcplugin.setContent(self.handle, "videos")
        
        entries = [
            ("Populární seriály", {"action": "metadata_tv_category", "category": "popular"}),
            ("Nejlépe hodnocené", {"action": "metadata_tv_category", "category": "top_rated"}),
            ("Vysílané dnes", {"action": "metadata_tv_category", "category": "airing_today"}),
            ("Aktuálně vysílané", {"action": "metadata_tv_category", "category": "on_the_air"}),
            ("Podle žánru", {"action": "metadata_genre_tvshows"}),
        ]
        
        for label, query in entries:
            url = self.build_url(query)
            item = xbmcgui.ListItem(label=label)
            xbmcplugin.addDirectoryItem(self.handle, url, item, isFolder=True)
        
        xbmcplugin.endOfDirectory(self.handle)

    def show_metadata_movie_category(self) -> None:
        """Show movies from a specific category."""
        category = self.params.get("category", "popular")
        page = int(self.params.get("page", "1"))
        
        if not self.metadata or not self.metadata.has_providers():
            self.notify("Metadata poskytovatelé nejsou k dispozici", level=xbmc.LOGWARNING)
            return
        
        # Map category to method
        method_map = {
            "popular": "get_popular_movies",
            "top_rated": "get_top_rated_movies", 
            "now_playing": "get_now_playing_movies",
            "upcoming": "get_upcoming_movies"
        }
        
        method_name = method_map.get(category)
        if not method_name:
            return
            
        method = getattr(self.metadata, method_name, None)
        if not method:
            return
            
        try:
            movies = method(page)
            if not movies:
                self.notify("Žádné filmy nenalezeny", level=xbmc.LOGINFO)
                return
                
            self._show_metadata_content_list(movies, "movie", category, page)
            
        except Exception as e:
            self._logger(f"Error fetching movies category {category}: {e}", xbmc.LOGERROR)
            self.notify("Chyba při načítání filmů", level=xbmc.LOGERROR)

    def show_metadata_genre_movies(self) -> None:
        """Show movie genres list."""
        if not self.metadata or not self.metadata.has_providers():
            self.notify("Metadata poskytovatelé nejsou k dispozici", level=xbmc.LOGWARNING)
            return
            
        try:
            genres = self.metadata.get_genre_list("movie")
            if not genres:
                self.notify("Žánry nejsou k dispozici", level=xbmc.LOGINFO)
                return
                
            xbmcplugin.setPluginCategory(self.handle, "Filmové žánry")
            xbmcplugin.setContent(self.handle, "videos")
            
            for genre_id, genre_name in sorted(genres.items(), key=lambda x: x[1]):
                url = self.build_url({
                    "action": "metadata_content",
                    "content_type": "movies_by_genre",
                    "genre_id": genre_id,
                    "genre_name": genre_name,
                    "page": 1
                })
                item = xbmcgui.ListItem(label=f"{genre_name}")
                xbmcplugin.addDirectoryItem(self.handle, url, item, isFolder=True)
                
            xbmcplugin.endOfDirectory(self.handle)
            
        except Exception as e:
            self._logger(f"Error fetching movie genres: {e}", xbmc.LOGERROR)
            self.notify("Chyba při načítání žánrů", level=xbmc.LOGERROR)

    def show_metadata_genre_tvshows(self) -> None:
        """Show TV show genres list.""" 
        if not self.metadata or not self.metadata.has_providers():
            self.notify("Metadata poskytovatelé nejsou k dispozici", level=xbmc.LOGWARNING)
            return
            
        try:
            genres = self.metadata.get_genre_list("tvshow")
            if not genres:
                self.notify("Žánry nejsou k dispozici", level=xbmc.LOGINFO)
                return
                
            xbmcplugin.setPluginCategory(self.handle, "Seriálové žánry")
            xbmcplugin.setContent(self.handle, "videos")
            
            for genre_id, genre_name in sorted(genres.items(), key=lambda x: x[1]):
                url = self.build_url({
                    "action": "metadata_content", 
                    "content_type": "tvshows_by_genre",
                    "genre_id": genre_id,
                    "genre_name": genre_name,
                    "page": 1
                })
                item = xbmcgui.ListItem(label=f"{genre_name}")
                xbmcplugin.addDirectoryItem(self.handle, url, item, isFolder=True)
                
            xbmcplugin.endOfDirectory(self.handle)
            
        except Exception as e:
            self._logger(f"Error fetching TV genres: {e}", xbmc.LOGERROR)
            self.notify("Chyba při načítání žánrů", level=xbmc.LOGERROR)

    def show_metadata_content(self) -> None:
        """Show content for specific metadata query."""
        content_type = self.params.get("content_type")
        page = int(self.params.get("page", "1"))
        
        if not self.metadata or not self.metadata.has_providers():
            self.notify("Metadata poskytovatelé nejsou k dispozici", level=xbmc.LOGWARNING)
            return
        
        try:
            content = None
            media_type = None
            
            if content_type == "movies_by_genre":
                genre_id = int(self.params.get("genre_id", "0"))
                content = self.metadata.get_movies_by_genre(genre_id, page)
                media_type = "movie"
            elif content_type == "tvshows_by_genre":
                genre_id = int(self.params.get("genre_id", "0")) 
                content = self.metadata.get_tv_shows_by_genre(genre_id, page)
                media_type = "tvshow"
                
            if not content:
                self.notify("Žádný obsah nenalezen", level=xbmc.LOGINFO)
                return
                
            self._show_metadata_content_list(content, media_type, content_type, page)
            
        except Exception as e:
            self._logger(f"Error fetching metadata content: {e}", xbmc.LOGERROR)
            self.notify("Chyba při načítání obsahu", level=xbmc.LOGERROR)

    def _show_metadata_content_list(self, content_list, media_type, category, page):
        """Show list of content from metadata with Webshare search integration."""
        category_names = {
            "popular": "Populární",
            "top_rated": "Nejlépe hodnocené", 
            "now_playing": "V kinech",
            "upcoming": "Připravované",
            "airing_today": "Vysílané dnes",
            "on_the_air": "Aktuálně vysílané",
            "movies_by_genre": f"Filmy - {self.params.get('genre_name', 'Žánr')}",
            "tvshows_by_genre": f"Seriály - {self.params.get('genre_name', 'Žánr')}"
        }
        
        category_name = category_names.get(category, category)
        xbmcplugin.setPluginCategory(self.handle, f"{category_name} (strana {page})")
        xbmcplugin.setContent(self.handle, "videos")
        
        for item in content_list:
            title = item.get("title") or item.get("name", "")
            year = item.get("year")
            overview = item.get("overview", "")
            poster = item.get("poster_path", "")
            fanart = item.get("backdrop_path", "")
            rating = item.get("vote_average", 0)
            
            # Create list item
            label = f"{title}"
            if year:
                label += f" ({year})"
                
            list_item = xbmcgui.ListItem(label=label)
            
            # Set artwork
            if poster:
                list_item.setArt({"poster": poster, "thumb": poster})
            if fanart:
                list_item.setArt({"fanart": fanart})
                
            # Set info
            info = {
                "title": title,
                "plot": overview,
                "year": year,
                "rating": rating,
                "mediatype": media_type
            }
            list_item.setInfo("video", info)
            
            # Create URL for optimized Webshare search
            if media_type == "movie":
                search_query = title
                if year:
                    search_query += f" {year}"
                url = self.build_url({
                    "action": "quick_movie_search",
                    "query": search_query,
                    "title": title,
                    "year": year or ""
                })
                # Movies are playable - dialog will be shown
                list_item.setProperty("IsPlayable", "true")
                xbmcplugin.addDirectoryItem(self.handle, url, list_item, isFolder=False)
            else:  # tvshow
                url = self.build_url({
                    "action": "show_metadata_seasons",
                    "series_name": title,
                    "series_id": item.get("id"),
                    "original_query": title
                })
                # TV shows are folders
                xbmcplugin.addDirectoryItem(self.handle, url, list_item, isFolder=True)
        
        # Add "Next page" if we have full results (usually 20 items per page)
        if len(content_list) >= 20:
            next_params = dict(self.params)
            next_params["page"] = str(page + 1)
            next_url = self.build_url(next_params)
            next_item = xbmcgui.ListItem(label=f"Další strana ({page + 1})")
            xbmcplugin.addDirectoryItem(self.handle, next_url, next_item, isFolder=True)
        
        xbmcplugin.endOfDirectory(self.handle)

    def quick_movie_search(self) -> None:
        """Smart movie search with detailed file information dialog."""
        query = self.params.get("query", "")
        title = self.params.get("title", "")
        year = self.params.get("year", "")
        
        if not query:
            return
            
        self._logger(f"Smart movie search for: '{title}' ({year}) - query: '{query}'", xbmc.LOGINFO)
        
        # Try multiple search strategies for better accuracy
        search_queries = [
            query,  # Original "Title Year" query
            title,  # Just title
            f"{title} {year}" if year else title,  # Ensure year is included
        ]
        
        # Remove duplicates while preserving order
        unique_queries = []
        for q in search_queries:
            if q and q not in unique_queries:
                unique_queries.append(q)
        
        all_items = []
        
        try:
            # Try each search query to find the best matches
            for i, search_query in enumerate(unique_queries):
                self._logger(f"Trying search query {i+1}/{len(unique_queries)}: '{search_query}'", xbmc.LOGINFO)
                
                # Adjust search parameters based on query type
                page_size = 30 if i == 0 else 20  # More results for first (most specific) query
                
                items, _, _, _ = self.catalogue.fetch(
                    media_type="movie",
                    query=search_query,
                    start_offset=0,
                    page_size=page_size
                )
                
                self._logger(f"Search '{search_query}' returned {len(items) if items else 0} items", xbmc.LOGINFO)
                
                if items:
                    # Filter items to match the movie better
                    filtered_items = self._filter_movie_results(items, title, year)
                    self._logger(f"After filtering: {len(filtered_items)} relevant items", xbmc.LOGINFO)
                    
                    all_items.extend(filtered_items)
                    
                    # If we found enough good matches, we can stop searching
                    if len(filtered_items) >= 5:  # Found sufficient results
                        self._logger(f"Found sufficient results ({len(filtered_items)}), stopping search", xbmc.LOGINFO)
                        break
                else:
                    self._logger(f"No items found for query: '{search_query}'", xbmc.LOGINFO)
            
            # Remove duplicates by ident while preserving order
            seen_idents = set()
            unique_items = []
            for item in all_items:
                if hasattr(item, 'ident') and item.ident and item.ident not in seen_idents:
                    unique_items.append(item)
                    seen_idents.add(item.ident)
            
            self._logger(f"Final result: {len(unique_items)} unique items found", xbmc.LOGINFO)
            
            if not unique_items:
                # Show user-friendly message when no results found
                self._logger(f"No results found for movie: '{title}' ({year})", xbmc.LOGINFO)
                self._show_movie_not_found_dialog(title, year)
                xbmcplugin.setResolvedUrl(self.handle, False, xbmcgui.ListItem())
                return
                
            # Show detailed stream selection dialog
            self._logger(f"Showing stream selection dialog for {len(unique_items)} items", xbmc.LOGINFO)
            self._show_movie_streams_dialog(unique_items, title, year)
            
        except Exception as e:
            self._logger(f"Error in smart movie search: {e}", xbmc.LOGERROR)
            self.notify("Chyba při vyhledávání filmu", level=xbmc.LOGERROR)
            xbmcplugin.setResolvedUrl(self.handle, False, xbmcgui.ListItem())
    
    def _filter_movie_results(self, items, title, year):
        """Filter search results to find items that better match the target movie."""
        if not items:
            return []
        
        title_lower = title.lower() if title else ""
        year_str = str(year) if year else ""
        
        # Score-based filtering for better results
        scored_items = []
        
        for item in items:
            score = 0
            
            # Get item title for comparison - check multiple sources
            item_title = ""
            item_filename = ""
            
            if hasattr(item, 'metadata') and item.metadata and item.metadata.get("title"):
                item_title = item.metadata.get("title").lower()
            elif hasattr(item, 'cleaned_title') and item.cleaned_title:
                item_title = item.cleaned_title.lower()
                
            if hasattr(item, 'original_name') and item.original_name:
                item_filename = item.original_name.lower()
            
            # Title matching with scoring
            if title_lower:
                # Exact title match gets highest score
                if title_lower == item_title:
                    score += 100
                elif title_lower in item_title or item_title in title_lower:
                    score += 50
                elif title_lower in item_filename:
                    score += 30
                else:
                    # Check if most words from title are present
                    title_words = title_lower.split()
                    matches = sum(1 for word in title_words if word in item_title or word in item_filename)
                    if matches > len(title_words) / 2:  # More than half words match
                        score += 25
            
            # Year matching
            if year_str:
                # Check metadata year
                if hasattr(item, 'metadata') and item.metadata:
                    item_year = item.metadata.get("year")
                    if item_year and str(item_year) == year_str:
                        score += 50
                
                # Check year in filename
                if year_str in item_filename:
                    score += 25
                    
                # Check guessed year from item
                if hasattr(item, 'guessed_year') and item.guessed_year and str(item.guessed_year) == year_str:
                    score += 25
            
            # Quality bonus (prefer higher quality)
            if hasattr(item, 'quality'):
                quality = getattr(item, 'quality', '')
                if quality:  # Check if quality is not None or empty
                    quality = quality.upper()
                    if quality in ['UHD', '4K', '2160P']:
                        score += 15
                    elif quality in ['HD', '1080P']:
                        score += 10
                    elif quality in ['720P']:
                        score += 5
            
            # Size bonus (reasonable file sizes get bonus)
            if hasattr(item, 'size') and item.size:
                size_gb = item.size / (1024 * 1024 * 1024)
                if 0.5 <= size_gb <= 20:  # Reasonable movie size range
                    score += 5
            
            if score > 0:  # Only include items with some relevance
                scored_items.append((item, score))
        
        # Sort by score (highest first) and return top matches
        scored_items.sort(key=lambda x: x[1], reverse=True)
        
        # Return top scored items, but at least some items if we have any
        if scored_items:
            # Take items with score above threshold, or top 10 if none meet threshold
            good_items = [item for item, score in scored_items if score >= 25]
            if not good_items and scored_items:
                good_items = [item for item, score in scored_items[:10]]
            return good_items
        
        # Fallback: return first 10 original items
        return items[:10]
    
    def _show_movie_not_found_dialog(self, title, year):
        """Show dialog when movie is not found on Webshare."""
        year_text = f" ({year})" if year else ""
        message = f"[COLOR yellow]Film '{title}{year_text}' se na Webshare.cz nepodařilo najít.[/COLOR]\n\n"
        message += "[COLOR white]Možné důvody:[/COLOR]\n"
        message += "[COLOR lightblue]•[/COLOR] Film může mít jiný název na Webshare\n"
        message += "[COLOR lightblue]•[/COLOR] Film ještě není uložen na Webshare.cz\n"
        message += "[COLOR lightblue]•[/COLOR] Zkuste vyhledat film ručně pomocí vyhledávání\n\n"
        message += "[COLOR lime]Tip:[/COLOR] Použijte obecné vyhledávání v hlavním menu"
        
        self.dialog.ok("[COLOR red]Film nenalezen[/COLOR]", message)
    
    def _show_streams_as_directory(self, items, title, year):
        """Show streams as Kodi directory for user selection."""
        if not items:
            xbmcplugin.endOfDirectory(self.handle)
            return
            
        year_text = f" ({year})" if year else ""
        xbmcplugin.setPluginCategory(self.handle, f"{title}{year_text} - Dostupné streamy")
        xbmcplugin.setContent(self.handle, "movies")
        
        for item in items:
            # Create descriptive label with quality and file info
            label = self._create_stream_label(item)
            
            # Create list item for the stream
            list_item = self._create_list_item(item, "movie", is_playable=True)
            list_item.setLabel(label)
            
            # Add extra video info
            info = {
                "title": title,
                "year": year,
                "mediatype": "movie"
            }
            list_item.setInfo("video", info)
            
            # Create URL for direct play with context information
            play_params = {
                "action": "play", 
                "ident": item.ident, 
                "media_type": "movie",
                "context_title": title
            }
            
            if year:
                play_params["context_year"] = year
            
            url = self.build_url(play_params)
            xbmcplugin.addDirectoryItem(self.handle, url, list_item, isFolder=False)
        
        xbmcplugin.endOfDirectory(self.handle)
    
    def _create_stream_label(self, item):
        """Create descriptive label for stream item."""
        # Get basic filename
        filename = getattr(item, 'original_name', '') or getattr(item, 'cleaned_title', '') or 'Neznámý soubor'
        
        # Get file size in readable format
        size_mb = getattr(item, 'size', 0) / (1024 * 1024) if hasattr(item, 'size') and getattr(item, 'size', 0) > 0 else 0
        if size_mb >= 1024:
            size_text = f"{size_mb/1024:.1f} GB"
        elif size_mb > 0:
            size_text = f"{size_mb:.0f} MB"
        else:
            size_text = "? MB"
        
        # Get quality
        quality = getattr(item, 'quality', 'SD') or 'SD'
        quality = quality.upper()
        
        # Get audio info
        audio_info = []
        if hasattr(item, 'audio_languages') and item.audio_languages:
            for lang in item.audio_languages:
                if lang and isinstance(lang, str):
                    audio_info.append(lang.upper())
        
        # Detect dubbing from filename
        dubbing = self._detect_dubbing(filename)
        if dubbing:
            audio_info.append(dubbing)
        
        # Build label parts
        parts = [f"[{quality}]", f"[{size_text}]"]
        if audio_info:
            parts.append(f"[{' | '.join(audio_info)}]")
        
        # Combine into final label
        label = f"{' '.join(parts)} {filename}"
        return label
    
    def _show_movie_streams_dialog(self, items, title, year):
        """Show detailed dialog with movie stream information."""
        if not items:
            return
        
        # Prepare stream information with colors
        stream_options = []
        
        for item in items:
            # Get filename for display
            filename = getattr(item, 'original_name', '') or getattr(item, 'cleaned_title', '') or 'Neznámý soubor'
            
            # Get file size in readable format
            size_mb = getattr(item, 'size', 0) / (1024 * 1024) if hasattr(item, 'size') and getattr(item, 'size', 0) > 0 else 0
            if size_mb >= 1024:
                size_text = f"{size_mb/1024:.1f} GB"
            elif size_mb > 0:
                size_text = f"{size_mb:.0f} MB"
            else:
                size_text = "Neznámá velikost"
            
            # Get quality with color
            quality = getattr(item, 'quality', 'SD') or 'SD'  # Handle None values
            quality = quality.upper()
            if quality in ['UHD', '4K', '2160P']:
                quality_colored = f"[COLOR gold]{quality}[/COLOR]"
            elif quality in ['HD', '1080P', '720P']:
                quality_colored = f"[COLOR lime]{quality}[/COLOR]"
            else:
                quality_colored = f"[COLOR white]{quality}[/COLOR]"
            
            # Get audio languages and dubbing
            audio_info = []
            if hasattr(item, 'audio_languages') and item.audio_languages:
                for lang in item.audio_languages:
                    if lang and isinstance(lang, str):  # Check lang is not None and is string
                        lang_upper = lang.upper()
                        if lang_upper == 'CZ':
                            audio_info.append(f"[COLOR cyan]CZ[/COLOR]")
                        elif lang_upper == 'EN':
                            audio_info.append(f"[COLOR yellow]EN[/COLOR]")
                        else:
                            audio_info.append(f"[COLOR white]{lang_upper}[/COLOR]")
            
            # Detect dubbing from filename
            dubbing = self._detect_dubbing(filename)
            if dubbing:
                if 'CZ' in dubbing:
                    audio_info.append(f"[COLOR cyan]{dubbing}[/COLOR]")
                elif 'EN' in dubbing:
                    audio_info.append(f"[COLOR yellow]{dubbing}[/COLOR]")
                else:
                    audio_info.append(f"[COLOR white]{dubbing}[/COLOR]")
            
            # Check for subtitles in filename - enhanced detection
            subs_info = []
            filename_lower = filename.lower()
            
            # Czech subtitle patterns
            cz_sub_patterns = [
                'cz sub', 'czech sub', 'titulky cz', 'cz tit', 'cz.sub', 'czech.sub',
                'subs.cz', 'sub.cz', 'cze.sub', 'ces.sub', 'czech subs', 'ceske titulky',
                'české titulky', 'cz-sub', 'cz_sub'
            ]
            if any(pattern in filename_lower for pattern in cz_sub_patterns):
                subs_info.append(f"[COLOR lightblue]CZ titulky[/COLOR]")
            
            # English subtitle patterns  
            en_sub_patterns = [
                'en sub', 'english sub', 'titulky en', 'en tit', 'en.sub', 'english.sub',
                'subs.en', 'sub.en', 'eng.sub', 'english subs', 'anglicke titulky',
                'anglické titulky', 'en-sub', 'en_sub'
            ]
            if any(pattern in filename_lower for pattern in en_sub_patterns):
                subs_info.append(f"[COLOR orange]EN titulky[/COLOR]")
            
            # Estimate required speed (rough calculation)
            estimated_bitrate = int(size_mb * 8 / (100 * 60)) if size_mb > 0 else 0  # Assume 100min movie
            if estimated_bitrate > 25:
                speed_text = f"[COLOR red]~{estimated_bitrate} Mbps (Vysoká)[/COLOR]"
            elif estimated_bitrate > 10:
                speed_text = f"[COLOR orange]~{estimated_bitrate} Mbps (Střední)[/COLOR]"
            elif estimated_bitrate > 0:
                speed_text = f"[COLOR lime]~{estimated_bitrate} Mbps (Nízká)[/COLOR]"
            else:
                speed_text = "[COLOR gray]Neznámá rychlost[/COLOR]"
            
            # Create formatted display text
            display_parts = []
            display_parts.append(f"[COLOR white]{filename}[/COLOR]")
            
            info_parts = []
            info_parts.append(quality_colored)
            info_parts.append(f"[COLOR lightgray]{size_text}[/COLOR]")
            
            if audio_info:
                info_parts.append(" | ".join(audio_info))
            
            if subs_info:
                info_parts.append(" | ".join(subs_info))
                
            info_parts.append(speed_text)
            
            display_text = display_parts[0] + "\n" + " | ".join(info_parts)
            
            stream_options.append({
                'label': display_text,
                'item': item
            })
        
        # If only one option, show it directly
        if len(stream_options) == 1:
            self._play_item(stream_options[0]['item'])
            return
        
        # Show selection dialog with colored labels
        labels = [option['label'] for option in stream_options]
        labels.append("[COLOR red][Zrušit][/COLOR]")
        
        year_text = f" ({year})" if year else ""
        dialog_title = f"Streams pro: [B]{title}{year_text}[/B]"
        selected = self.dialog.select(dialog_title, labels)
        
        if selected >= 0 and selected < len(stream_options):
            self._logger(f"User selected stream {selected}, playing item", xbmc.LOGINFO)
            self._play_item(stream_options[selected]['item'])
        else:
            # User cancelled selection - set invalid resolved URL
            self._logger(f"User cancelled stream selection (selected={selected})", xbmc.LOGINFO)
            xbmcplugin.setResolvedUrl(self.handle, False, xbmcgui.ListItem())

    def show_seasonal_content(self) -> None:
        """Show content based on seasons (spring, summer, autumn, winter)."""
        xbmcplugin.setPluginCategory(self.handle, "Výběr dle ročního období")
        xbmcplugin.setContent(self.handle, "videos")
        
        entries = [
            ("JARO", {"action": "browse", "seasonal": "spring"}),
            ("LÉTO", {"action": "browse", "seasonal": "summer"}),
            ("PODZIM", {"action": "browse", "seasonal": "autumn"}),
            ("ZIMA", {"action": "browse", "seasonal": "winter"}),
        ]
        
        for label, query in entries:
            url = self.build_url(query)
            item = xbmcgui.ListItem(label=label)
            xbmcplugin.addDirectoryItem(self.handle, url, item, isFolder=True)
        
        xbmcplugin.endOfDirectory(self.handle)

    def show_info(self) -> None:
        """Show plugin information and features."""
        info_text = """[B]TVStreamCZ Plugin - Informace[/B]

[COLOR gold]AKTUÁLNÍ FUNKCE:[/COLOR]
• Procházení filmů a seriálů z Webshare.cz
• Pokročilé vyhledávání s filtry (kvalita, dabing, titulky)
• Metadata z TMDb a ČSFD databází
• Automatická detekce kvality (HD/UHD/SD) a dabingu (CZ/EN)
• Strukturované procházení seriálů po sériích a epizodách
• Streamování přes oficiální Webshare API
• Výběr obsahu podle ročního období

[COLOR lightblue]PLÁNOVANÉ FUNKCE:[/COLOR]
• Statistiky sledování a oblíbené obsahy
• Notifikace o nových epizodách oblíbených seriálů
• Synchronizace sledovaných položek mezi zařízeními
• Rozšířené filtry podle herců a režisérů
• Kalendář premiér filmů a seriálů
• Offline režim s možností stahování
• AI doporučení na základě sledovaného obsahu
• Integrace s hudebními službami pro soundtracky
• Žebříčky a hodnocení od komunity
• Vícejazyčné rozhraní
• Pokročilé analytiky sledování

[COLOR orange]POŽADAVKY:[/COLOR]
• Aktivní Webshare.cz účet
• Kodi 20+ (Python 3)
• Internetové připojení

[COLOR lime]PODPORA:[/COLOR]
GitHub: github.com/daker52/TVstreamCZ
"""
        
        dialog = xbmcgui.Dialog()
        dialog.textviewer("TVStreamCZ - Informace", info_text)

    def show_settings(self) -> None:
        """Open plugin settings."""
        self.addon.openSettings()

    def check_updates(self) -> None:
        """Check for plugin updates."""
        try:
            import requests
            
            # GitHub API pro zjištění nejnovější verze
            api_url = "https://api.github.com/repos/daker52/TVstreamCZ/releases/latest"
            
            dialog = xbmcgui.Dialog()
            dialog.notification("TVStreamCZ", "Kontrola aktualizací...", xbmcgui.NOTIFICATION_INFO, 2000)
            
            try:
                response = requests.get(api_url, timeout=10)
                if response.status_code == 200:
                    release_data = response.json()
                    latest_version = release_data.get("tag_name", "neznámá")
                    current_version = self.addon.getAddonInfo("version")
                    
                    if latest_version != current_version:
                        message = f"Dostupná nová verze: {latest_version}\nAktuální verze: {current_version}\n\nChcete přejít na stránku stažení?"
                        if dialog.yesno("Aktualizace dostupná", message):
                            # Otevře GitHub releases stránku
                            import webbrowser
                            webbrowser.open("https://github.com/daker52/TVstreamCZ/releases/latest")
                    else:
                        dialog.ok("Aktuální verze", f"Používáte nejnovější verzi: {current_version}")
                else:
                    dialog.ok("Chyba", "Nelze zkontrolovat aktualizace. Zkuste to později.")
            except requests.exceptions.RequestException:
                dialog.ok("Chyba sítě", "Nelze se připojit k serveru pro kontrolu aktualizací.")
                
        except ImportError:
            dialog = xbmcgui.Dialog()
            dialog.ok("Chyba", "Modul requests není dostupný pro kontrolu aktualizací.")

    # ------------------------------------------------------------------
    # Historie přehrávání
    # ------------------------------------------------------------------
    
    def show_history(self) -> None:
        """Show playback history menu."""
        xbmcplugin.setPluginCategory(self.handle, "Historie přehrávání")
        xbmcplugin.setContent(self.handle, "videos")
        
        entries = [
            ("📺 Nedávno přehrané", {"action": "show_recent"}),
            ("⭐ Nejčastěji přehrávané", {"action": "show_frequent"}),
            ("💖 Oblíbené", {"action": "show_favorites"}),
            ("⏸️ Pozastavené filmy", {"action": "show_resume"}),
            ("📊 Statistiky přehrávání", {"action": "show_stats"}),
            ("🗑️ Vymazat historii", {"action": "clear_history"}),
        ]
        
        for label, query in entries:
            url = self.build_url(query)
            item = xbmcgui.ListItem(label=label)
            xbmcplugin.addDirectoryItem(self.handle, url, item, isFolder=True)
        
        xbmcplugin.endOfDirectory(self.handle)

    def show_recent_history(self) -> None:
        """Show recently played items."""
        xbmcplugin.setPluginCategory(self.handle, "Nedávno přehrané")
        xbmcplugin.setContent(self.handle, "movies")
        
        # Get recent items from Kodi's database
        recent_items = self._get_recent_items()
        
        self._logger(f"Recent items from storage: {len(recent_items) if recent_items else 0}", xbmc.LOGINFO)
        if recent_items:
            self._logger(f"Sample recent item: {recent_items[0] if recent_items else 'None'}", xbmc.LOGINFO)
        
        if not recent_items:
            # Show empty message
            item = xbmcgui.ListItem(label="Žádné nedávno přehrané položky")
            xbmcplugin.addDirectoryItem(self.handle, "", item, isFolder=False)
        else:
            for item_data in recent_items:
                list_item = self._create_history_list_item(item_data)
                url = self.build_url({
                    "action": "play", 
                    "ident": item_data.get("ident"),
                    "media_type": item_data.get("media_type", "movie")
                })
                xbmcplugin.addDirectoryItem(self.handle, url, list_item, isFolder=False)
        
        xbmcplugin.endOfDirectory(self.handle)

    def show_frequent_history(self) -> None:
        """Show most frequently played items."""
        xbmcplugin.setPluginCategory(self.handle, "Nejčastěji přehrávané")
        xbmcplugin.setContent(self.handle, "movies")
        
        # Get frequent items from stored data
        frequent_items = self._get_frequent_items()
        
        if not frequent_items:
            item = xbmcgui.ListItem(label="Žádné často přehrávané položky")
            xbmcplugin.addDirectoryItem(self.handle, "", item, isFolder=False)
        else:
            for item_data in frequent_items:
                # Add play count to the label
                label = f"{item_data.get('title', 'Neznámý')} ({item_data.get('play_count', 0)}x)"
                list_item = self._create_history_list_item(item_data)
                list_item.setLabel(label)
                
                url = self.build_url({
                    "action": "play",
                    "ident": item_data.get("ident"), 
                    "media_type": item_data.get("media_type", "movie")
                })
                xbmcplugin.addDirectoryItem(self.handle, url, list_item, isFolder=False)
        
        xbmcplugin.endOfDirectory(self.handle)

    def show_favorites(self) -> None:
        """Show favorite items."""
        xbmcplugin.setPluginCategory(self.handle, "Oblíbené")
        xbmcplugin.setContent(self.handle, "movies")
        
        favorites = self._get_favorites()
        
        if not favorites:
            item = xbmcgui.ListItem(label="Žádné oblíbené položky")
            xbmcplugin.addDirectoryItem(self.handle, "", item, isFolder=False)
        else:
            for item_data in favorites:
                list_item = self._create_history_list_item(item_data)
                # Add heart emoji to favorites
                current_label = list_item.getLabel()
                list_item.setLabel(f"💖 {current_label}")
                
                url = self.build_url({
                    "action": "play",
                    "ident": item_data.get("ident"),
                    "media_type": item_data.get("media_type", "movie")
                })
                xbmcplugin.addDirectoryItem(self.handle, url, list_item, isFolder=False)
        
        xbmcplugin.endOfDirectory(self.handle)

    def show_resume_points(self) -> None:
        """Show items with resume points (partially watched)."""
        xbmcplugin.setPluginCategory(self.handle, "Pozastavené filmy") 
        xbmcplugin.setContent(self.handle, "movies")
        
        resume_items = self._get_resume_items()
        
        if not resume_items:
            item = xbmcgui.ListItem(label="Žádné pozastavené filmy")
            xbmcplugin.addDirectoryItem(self.handle, "", item, isFolder=False)
        else:
            for item_data in resume_items:
                # Add resume time to label
                resume_time = item_data.get('resume_time', 0)
                minutes = int(resume_time // 60)
                label = f"{item_data.get('title', 'Neznámý')} (⏸️ {minutes}min)"
                
                list_item = self._create_history_list_item(item_data)
                list_item.setLabel(label)
                
                url = self.build_url({
                    "action": "play",
                    "ident": item_data.get("ident"),
                    "media_type": item_data.get("media_type", "movie")
                })
                xbmcplugin.addDirectoryItem(self.handle, url, list_item, isFolder=False)
        
        xbmcplugin.endOfDirectory(self.handle)

    def show_playback_stats(self) -> None:
        """Show playback statistics."""
        try:
            import json
            
            recent_items = json.loads(self.addon.getSetting("recent_items") or "[]")
            frequent_items = json.loads(self.addon.getSetting("frequent_items") or "[]")
            favorites = json.loads(self.addon.getSetting("favorites") or "[]")
            
            total_plays = sum(item.get("play_count", 1) for item in frequent_items)
            total_unique = len(frequent_items)
            
            # Find most played item
            most_played = None
            if frequent_items:
                most_played = max(frequent_items, key=lambda x: x.get("play_count", 0))
            
            # Create stats message
            stats_lines = [
                f"📊 STATISTIKY PŘEHRÁVÁNÍ",
                "",
                f"Celkem přehrání: {total_plays}",
                f"Unikátních položek: {total_unique}",
                f"Nedávno přehraných: {len(recent_items)}",
                f"Oblíbených: {len(favorites)}",
                ""
            ]
            
            if most_played:
                stats_lines.extend([
                    f"Nejčastěji přehráváno:",
                    f"'{most_played.get('title', 'Neznámý')}'",
                    f"({most_played.get('play_count', 0)} krát)",
                    ""
                ])
            
            # Show in dialog
            dialog = xbmcgui.Dialog()
            dialog.textviewer("Statistiky přehrávání", "\n".join(stats_lines))
            
        except Exception as e:
            self._logger(f"Error showing stats: {e}", xbmc.LOGERROR)
            self.notify("Chyba při zobrazení statistik", level=xbmc.LOGWARNING)

    def clear_history(self) -> None:
        """Clear playback history with confirmation."""
        dialog = xbmcgui.Dialog()
        
        # Show options for what to clear
        options = [
            "Nedávno přehrané",
            "Nejčastěji přehrávané", 
            "Oblíbené",
            "Pozastavené filmy",
            "Celou historii"
        ]
        
        selected = dialog.select("Co chcete vymazat?", options)
        
        if selected == -1:  # User cancelled
            return
            
        # Confirmation dialog
        confirm_msg = f"Opravdu chcete vymazat '{options[selected]}'?"
        if not dialog.yesno("Potvrzení", confirm_msg):
            return
            
        try:
            if selected == 0:  # Recent
                self._clear_recent_history()
            elif selected == 1:  # Frequent
                self._clear_frequent_history()
            elif selected == 2:  # Favorites
                self._clear_favorites()
            elif selected == 3:  # Resume points
                self._clear_resume_points()
            elif selected == 4:  # All history
                self._clear_all_history()
                
            self.notify(f"{options[selected]} bylo vymazáno", level=xbmc.LOGINFO)
            
        except Exception as e:
            self._logger(f"Error clearing history: {e}", xbmc.LOGERROR)
            self.notify("Chyba při mazání historie", level=xbmc.LOGWARNING)

    def add_to_favorites(self) -> None:
        """Add current item to favorites."""
        ident = self.params.get("ident")
        if not ident:
            return
            
        try:
            # Get item info and add to favorites
            self._add_to_favorites_db(ident)
            self.notify("Přidáno do oblíbených", level=xbmc.LOGINFO)
        except Exception as e:
            self._logger(f"Error adding to favorites: {e}", xbmc.LOGERROR)
            self.notify("Chyba při přidávání do oblíbených", level=xbmc.LOGWARNING)

    # Helper methods for history management
    def _create_history_list_item(self, item_data: dict) -> xbmcgui.ListItem:
        """Create ListItem from history data."""
        title = item_data.get("title", "Neznámý")
        list_item = xbmcgui.ListItem(label=title)
        
        # Set video info
        info = {
            "title": title,
            "mediatype": "movie" if item_data.get("media_type") == "movie" else "episode"
        }
        
        # Add additional info if available
        if item_data.get("year"):
            info["year"] = item_data["year"]
        if item_data.get("plot"):
            info["plot"] = item_data["plot"]
        if item_data.get("season"):
            info["season"] = item_data["season"]
        if item_data.get("episode"):
            info["episode"] = item_data["episode"]
            
        list_item.setInfo("video", info)
        
        # Set artwork if available
        art = {}
        if item_data.get("thumb"):
            art["thumb"] = item_data["thumb"]
        if item_data.get("poster"):
            art["poster"] = item_data["poster"]
        if art:
            list_item.setArt(art)
            
        list_item.setProperty("IsPlayable", "true")
        return list_item

    def _get_recent_items(self) -> list:
        """Get recently played items from addon storage."""
        try:
            # Use addon settings to store recent items (simplified approach)
            recent_json = self.addon.getSetting("recent_items") or "[]"
            import json
            return json.loads(recent_json)
        except:
            return []

    def _get_frequent_items(self) -> list:
        """Get frequently played items."""
        try:
            frequent_json = self.addon.getSetting("frequent_items") or "[]"
            import json
            items = json.loads(frequent_json)
            # Sort by play count descending
            return sorted(items, key=lambda x: x.get("play_count", 0), reverse=True)[:20]
        except:
            return []

    def _get_favorites(self) -> list:
        """Get favorite items."""
        try:
            favorites_json = self.addon.getSetting("favorites") or "[]"
            import json
            return json.loads(favorites_json)
        except:
            return []

    def _get_resume_items(self) -> list:
        """Get items with resume points."""
        try:
            resume_json = self.addon.getSetting("resume_items") or "[]"
            import json
            return json.loads(resume_json)
        except:
            return []

    def _clear_recent_history(self):
        """Clear recent items history."""
        self.addon.setSetting("recent_items", "[]")

    def _clear_frequent_history(self):
        """Clear frequent items history."""
        self.addon.setSetting("frequent_items", "[]")

    def _clear_favorites(self):
        """Clear favorites."""
        self.addon.setSetting("favorites", "[]")

    def _clear_resume_points(self):
        """Clear resume points."""
        self.addon.setSetting("resume_items", "[]")

    def _clear_all_history(self):
        """Clear all history data."""
        self._clear_recent_history()
        self._clear_frequent_history() 
        self._clear_favorites()
        self._clear_resume_points()

    def _add_to_favorites_db(self, ident: str):
        """Add item to favorites database."""
        try:
            import json
            favorites_json = self.addon.getSetting("favorites") or "[]"
            favorites = json.loads(favorites_json)
            
            # Check if already in favorites
            for fav in favorites:
                if fav.get("ident") == ident:
                    return  # Already in favorites
            
            # Get item info (this would need to be enhanced to fetch actual item data)
            item_data = {
                "ident": ident,
                "title": f"Item {ident}",  # Placeholder - would need actual title
                "added_date": str(datetime.datetime.now()),
                "media_type": self.params.get("media_type", "movie")
            }
            
            favorites.append(item_data)
            self.addon.setSetting("favorites", json.dumps(favorites))
            
        except Exception as e:
            self._logger(f"Error adding to favorites DB: {e}", xbmc.LOGERROR)

    def _record_playback_history(self, ident: str):
        """Record item playback to history."""
        try:
            import json
            
            # Get current item info from catalogue
            media_type = self.params.get("media_type", "movie")
            item_info = self._get_item_info_by_ident(ident)
            
            if not item_info:
                self._logger(f"Could not get item info for ident: {ident}", xbmc.LOGWARNING)
                return
            
            # Extract item data with real information
            item_data = {
                "ident": ident,
                "title": item_info.get("title", f"Video {ident}"),
                "media_type": media_type,
                "play_date": str(datetime.datetime.now()),
                "year": item_info.get("year"),
                "thumb": item_info.get("thumb"),
                "plot": item_info.get("plot"),
                "season": item_info.get("season"),
                "episode": item_info.get("episode")
            }
            
            # Update recent items (keep last 30)
            recent_json = self.addon.getSetting("recent_items") or "[]"
            recent_items = json.loads(recent_json)
            
            # Remove item if already exists to avoid duplicates
            recent_items = [item for item in recent_items if item.get("ident") != ident]
            
            # Add to front of list
            recent_items.insert(0, item_data)
            
            # Keep only last 30 items
            recent_items = recent_items[:30]
            
            self.addon.setSetting("recent_items", json.dumps(recent_items))
            
            self._logger(f"Saved {len(recent_items)} recent items to storage. Latest: {item_data['title']}", xbmc.LOGINFO)
            
            # Update frequent items (play count)
            frequent_json = self.addon.getSetting("frequent_items") or "[]"
            frequent_items = json.loads(frequent_json)
            
            # Find existing item or create new one
            found = False
            for item in frequent_items:
                if item.get("ident") == ident:
                    item["play_count"] = item.get("play_count", 0) + 1
                    item["last_played"] = str(datetime.datetime.now())
                    found = True
                    break
            
            if not found:
                item_data["play_count"] = 1
                item_data["last_played"] = str(datetime.datetime.now())
                frequent_items.append(item_data)
            
            # Keep only top 50 most played items
            frequent_items = sorted(frequent_items, key=lambda x: x.get("play_count", 0), reverse=True)[:50]
            
            self.addon.setSetting("frequent_items", json.dumps(frequent_items))
            
            self._logger(f"Recorded playback history for ident: {ident}", xbmc.LOGDEBUG)
            
        except Exception as e:
            self._logger(f"Error recording playback history: {e}", xbmc.LOGERROR)

    def _get_item_info_by_ident(self, ident: str) -> dict:
        """Get item information by ident from various sources."""
        try:
            # Method 1: Try to get from current browse results if available
            if hasattr(self, '_current_items'):
                for item in self._current_items:
                    if getattr(item, 'ident', None) == ident:
                        return self._extract_item_info(item)
            
            # Method 2: Try to search by ident directly (if supported by API)
            try:
                # This would require API method to get item by ident
                # For now, we'll use a simplified approach
                pass
            except:
                pass
            
            # Method 3: Use stored context from params if available
            context_title = self.params.get("context_title")
            context_year = self.params.get("context_year")
            if context_title:
                return {
                    "title": context_title,
                    "year": context_year,
                    "thumb": None,
                    "plot": None,
                    "season": self.params.get("season"),
                    "episode": self.params.get("episode")
                }
            
            # Fallback: Basic info from ident
            return {
                "title": f"Položka {ident[:8]}...",  # Show first 8 chars of ident
                "year": None,
                "thumb": None,
                "plot": None,
                "season": None,
                "episode": None
            }
            
        except Exception as e:
            self._logger(f"Error getting item info for {ident}: {e}", xbmc.LOGWARNING)
            return {
                "title": f"Položka {ident[:8]}...",
                "year": None,
                "thumb": None,
                "plot": None,
                "season": None,
                "episode": None
            }

    def _extract_item_info(self, item) -> dict:
        """Extract information from catalogue item."""
        info = {}
        
        # Title
        if hasattr(item, 'metadata') and item.metadata:
            info["title"] = item.metadata.get("title", item.cleaned_title if hasattr(item, 'cleaned_title') else str(item))
        elif hasattr(item, 'cleaned_title'):
            info["title"] = item.cleaned_title
        else:
            info["title"] = str(item)
        
        # Year
        if hasattr(item, 'metadata') and item.metadata:
            info["year"] = item.metadata.get("year")
        elif hasattr(item, 'guessed_year'):
            info["year"] = item.guessed_year
        else:
            info["year"] = None
            
        # Thumbnail
        if hasattr(item, 'metadata') and item.metadata and item.metadata.get("poster"):
            info["thumb"] = item.metadata.get("poster")
        elif hasattr(item, 'preview_image') and item.preview_image:
            info["thumb"] = item.preview_image
        else:
            info["thumb"] = None
            
        # Plot
        if hasattr(item, 'metadata') and item.metadata:
            info["plot"] = item.metadata.get("plot")
        else:
            info["plot"] = None
            
        # Season/Episode
        info["season"] = getattr(item, 'season', None) if hasattr(item, 'season') else None
        info["episode"] = getattr(item, 'episode', None) if hasattr(item, 'episode') else None
        
        return info
