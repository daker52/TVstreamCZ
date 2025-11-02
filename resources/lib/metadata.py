"""Metadata providers for enriching Webshare items."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Iterable, List, Optional

import requests
import xbmc

from .parser import MediaItem

_TMDb_IMAGE_BASE = "https://image.tmdb.org/t/p/"
_TMDb_POSTER_SIZE = "w500"
_TMDb_FANART_SIZE = "w780"


class MetadataProvider:
    """Abstract metadata provider."""

    name = "base"

    def enrich(self, item: MediaItem) -> Optional[Dict[str, object]]:  # pragma: no cover - interface
        raise NotImplementedError

    def get_genres(self, media_type: str) -> Optional[List[str]]:  # pragma: no cover - interface
        return None


@dataclass
class ProviderContext:
    session: requests.Session
    language: str
    region: Optional[str]


class TMDbMetadataProvider(MetadataProvider):
    name = "tmdb"

    def __init__(self, api_key: str, language: str, region: Optional[str], logger):
        self._api_key = api_key
        self._ctx = ProviderContext(requests.Session(), language, region or None)
        self._logger = logger
        self._genre_cache: Dict[str, List[str]] = {}

    def _request(self, path: str, params: Optional[Dict[str, object]] = None) -> Optional[Dict[str, object]]:
        payload = {
            "api_key": self._api_key,
            "language": self._ctx.language,
        }
        if params:
            payload.update(params)
        try:
            response = self._ctx.session.get(
                f"https://api.themoviedb.org/3/{path}", params=payload, timeout=12
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            self._logger(f"TMDb request failed ({path}): {exc}", xbmc.LOGWARNING)
            return None
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            self._logger(f"TMDb JSON decode error ({path}): {exc}", xbmc.LOGWARNING)
            return None

    def _normalise(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.lower())

    def _candidate_score(self, query: MediaItem, title: str, year: Optional[int]) -> int:
        score = 0
        cleaned_query = self._normalise(query.cleaned_title)
        cleaned_title = self._normalise(title)
        if cleaned_query == cleaned_title:
            score += 80
        elif cleaned_query in cleaned_title or cleaned_title in cleaned_query:
            score += 50
        if query.guessed_year and year:
            if abs(query.guessed_year - year) <= 1:
                score += 30
            else:
                score -= 20
        if query.media_type == "tvshow" and query.season is not None:
            score += 10
        return score

    def _build_image(self, path: Optional[str], size: str) -> Optional[str]:
        if not path:
            return None
        return f"{_TMDb_IMAGE_BASE}{size}{path}"

    @lru_cache(maxsize=128)
    def _details(self, media_type: str, tmdb_id: int) -> Optional[Dict[str, object]]:
        endpoint = "movie" if media_type == "movie" else "tv"
        return self._request(f"{endpoint}/{tmdb_id}")

    def _search(self, media_type: str, item: MediaItem) -> Optional[Dict[str, object]]:
        endpoint = "search/movie" if media_type == "movie" else "search/tv"
        params: Dict[str, object] = {"query": item.cleaned_title, "include_adult": "false"}
        if item.guessed_year and media_type == "movie":
            params["year"] = item.guessed_year
        if item.guessed_year and media_type == "tvshow":
            params["first_air_date_year"] = item.guessed_year
        if self._ctx.region:
            params["region"] = self._ctx.region
        data = self._request(endpoint, params)
        if not data or not data.get("results"):
            return None
        scored: List[Dict[str, object]] = []
        for result in data["results"]:
            title_field = result.get("title") or result.get("name") or ""
            year_field: Optional[int] = None
            release_date = result.get("release_date") or result.get("first_air_date")
            if release_date:
                try:
                    year_field = int(release_date.split("-", 1)[0])
                except (ValueError, AttributeError):
                    year_field = None
            score = self._candidate_score(item, title_field, year_field)
            result["__score"] = score
            result["__year"] = year_field
            scored.append(result)
        scored.sort(key=lambda entry: entry.get("__score", 0), reverse=True)
        return scored[0] if scored else None

    def enrich(self, item: MediaItem) -> Optional[Dict[str, object]]:
        candidate = self._search(item.media_type, item)
        if not candidate:
            return None
        tmdb_id = candidate.get("id")
        if tmdb_id is None:
            return None
        details = self._details(item.media_type, int(tmdb_id))
        if not details:
            return None
        title = details.get("title") or details.get("name") or item.cleaned_title
        original_title = details.get("original_title") or details.get("original_name")
        overview = details.get("overview") or candidate.get("overview")
        poster = self._build_image(details.get("poster_path") or candidate.get("poster_path"), _TMDb_POSTER_SIZE)
        fanart = self._build_image(details.get("backdrop_path") or candidate.get("backdrop_path"), _TMDb_FANART_SIZE)
        release_date = details.get("release_date") or details.get("first_air_date")
        year = None
        if release_date:
            try:
                year = int(release_date.split("-", 1)[0])
            except (ValueError, AttributeError):
                year = None
        genres = [genre.get("name") for genre in details.get("genres", []) if genre.get("name")]
        rating = details.get("vote_average")
        vote_count = details.get("vote_count")
        metadata = {
            "title": title,
            "originaltitle": original_title,
            "plot": overview,
            "poster": poster,
            "fanart": fanart,
            "year": year,
            "genres": genres,
            "rating": rating,
            "votes": vote_count,
            "provider": "TMDb",
            "id": tmdb_id,
        }
        if item.media_type == "tvshow":
            metadata["tvshowtitle"] = title
        return metadata

    def get_genres(self, media_type: str) -> Optional[List[str]]:
        if media_type in self._genre_cache:
            return self._genre_cache[media_type]
        endpoint = "genre/movie/list" if media_type == "movie" else "genre/tv/list"
        data = self._request(endpoint)
        if not data or not data.get("genres"):
            return None
        names = [genre.get("name") for genre in data["genres"] if genre.get("name")]
        self._genre_cache[media_type] = names
        return names
    
    def search_tv_series(self, series_name: str) -> Optional[Dict[str, object]]:
        """Search for TV series and get season information with fallback."""
        from .title_mapping import CZECH_TO_ENGLISH_MAPPING
        
        # Try multiple search strategies
        search_terms = [series_name.lower()]
        
        # Add English equivalent if available
        english_title = CZECH_TO_ENGLISH_MAPPING.get(series_name.lower())
        if english_title:
            search_terms.append(english_title)
            self._logger(f"Using English mapping: '{series_name}' -> '{english_title}'", xbmc.LOGINFO)
        
        # Try different search terms
        for search_term in search_terms:
            self._logger(f"Searching TMDb for: '{search_term}'", xbmc.LOGINFO)
            
            # Try with current language first
            params = {"query": search_term, "include_adult": "false"}
            if self._ctx.region:
                params["region"] = self._ctx.region
                
            data = self._request("search/tv", params)
            
            # If no results with current language, try English
            if not data or not data.get("results"):
                self._logger(f"No results with {self._ctx.language}, trying English", xbmc.LOGINFO)
                # Temporarily switch to English
                original_lang = self._ctx.language
                self._ctx.language = "en-US"
                data = self._request("search/tv", params)
                self._ctx.language = original_lang
            
            if data and data.get("results"):
                self._logger(f"Found {len(data['results'])} results for '{search_term}'", xbmc.LOGINFO)
                break
        
        if not data or not data.get("results"):
            self._logger(f"No TMDb results found for any search term", xbmc.LOGWARNING)
            return None
            
        # Get the first (best match) result
        series = data["results"][0]
        series_id = series.get("id")
        if not series_id:
            return None
            
        # Get detailed series information including seasons
        series_details = self._request(f"tv/{series_id}")
        if not series_details:
            return None
            
        # Extract season information - ensure we get all seasons
        seasons = []
        if "seasons" in series_details:
            all_seasons = series_details["seasons"]
            self._logger(f"Found {len(all_seasons)} total seasons", xbmc.LOGINFO)
            
            for season in all_seasons:
                season_num = season.get("season_number", 0)
                # Skip season 0 (specials) unless it's the only season
                if season_num == 0 and len(all_seasons) > 1:
                    continue
                    
                season_data = {
                    "season_number": season_num,
                    "episode_count": season.get("episode_count", 0),
                    "name": season.get("name", f"Série {season_num}"),
                    "poster_path": season.get("poster_path"),
                    "air_date": season.get("air_date")
                }
                seasons.append(season_data)
                self._logger(f"Added season {season_num}: {season.get('episode_count', 0)} episodes", xbmc.LOGINFO)
        
        return {
            "id": series_id,
            "name": series_details.get("name", series_name),
            "overview": series_details.get("overview"),
            "poster_path": series_details.get("poster_path"),
            "backdrop_path": series_details.get("backdrop_path"),
            "first_air_date": series_details.get("first_air_date"),
            "seasons": seasons
        }
    
    def get_season_episodes(self, series_id: int, season_number: int) -> Optional[List[Dict[str, object]]]:
        """Get episodes for a specific season."""
        season_details = self._request(f"tv/{series_id}/season/{season_number}")
        if not season_details:
            return None
            
        episodes = []
        if "episodes" in season_details:
            for episode in season_details["episodes"]:
                episodes.append({
                    "episode_number": episode.get("episode_number", 1),
                    "name": episode.get("name", f"Episode {episode.get('episode_number', 1)}"),
                    "overview": episode.get("overview", ""),
                    "still_path": episode.get("still_path"),
                    "air_date": episode.get("air_date"),
                    "runtime": episode.get("runtime"),
                    "vote_average": episode.get("vote_average")
                })
        
        return episodes
    
    def get_popular_movies(self, page: int = 1) -> Optional[List[Dict[str, object]]]:
        """Get popular movies from TMDb."""
        data = self._request("movie/popular", {"page": page})
        if not data or not data.get("results"):
            return None
        return self._format_movie_results(data["results"])
    
    def get_top_rated_movies(self, page: int = 1) -> Optional[List[Dict[str, object]]]:
        """Get top rated movies from TMDb."""
        data = self._request("movie/top_rated", {"page": page})
        if not data or not data.get("results"):
            return None
        return self._format_movie_results(data["results"])
    
    def get_now_playing_movies(self, page: int = 1) -> Optional[List[Dict[str, object]]]:
        """Get movies currently in theaters."""
        params = {"page": page}
        if self._ctx.region:
            params["region"] = self._ctx.region
        data = self._request("movie/now_playing", params)
        if not data or not data.get("results"):
            return None
        return self._format_movie_results(data["results"])
    
    def get_upcoming_movies(self, page: int = 1) -> Optional[List[Dict[str, object]]]:
        """Get upcoming movies."""
        params = {"page": page}
        if self._ctx.region:
            params["region"] = self._ctx.region
        data = self._request("movie/upcoming", params)
        if not data or not data.get("results"):
            return None
        return self._format_movie_results(data["results"])
    
    def get_popular_tv_shows(self, page: int = 1) -> Optional[List[Dict[str, object]]]:
        """Get popular TV shows from TMDb."""
        data = self._request("tv/popular", {"page": page})
        if not data or not data.get("results"):
            return None
        return self._format_tv_results(data["results"])
    
    def get_top_rated_tv_shows(self, page: int = 1) -> Optional[List[Dict[str, object]]]:
        """Get top rated TV shows from TMDb."""
        data = self._request("tv/top_rated", {"page": page})
        if not data or not data.get("results"):
            return None
        return self._format_tv_results(data["results"])
    
    def get_airing_today_tv_shows(self, page: int = 1) -> Optional[List[Dict[str, object]]]:
        """Get TV shows airing today."""
        data = self._request("tv/airing_today", {"page": page})
        if not data or not data.get("results"):
            return None
        return self._format_tv_results(data["results"])
    
    def get_on_the_air_tv_shows(self, page: int = 1) -> Optional[List[Dict[str, object]]]:
        """Get TV shows currently on the air."""
        data = self._request("tv/on_the_air", {"page": page})
        if not data or not data.get("results"):
            return None
        return self._format_tv_results(data["results"])
    
    def get_movies_by_genre(self, genre_id: int, page: int = 1) -> Optional[List[Dict[str, object]]]:
        """Get movies by genre."""
        params = {"with_genres": genre_id, "page": page, "sort_by": "popularity.desc"}
        if self._ctx.region:
            params["region"] = self._ctx.region
        data = self._request("discover/movie", params)
        if not data or not data.get("results"):
            return None
        return self._format_movie_results(data["results"])
    
    def get_tv_shows_by_genre(self, genre_id: int, page: int = 1) -> Optional[List[Dict[str, object]]]:
        """Get TV shows by genre."""
        params = {"with_genres": genre_id, "page": page, "sort_by": "popularity.desc"}
        data = self._request("discover/tv", params)
        if not data or not data.get("results"):
            return None
        return self._format_tv_results(data["results"])
    
    def get_genre_list(self, media_type: str) -> Optional[Dict[int, str]]:
        """Get list of genres with IDs."""
        endpoint = "genre/movie/list" if media_type == "movie" else "genre/tv/list"
        data = self._request(endpoint)
        if not data or not data.get("genres"):
            return None
        return {genre["id"]: genre["name"] for genre in data["genres"]}
    
    def _format_movie_results(self, results: List[Dict[str, object]]) -> List[Dict[str, object]]:
        """Format movie results with standard fields."""
        formatted = []
        for movie in results:
            formatted_movie = {
                "id": movie.get("id"),
                "title": movie.get("title", ""),
                "original_title": movie.get("original_title"),
                "overview": movie.get("overview", ""),
                "release_date": movie.get("release_date"),
                "poster_path": self._build_image(movie.get("poster_path"), _TMDb_POSTER_SIZE),
                "backdrop_path": self._build_image(movie.get("backdrop_path"), _TMDb_FANART_SIZE),
                "vote_average": movie.get("vote_average", 0),
                "vote_count": movie.get("vote_count", 0),
                "popularity": movie.get("popularity", 0),
                "media_type": "movie"
            }
            # Extract year from release date
            if formatted_movie["release_date"]:
                try:
                    formatted_movie["year"] = int(formatted_movie["release_date"].split("-")[0])
                except (ValueError, AttributeError):
                    formatted_movie["year"] = None
            formatted.append(formatted_movie)
        return formatted
    
    def _format_tv_results(self, results: List[Dict[str, object]]) -> List[Dict[str, object]]:
        """Format TV show results with standard fields."""
        formatted = []
        for show in results:
            formatted_show = {
                "id": show.get("id"),
                "name": show.get("name", ""),
                "title": show.get("name", ""),  # For compatibility
                "original_name": show.get("original_name"),
                "overview": show.get("overview", ""),
                "first_air_date": show.get("first_air_date"),
                "poster_path": self._build_image(show.get("poster_path"), _TMDb_POSTER_SIZE),
                "backdrop_path": self._build_image(show.get("backdrop_path"), _TMDb_FANART_SIZE),
                "vote_average": show.get("vote_average", 0),
                "vote_count": show.get("vote_count", 0),
                "popularity": show.get("popularity", 0),
                "media_type": "tvshow"
            }
            # Extract year from first air date
            if formatted_show["first_air_date"]:
                try:
                    formatted_show["year"] = int(formatted_show["first_air_date"].split("-")[0])
                except (ValueError, AttributeError):
                    formatted_show["year"] = None
            formatted.append(formatted_show)
        return formatted


class CSFDMetadataProvider(MetadataProvider):
    name = "csfd"

    _SECTION_TEMPLATE = r'<section class="main-box" data-search-results="{kind}".*?<div id="snippet--container[^>]+>(?P<body>.*?)</section>'
    _ARTICLE_RE = re.compile(r"<article class=\"article[\s\S]*?<\/article>")
    _TITLE_RE = re.compile(r'class="film-title-name">([^<]+)</a>')
    _HREF_RE = re.compile(r'<a href="(/(?:film|serial)/[^"]+)"')
    _YEAR_RE = re.compile(r'<span class="info">\((\d{4})\)</span>')
    _GENRES_RE = re.compile(r'<p class="film-origins-genres"><span class="info">([^<]+)</span></p>')
    _IMG_RE = re.compile(r'<img[^>]+src="([^"]+)"')
    _RATING_RE = re.compile(r'<div class="film-rating-average">\s*(\d+)%')
    _ORIGIN_RE = re.compile(r'<div class="origin">([^<]+)</div>')
    _JSONLD_RE = re.compile(r'<script type="application/ld\+json">([^<]+)</script>')
    _PLOT_RE = re.compile(r'<div class="plot-preview">([\s\S]*?)</div>')

    def __init__(self, user_agent: str, logger):
        self._session = requests.Session()
        # Use better headers based on the working ČSFD scraper
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36"
        })
        self._logger = logger

    def _strip_tags(self, html: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html)).strip()

    def _fetch(self, url: str) -> Optional[str]:
        try:
            response = self._session.get(url, timeout=12)
            response.raise_for_status()
            response.encoding = response.encoding or "utf-8"
            return response.text
        except requests.RequestException as exc:
            self._logger(f"ČSFD request failed: {exc}", xbmc.LOGWARNING)
            return None

    def _search(self, query: str, kind: str) -> Optional[Dict[str, object]]:
        url = f"https://www.csfd.cz/hledat/?q={requests.utils.quote(query)}"
        html = self._fetch(url)
        if not html:
            return None
        section_re = re.compile(self._SECTION_TEMPLATE.format(kind=kind), re.S)
        section_match = section_re.search(html)
        if not section_match:
            return None
        section_body = section_match.group("body")
        article_match = self._ARTICLE_RE.search(section_body)
        if not article_match:
            return None
        article = article_match.group(0)
        title_match = self._TITLE_RE.search(article)
        href_match = self._HREF_RE.search(article)
        if not title_match or not href_match:
            return None
        year_match = self._YEAR_RE.search(article)
        genres_match = self._GENRES_RE.search(article)
        img_match = self._IMG_RE.search(article)
        href = href_match.group(1)
        poster = img_match.group(1) if img_match else None
        if poster and poster.startswith("//"):
            poster = "https:" + poster
        genres = []
        if genres_match:
            genres = [self._strip_tags(part).strip() for part in genres_match.group(1).split("/")]
            genres = [genre for genre in genres if genre]
        return {
            "title": title_match.group(1).strip(),
            "href": href,
            "year": int(year_match.group(1)) if year_match else None,
            "poster": poster,
            "genres": genres,
        }

    def _detail(self, path: str) -> Optional[Dict[str, object]]:
        url = f"https://www.csfd.cz{path}"
        html = self._fetch(url)
        if not html:
            return None
        result: Dict[str, object] = {"url": url}
        jsonld_match = self._JSONLD_RE.search(html)
        if jsonld_match:
            try:
                data = json.loads(jsonld_match.group(1))
                if isinstance(data, dict):
                    result["title"] = data.get("name")
                    result["description"] = data.get("description")
                    year_value = data.get("dateCreated") or data.get("datePublished")
                    if year_value:
                        try:
                            result["year"] = int(str(year_value)[:4])
                        except (ValueError, TypeError):
                            pass
                    agg = data.get("aggregateRating") or {}
                    rating_value = agg.get("ratingValue")
                    if rating_value is not None:
                        try:
                            result["rating"] = float(rating_value) / 10.0
                        except (ValueError, TypeError):
                            result["rating"] = None
                    result["votes"] = agg.get("ratingCount")
                    if data.get("image"):
                        result["poster"] = data.get("image")
            except json.JSONDecodeError:
                self._logger("ČSFD JSON-LD parse failed", xbmc.LOGWARNING)
        rating_match = self._RATING_RE.search(html)
        if rating_match and "rating" not in result:
            try:
                result["rating"] = float(rating_match.group(1)) / 10.0
            except ValueError:
                result["rating"] = None
        origin_match = self._ORIGIN_RE.search(html)
        if origin_match:
            origin_text = self._strip_tags(origin_match.group(1))
            result["origin"] = origin_text
            if "year" not in result:
                years = re.findall(r"(19|20)\d{2}", origin_text)
                if years:
                    try:
                        result["year"] = int(years[0])
                    except ValueError:
                        pass
        plot_match = self._PLOT_RE.search(html)
        if plot_match:
            result["plot"] = self._strip_tags(plot_match.group(1))
        genres_section = re.search(r'<div class="genres">([\s\S]*?)</div>', html)
        if genres_section:
            raw = self._strip_tags(genres_section.group(1))
            genres = [part.strip() for part in raw.split("/") if part.strip()]
            result["genres"] = genres
        return result

    def enrich(self, item: MediaItem) -> Optional[Dict[str, object]]:
        kind = "films" if item.media_type == "movie" else "series"
        candidate = self._search(item.cleaned_title, kind)
        if not candidate:
            return None
        detail = self._detail(candidate["href"])
        if not detail:
            return None
        poster = detail.get("poster") or candidate.get("poster")
        metadata = {
            "title": detail.get("title") or candidate.get("title"),
            "plot": detail.get("plot") or detail.get("description"),
            "poster": poster,
            "fanart": poster,
            "year": detail.get("year") or candidate.get("year"),
            "genres": detail.get("genres") or candidate.get("genres"),
            "rating": detail.get("rating"),
            "votes": detail.get("votes"),
            "country": detail.get("origin"),
            "provider": "ČSFD",
            "url": detail.get("url"),
        }
        return metadata
    
    def search_tv_series(self, series_name: str) -> Optional[Dict[str, object]]:
        """Search for TV series on ČSFD with enhanced detection patterns."""
        from .title_mapping import CZECH_TO_ENGLISH_MAPPING
        
        # Try both original and English name
        search_terms = [series_name.lower()]
        english_title = CZECH_TO_ENGLISH_MAPPING.get(series_name.lower())
        if english_title:
            search_terms.append(english_title)
        
        for search_term in search_terms:
            self._logger(f"Searching ČSFD for TV series: '{search_term}'", xbmc.LOGINFO)
            
            # Search for series on ČSFD
            search_url = f"https://www.csfd.cz/hledat/?q={requests.utils.quote(search_term)}"
            
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'cs,en-US;q=0.7,en;q=0.3'
                }
                
                response = self._session.get(search_url, headers=headers, timeout=10)
                response.raise_for_status()
                content = response.text
                
                # Enhanced TV series detection patterns
                series_patterns = [
                    # Direct serial URLs
                    (r'<a href="(/serial/[^"]+)"[^>]*>.*?class="film-title-name">([^<]+)</a>', "serial"),
                    # TV series under film URLs (some series are classified as films)
                    (r'<a href="(/film/[^"]+)"[^>]*>.*?class="film-title-name">([^<]+)</a>.*?(?:seriál|TV seriál)', "film-serial"),
                    # Series with explicit type indication
                    (r'<a href="(/film/[^"]+)"[^>]*>.*?<span[^>]*>([^<]+)</span>.*?(?:série|season)', "film-series")
                ]
                
                for pattern, pattern_type in series_patterns:
                    series_match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
                    if series_match:
                        series_url = "https://www.csfd.cz" + series_match.group(1)
                        series_title = series_match.group(2).strip()
                        
                        self._logger(f"Found series via {pattern_type}: '{series_title}' at {series_url}", xbmc.LOGINFO)
                        
                        # Get enhanced series details
                        series_data = self._get_series_details(series_url, series_title)
                        if series_data:
                            return series_data
                
                # If no direct matches, try broader search in results
                if "/film/" in content or "/serial/" in content:
                    self._logger(f"Trying broader match for '{search_term}'", xbmc.LOGINFO)
                    
                    # Look for any film/serial that might be a TV show
                    all_matches = re.findall(r'<a href="(/(?:film|serial)/[^"]+)"[^>]*>.*?class="film-title-name">([^<]+)</a>', content, re.DOTALL)
                    
                    for url_path, title in all_matches[:3]:  # Try first 3 results
                        series_url = "https://www.csfd.cz" + url_path
                        
                        # Quick check if this might be a TV series
                        if self._is_likely_tv_series(series_url, title, search_term):
                            series_data = self._get_series_details(series_url, title.strip())
                            if series_data and series_data.get("seasons") and len(series_data["seasons"]) > 0:
                                return series_data
                            
            except Exception as e:
                self._logger(f"ČSFD search failed for '{search_term}': {e}", xbmc.LOGWARNING)
                continue
        
        return None
    
    def _is_likely_tv_series(self, url: str, title: str, search_term: str) -> bool:
        """Quick heuristic check if a ČSFD entry is likely a TV series."""
        try:
            # Title similarity check
            if search_term.lower() not in title.lower():
                return False
            
            # Quick page check for series indicators
            response = self._session.get(url, timeout=5)
            if response.status_code != 200:
                return False
                
            content = response.text[:2000]  # Just check beginning of page
            
            # Look for series indicators
            series_indicators = [
                'seriál', 'série', 'season', 'episode', 'epizoda',
                'S01E', 'S02E', 'S03E', 'TV seriál'
            ]
            
            for indicator in series_indicators:
                if indicator.lower() in content.lower():
                    self._logger(f"Found series indicator '{indicator}' for {title}", xbmc.LOGINFO)
                    return True
            
            return False
            
        except Exception:
            return False
    
    def _get_series_details(self, series_url: str, series_title: str) -> Optional[Dict[str, object]]:
        """Get detailed information about a TV series from ČSFD with enhanced structure detection."""
        try:
            response = self._session.get(series_url, timeout=10)
            response.raise_for_status()
            content = response.text
            
            # Extract basic info
            year_match = re.search(r'<span class="info">\((\d{4})[-–]?(\d{4})?\)</span>', content)
            plot_match = re.search(r'<div class="plot-preview">(.*?)</div>', content, re.DOTALL)
            
            # Enhanced season detection - ČSFD structure analysis
            seasons = []
            
            # Method 1: Look for direct season links in navigation
            season_links = re.findall(r'<a[^>]*href="[^"]*serie-(\d+)[^"]*"[^>]*>.*?Série\s*(\d+)', content, re.IGNORECASE)
            if season_links:
                self._logger(f"Found {len(season_links)} seasons via navigation links", xbmc.LOGINFO)
                for link_num, season_num in season_links:
                    seasons.append({
                        "season_number": int(season_num),
                        "episode_count": 0,  # Will be filled by episode detection
                        "name": f"Série {season_num}",
                        "poster_path": None,
                        "air_date": None
                    })
            
            # Method 2: Look for season information in structured data
            if not seasons:
                season_text_matches = re.findall(r'(?:Série|Season)\s*(\d+)', content, re.IGNORECASE)
                if season_text_matches:
                    self._logger(f"Found {len(set(season_text_matches))} seasons via text analysis", xbmc.LOGINFO)
                    for season_num in sorted(set(season_text_matches)):
                        seasons.append({
                            "season_number": int(season_num),
                            "episode_count": 0,
                            "name": f"Série {season_num}",
                            "poster_path": None,
                            "air_date": None
                        })
            
            # Method 3: Try to detect episodes and infer seasons from position codes
            if not seasons:
                episode_codes = re.findall(r'S(\d+)E(\d+)', content, re.IGNORECASE)
                if episode_codes:
                    season_numbers = sorted(set(int(s) for s, e in episode_codes))
                    self._logger(f"Found {len(season_numbers)} seasons via episode position codes", xbmc.LOGINFO)
                    for season_num in season_numbers:
                        episode_count = len([e for s, e in episode_codes if int(s) == season_num])
                        seasons.append({
                            "season_number": season_num,
                            "episode_count": episode_count,
                            "name": f"Série {season_num}",
                            "poster_path": None,
                            "air_date": None
                        })
            
            # Fallback: Assume at least 1 season if series detected
            if not seasons:
                self._logger("No specific seasons found, creating default season 1", xbmc.LOGINFO)
                seasons.append({
                    "season_number": 1,
                    "episode_count": 0,
                    "name": "Série 1",
                    "poster_path": None,
                    "air_date": None
                })
            
            # Sort seasons by season number
            seasons.sort(key=lambda x: x["season_number"])
            
            series_id = abs(hash(series_url)) % 10000  # Generate numeric ID from URL
            
            self._logger(f"ČSFD series '{series_title}' has {len(seasons)} seasons", xbmc.LOGINFO)
            
            return {
                "id": series_id,
                "name": series_title,
                "overview": self._strip_tags(plot_match.group(1)) if plot_match else "",
                "poster_path": None,  # ČSFD images might be protected
                "backdrop_path": None,
                "first_air_date": year_match.group(1) if year_match else None,
                "seasons": seasons,
                "source": "csfd",
                "csfd_url": series_url
            }
            
        except Exception as e:
            self._logger(f"Failed to get ČSFD series details: {e}", xbmc.LOGWARNING)
            return None
    
    def get_csfd_season_episodes(self, series_id: int, season_number: int, csfd_url: str = None) -> Optional[List[Dict[str, object]]]:
        """Get episodes for a specific season from ČSFD."""
        try:
            if not csfd_url:
                # Try to reconstruct URL from ID (limited functionality)
                self._logger(f"No ČSFD URL provided for season {season_number} episodes", xbmc.LOGWARNING)
                return None
            
            # Try to get season-specific page
            season_url = csfd_url.replace('/serial/', f'/serial/').rstrip('/') + f'/serie-{season_number}/'
            
            response = self._session.get(season_url, timeout=10)
            if response.status_code == 404:
                # Fallback to main series page
                response = self._session.get(csfd_url, timeout=10)
            
            response.raise_for_status()
            content = response.text
            
            episodes = []
            
            # Look for episode listings with position codes
            episode_pattern = r'S0?%dE(\d+)(?:[^>]*>([^<]+))?' % season_number
            episode_matches = re.findall(episode_pattern, content, re.IGNORECASE)
            
            if episode_matches:
                for episode_num, episode_title in episode_matches:
                    episodes.append({
                        "episode_number": int(episode_num),
                        "name": episode_title.strip() if episode_title else f"Episode {episode_num}",
                        "overview": "",
                        "still_path": None,
                        "air_date": None,
                        "runtime": None
                    })
            
            # Sort episodes by episode number
            episodes.sort(key=lambda x: x["episode_number"])
            
            self._logger(f"Found {len(episodes)} episodes for season {season_number} on ČSFD", xbmc.LOGINFO)
            return episodes
            
        except Exception as e:
            self._logger(f"Failed to get ČSFD season episodes: {e}", xbmc.LOGWARNING)
            return None


class MetadataManager:
    """Coordinates metadata lookup across providers."""

    def __init__(self, settings, logger):
        self._logger = logger
        self._providers: List[MetadataProvider] = []
        order = settings.metadata_provider
        if order == "none":
            return
        desired: List[str]
        if order == "tmdb_first":
            desired = ["tmdb", "csfd"]
        elif order == "csfd_first":
            desired = ["csfd", "tmdb"]
        elif order == "tmdb_only":
            desired = ["tmdb"]
        elif order == "csfd_only":
            desired = ["csfd"]
        else:
            desired = ["tmdb", "csfd"]
        for provider_name in desired:
            if provider_name == "tmdb" and settings.tmdb_api_key:
                self._providers.append(
                    TMDbMetadataProvider(settings.tmdb_api_key, settings.metadata_language, settings.metadata_region, logger)
                )
            elif provider_name == "csfd":
                self._providers.append(CSFDMetadataProvider(settings.csfd_user_agent, logger))
        self._cache: Dict[tuple, Optional[Dict[str, object]]] = {}

    def has_providers(self) -> bool:
        return bool(self._providers)

    def get_genres(self, media_type: str) -> Optional[List[str]]:
        for provider in self._providers:
            genres = provider.get_genres(media_type)
            if genres:
                return genres
        return None

    def enrich(self, item: MediaItem) -> Optional[Dict[str, object]]:
        cache_key = (item.media_type, item.cleaned_title.lower(), item.guessed_year, item.season)
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if cached:
                item.apply_metadata(cached)
            return cached
        metadata = None
        for provider in self._providers:
            try:
                metadata = provider.enrich(item)
            except Exception as exc:  # noqa: broad-except to keep plugin resilient
                self._logger(f"Metadata provider {provider.name} failed: {exc}", xbmc.LOGWARNING)
                metadata = None
            if metadata:
                item.apply_metadata(metadata)
                break
        self._cache[cache_key] = metadata
        return metadata
    
    def search_tv_series(self, series_name: str) -> Optional[Dict[str, object]]:
        """Search for TV series metadata including season information."""
        if not self.has_providers():
            return None
            
        for provider in self._providers:
            if hasattr(provider, 'search_tv_series'):
                try:
                    return provider.search_tv_series(series_name)
                except Exception as exc:
                    self._logger(f"TV series search failed for {provider.name}: {exc}", xbmc.LOGWARNING)
                    continue
        return None
    
    def get_season_episodes(self, series_id: int, season_number: int) -> Optional[List[Dict[str, object]]]:
        """Get episodes for a specific season."""
        if not self.has_providers():
            return None
            
        for provider in self._providers:
            if hasattr(provider, 'get_season_episodes'):
                try:
                    return provider.get_season_episodes(series_id, season_number)
                except Exception as exc:
                    self._logger(f"Season episodes fetch failed for {provider.name}: {exc}", xbmc.LOGWARNING)
                    continue
        return None
    
    # Movie category methods
    def get_popular_movies(self, page: int = 1) -> Optional[List[Dict[str, object]]]:
        """Get popular movies."""
        for provider in self._providers:
            if hasattr(provider, 'get_popular_movies'):
                try:
                    return provider.get_popular_movies(page)
                except Exception as exc:
                    self._logger(f"Popular movies fetch failed for {provider.name}: {exc}", xbmc.LOGWARNING)
                    continue
        return None
    
    def get_top_rated_movies(self, page: int = 1) -> Optional[List[Dict[str, object]]]:
        """Get top rated movies."""
        for provider in self._providers:
            if hasattr(provider, 'get_top_rated_movies'):
                try:
                    return provider.get_top_rated_movies(page)
                except Exception as exc:
                    self._logger(f"Top rated movies fetch failed for {provider.name}: {exc}", xbmc.LOGWARNING)
                    continue
        return None
    
    def get_now_playing_movies(self, page: int = 1) -> Optional[List[Dict[str, object]]]:
        """Get movies currently in theaters."""
        for provider in self._providers:
            if hasattr(provider, 'get_now_playing_movies'):
                try:
                    return provider.get_now_playing_movies(page)
                except Exception as exc:
                    self._logger(f"Now playing movies fetch failed for {provider.name}: {exc}", xbmc.LOGWARNING)
                    continue
        return None
    
    def get_upcoming_movies(self, page: int = 1) -> Optional[List[Dict[str, object]]]:
        """Get upcoming movies."""
        for provider in self._providers:
            if hasattr(provider, 'get_upcoming_movies'):
                try:
                    return provider.get_upcoming_movies(page)
                except Exception as exc:
                    self._logger(f"Upcoming movies fetch failed for {provider.name}: {exc}", xbmc.LOGWARNING)
                    continue
        return None
    
    def get_movies_by_genre(self, genre_id: int, page: int = 1) -> Optional[List[Dict[str, object]]]:
        """Get movies by genre."""
        for provider in self._providers:
            if hasattr(provider, 'get_movies_by_genre'):
                try:
                    return provider.get_movies_by_genre(genre_id, page)
                except Exception as exc:
                    self._logger(f"Movies by genre fetch failed for {provider.name}: {exc}", xbmc.LOGWARNING)
                    continue
        return None
    
    # TV Show category methods
    def get_popular_tv_shows(self, page: int = 1) -> Optional[List[Dict[str, object]]]:
        """Get popular TV shows."""
        for provider in self._providers:
            if hasattr(provider, 'get_popular_tv_shows'):
                try:
                    return provider.get_popular_tv_shows(page)
                except Exception as exc:
                    self._logger(f"Popular TV shows fetch failed for {provider.name}: {exc}", xbmc.LOGWARNING)
                    continue
        return None
    
    def get_top_rated_tv_shows(self, page: int = 1) -> Optional[List[Dict[str, object]]]:
        """Get top rated TV shows."""
        for provider in self._providers:
            if hasattr(provider, 'get_top_rated_tv_shows'):
                try:
                    return provider.get_top_rated_tv_shows(page)
                except Exception as exc:
                    self._logger(f"Top rated TV shows fetch failed for {provider.name}: {exc}", xbmc.LOGWARNING)
                    continue
        return None
    
    def get_airing_today_tv_shows(self, page: int = 1) -> Optional[List[Dict[str, object]]]:
        """Get TV shows airing today."""
        for provider in self._providers:
            if hasattr(provider, 'get_airing_today_tv_shows'):
                try:
                    return provider.get_airing_today_tv_shows(page)
                except Exception as exc:
                    self._logger(f"Airing today TV shows fetch failed for {provider.name}: {exc}", xbmc.LOGWARNING)
                    continue
        return None
    
    def get_on_the_air_tv_shows(self, page: int = 1) -> Optional[List[Dict[str, object]]]:
        """Get TV shows currently on the air."""
        for provider in self._providers:
            if hasattr(provider, 'get_on_the_air_tv_shows'):
                try:
                    return provider.get_on_the_air_tv_shows(page)
                except Exception as exc:
                    self._logger(f"On the air TV shows fetch failed for {provider.name}: {exc}", xbmc.LOGWARNING)
                    continue
        return None
    
    def get_tv_shows_by_genre(self, genre_id: int, page: int = 1) -> Optional[List[Dict[str, object]]]:
        """Get TV shows by genre."""
        for provider in self._providers:
            if hasattr(provider, 'get_tv_shows_by_genre'):
                try:
                    return provider.get_tv_shows_by_genre(genre_id, page)
                except Exception as exc:
                    self._logger(f"TV shows by genre fetch failed for {provider.name}: {exc}", xbmc.LOGWARNING)
                    continue
        return None
    
    def get_genre_list(self, media_type: str) -> Optional[Dict[int, str]]:
        """Get list of genres with IDs."""
        for provider in self._providers:
            if hasattr(provider, 'get_genre_list'):
                try:
                    return provider.get_genre_list(media_type)
                except Exception as exc:
                    self._logger(f"Genre list fetch failed for {provider.name}: {exc}", xbmc.LOGWARNING)
                    continue
        return None
