"""Kodi routing layer for the TVStreamCZ add-on."""
from __future__ import annotations

import sys
import urllib.parse
from typing import Dict, Optional

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from .catalogue import WebshareCatalogue
from .metadata import MetadataManager
from .settings import AddonSettings
from .webshare_api import WebshareAPI, WebshareAuthError, WebshareError


class Plugin:
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

    def _create_list_item(self, item, media_type: Optional[str]) -> xbmcgui.ListItem:
        label = item.metadata.get("title") if item.metadata else item.cleaned_title
        if not label:
            label = item.cleaned_title
        suffix_parts = []
        if item.season is not None and item.episode is not None:
            suffix_parts.append(f"S{item.season:02d}E{item.episode:02d}")
        if item.quality:
            suffix_parts.append(item.quality.upper())
        if item.audio_languages:
            suffix_parts.append("/".join(code.upper() for code in item.audio_languages))
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
        list_item.setProperty("IsPlayable", "true")
        return list_item

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------
    def run(self) -> None:
        action = self.params.get("action")
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
        elif action == "play":
            self.play_item()
        else:
            self.show_root()

    def show_root(self) -> None:
        xbmcplugin.setPluginCategory(self.handle, self.addon.getAddonInfo("name"))
        xbmcplugin.setContent(self.handle, "videos")
        entries = [
            (self._localized(32000), {"action": "media_root", "media_type": "movie"}),
            (self._localized(32001), {"action": "media_root", "media_type": "tvshow"}),
            ("📺 Kategorie (TMDb/ČSFD)", {"action": "metadata_categories"}),
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
        
        # For TV shows, redirect to structured series list
        if media_type == "tvshow":
            self._logger("Redirecting to show_series_list", xbmc.LOGINFO)
            self.show_series_list()
            return
            
        letter = self.params.get("letter")
        quality = self.params.get("quality") or self.settings.default_quality
        audio = self.params.get("audio") or self.settings.default_audio
        subtitles = self.params.get("subtitles") or self.settings.default_subtitles
        genre = self.params.get("genre")
        sort = self.params.get("sort")
        query = self.params.get("query") or ""
        offset = int(self.params.get("offset", "0"))
        xbmcplugin.setPluginCategory(self.handle, self._localized(32000 if media_type == "movie" else 32001))
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
        )
        if not items:
            xbmcplugin.endOfDirectory(self.handle)
            if offset == 0:
                self.notify(self._localized(32020), level=xbmc.LOGINFO)
            return
        # If only a few items found and it's a direct search, show stream selection
        if query and len(items) <= 10 and not has_more:
            # Show stream selection dialog for direct search results
            self._show_stream_selection_for_browse(items, query)
            return
            
        for item in items:
            list_item = self._create_list_item(item, media_type)
            url = self.build_url({"action": "play", "ident": item.ident, "media_type": media_type})
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
        except WebshareError as exc:
            self.notify(str(exc), level=xbmc.LOGWARNING)
            xbmcplugin.setResolvedUrl(self.handle, False, xbmcgui.ListItem())
            return
        list_item = xbmcgui.ListItem(path=link)
        list_item.setProperty("IsPlayable", "true")
        xbmcplugin.setResolvedUrl(self.handle, True, list_item)

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
        
        # If only one series found and it matches the query closely, auto-navigate to it
        if len(series_names) == 1 and query.lower() in list(series_names)[0].lower():
            single_series = list(series_names)[0]
            self._logger(f"Single series match found: '{single_series}', auto-navigating", xbmc.LOGINFO)
            # Navigate directly to seasons
            self.params = {"action": "show_seasons", "series_name": single_series, "query": query}
            self.show_seasons(single_series)
            return
        
        xbmcplugin.setPluginCategory(self.handle, f"Vyhledávání: {query}")
        xbmcplugin.setContent(self.handle, "tvshows")
        
        # Show unique series
        for series_name in sorted(series_names):
            example_item = series_examples[series_name]
            list_item = xbmcgui.ListItem(label=series_name)
            list_item.setInfo('video', {
                'title': series_name,
                'mediatype': 'tvshow',
                'plot': f'Seriál {series_name}'
            })
            
            if example_item.preview_image:
                list_item.setArt({'thumb': example_item.preview_image})
            
            url = self.build_url({
                "action": "show_seasons", 
                "series_name": series_name,
                "query": query
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
            
            url = self.build_url({"action": "play", "ident": item.ident, "media_type": "tvshow"})
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
                xbmcplugin.addDirectoryItem(self.handle, url, list_item, isFolder=True)
            
        xbmcplugin.endOfDirectory(self.handle)
    
    def search_and_play_episode(self) -> None:
        """Search Webshare for specific episode and show stream selection dialog."""
        query = self.params.get("query", "")
        series_name = self.params.get("series_name", "")
        season = self.params.get("season", "")
        episode = self.params.get("episode", "")
        
        self._logger(f"search_and_play_episode: {query}", xbmc.LOGINFO)
        
        if not query:
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
            return
        
        # Show stream selection dialog
        self._show_stream_selection(items, f"{series_name} S{season}E{episode}")
    
    def _show_stream_selection(self, items, title="Vyberte stream"):
        """Show stream selection dialog with quality info."""
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
    
    def _play_item(self, item):
        """Play media item using the standard plugin method."""
        try:
            # Use the existing play_item method which handles Webshare API properly
            self.params = {"ident": item.ident, "media_type": item.media_type}
            self.play_item()
            
        except Exception as e:
            self._logger(f"Error playing item: {e}", xbmc.LOGERROR)
            self.notify("Chyba při přehrávání", level=xbmc.LOGERROR)
    
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
            list_item = self._create_list_item(item, media_type)
            url = self.build_url({"action": "play", "ident": item.ident, "media_type": media_type})
            xbmcplugin.addDirectoryItem(self.handle, url, list_item, isFolder=False)
            
        xbmcplugin.endOfDirectory(self.handle)

    # Metadata-based browsing methods
    def show_metadata_categories(self) -> None:
        """Show main metadata categories menu."""
        xbmcplugin.setPluginCategory(self.handle, "Kategorie")
        xbmcplugin.setContent(self.handle, "videos")
        
        entries = [
            ("🎬 Filmy", {"action": "metadata_movies"}),
            ("📺 Seriály", {"action": "metadata_tvshows"}),
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
            ("🔥 Populární filmy", {"action": "metadata_movie_category", "category": "popular"}),
            ("⭐ Nejlépe hodnocené", {"action": "metadata_movie_category", "category": "top_rated"}),
            ("🎭 V kinech", {"action": "metadata_movie_category", "category": "now_playing"}),
            ("📅 Připravované", {"action": "metadata_movie_category", "category": "upcoming"}),
            ("🎭 Podle žánru", {"action": "metadata_genre_movies"}),
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
            ("🔥 Populární seriály", {"action": "metadata_tv_category", "category": "popular"}),
            ("⭐ Nejlépe hodnocené", {"action": "metadata_tv_category", "category": "top_rated"}),
            ("📺 Vysílané dnes", {"action": "metadata_tv_category", "category": "airing_today"}),
            ("📡 Aktuálně vysílané", {"action": "metadata_tv_category", "category": "on_the_air"}),
            ("🎭 Podle žánru", {"action": "metadata_genre_tvshows"}),
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

    def show_metadata_tv_category(self) -> None:
        """Show TV shows from a specific category."""
        category = self.params.get("category", "popular")
        page = int(self.params.get("page", "1"))
        
        if not self.metadata or not self.metadata.has_providers():
            self.notify("Metadata poskytovatelé nejsou k dispozici", level=xbmc.LOGWARNING)
            return
        
        # Map category to method
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
                item = xbmcgui.ListItem(label=f"🎬 {genre_name}")
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
                item = xbmcgui.ListItem(label=f"📺 {genre_name}")
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
            
            # Create URL for Webshare search
            if media_type == "movie":
                search_query = title
                if year:
                    search_query += f" {year}"
                url = self.build_url({
                    "action": "browse",
                    "query": search_query,
                    "media_type": "movie"
                })
            else:  # tvshow
                url = self.build_url({
                    "action": "show_metadata_seasons",
                    "series_name": title,
                    "series_id": item.get("id"),
                    "original_query": title
                })
            
            xbmcplugin.addDirectoryItem(self.handle, url, list_item, isFolder=True)
        
        # Add "Next page" if we have full results (usually 20 items per page)
        if len(content_list) >= 20:
            next_params = dict(self.params)
            next_params["page"] = str(page + 1)
            next_url = self.build_url(next_params)
            next_item = xbmcgui.ListItem(label=f"▶️ Další strana ({page + 1})")
            xbmcplugin.addDirectoryItem(self.handle, next_url, next_item, isFolder=True)
        
        xbmcplugin.endOfDirectory(self.handle)
