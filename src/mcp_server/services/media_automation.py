"""
Media Automation Service for Aura IA MCP

Integrates Sonarr, Radarr, SABnzbd, and Plex for seamless media management.
Ask the MCP to search, download, and manage your media library.

Usage:
    "Download Dune" → Searches Radarr, adds to queue, SABnzbd downloads, Plex updates
    "Get The Bear season 3" → Searches Sonarr, monitors series, downloads new episodes
    "What's downloading?" → Shows SABnzbd queue status
    "Search anime Demon Slayer" → Searches both Sonarr (anime tag) and Radarr

Author: Herman Swanepoel
Created: December 13, 2025

TRACKING MODE (Dec 14, 2025):
    - All searches are logged to PostgreSQL for recommendation learning
    - Downloads are DISABLED unless user explicitly confirms
    - Data retained for 15 days, then auto-cleaned
    - Set MEDIA_TRACKING_ONLY=false to enable downloads
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# TRACKING MODE CONFIGURATION
# ─────────────────────────────────────────────────────────────────────
# Set to False to enable actual downloads to Radarr/Sonarr
TRACKING_ONLY_MODE = os.getenv("MEDIA_TRACKING_ONLY", "true").lower() == "true"
DATA_RETENTION_DAYS = 15

# Database connection for download history
_db_pool = None

async def _get_db_pool():
    """Get or create database connection pool."""
    global _db_pool
    if _db_pool is None:
        try:
            import asyncpg
            db_url = os.getenv("DATABASE_URL", "")
            if not db_url:
                raise ValueError("DATABASE_URL environment variable not set")
            _db_pool = await asyncpg.create_pool(db_url, min_size=1, max_size=5)
        except Exception as e:
            logger.warning(f"Database pool creation failed: {e}")
            _db_pool = None
    return _db_pool

async def log_media_request(
    title: str,
    media_type: str,
    action: str = "search",  # search, request, download, confirm
    tmdb_id: int = None,
    tvdb_id: int = None,
    year: int = None,
    genres: list[str] = None,
    rating: float = None,
    overview: str = None,
    poster_url: str = None,
    source: str = "mcp",
    added_to_library: bool = False
) -> bool:
    """Log a media request to PostgreSQL for recommendation learning.
    
    Actions:
        - search: User searched for this title
        - request: User asked to download (but tracking mode blocked it)
        - download: Actually added to Radarr/Sonarr
        - confirm: User explicitly confirmed download
    """
    try:
        pool = await _get_db_pool()
        if pool is None:
            logger.debug("No database pool, skipping request log")
            return False
        
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO media_downloads 
                (title, media_type, tmdb_id, tvdb_id, year, genres, rating, overview, poster_url, source, added_to_library)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """, title, media_type, tmdb_id, tvdb_id, year, genres or [], rating, overview, poster_url, f"{source}:{action}", added_to_library)
            logger.info(f"📊 Logged {action}: {title} ({media_type})")
            return True
    except Exception as e:
        logger.warning(f"Failed to log request: {e}")
        return False


async def cleanup_old_tracking_data() -> int:
    """Remove tracking data older than DATA_RETENTION_DAYS. Returns count deleted."""
    try:
        pool = await _get_db_pool()
        if pool is None:
            return 0
        
        cutoff = datetime.now() - timedelta(days=DATA_RETENTION_DAYS)
        async with pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM media_downloads 
                WHERE created_at < $1 AND added_to_library = FALSE
            """, cutoff)
            # Extract count from "DELETE X"
            count = int(result.split()[-1]) if result else 0
            if count > 0:
                logger.info(f"🧹 Cleaned up {count} old tracking records (>{DATA_RETENTION_DAYS} days)")
            return count
    except Exception as e:
        logger.warning(f"Failed to cleanup old data: {e}")
        return 0


async def get_tracking_stats() -> dict[str, Any]:
    """Get statistics about tracked media requests."""
    try:
        import asyncpg
        db_url = os.getenv("DATABASE_URL", "")
        if not db_url:
            return {"total_requests": 0, "error": "DATABASE_URL not configured"}
        
        # Use fresh connection to avoid stale pool/event loop issues
        conn = await asyncpg.connect(db_url)
        try:
            # Total requests
            total = await conn.fetchval("SELECT COUNT(*) FROM media_downloads")
            
            # By media type
            by_type = await conn.fetch("""
                SELECT media_type, COUNT(*) as count 
                FROM media_downloads 
                GROUP BY media_type
            """)
            
            # Recent requests (last 7 days)
            recent = await conn.fetch("""
                SELECT title, media_type, source, created_at 
                FROM media_downloads 
                ORDER BY created_at DESC 
                LIMIT 10
            """)
            
            # Top genres
            top_genres = await conn.fetch("""
                SELECT unnest(genres) as genre, COUNT(*) as count 
                FROM media_downloads 
                WHERE genres IS NOT NULL AND array_length(genres, 1) > 0
                GROUP BY genre 
                ORDER BY count DESC 
                LIMIT 5
            """)
            
            return {
                "total_requests": total,
                "by_type": {r["media_type"]: r["count"] for r in by_type},
                "recent": [{"title": r["title"], "media_type": r["media_type"], "source": r["source"], "created_at": str(r["created_at"])} for r in recent],
                "top_genres": [{"genre": r["genre"], "count": r["count"]} for r in top_genres],
                "tracking_mode": TRACKING_ONLY_MODE,
                "retention_days": DATA_RETENTION_DAYS
            }
        finally:
            await conn.close()
    except Exception as e:
        logger.warning(f"Failed to get tracking stats: {e}")
        return {"error": str(e)}
        return {"error": str(e)}


# Alias for backward compatibility
async def log_media_download(
    title: str,
    media_type: str,
    tmdb_id: int = None,
    tvdb_id: int = None,
    year: int = None,
    genres: list[str] = None,
    rating: float = None,
    overview: str = None,
    poster_url: str = None,
    source: str = "mcp"
) -> bool:
    """Backward compatible alias for log_media_request with action=download."""
    return await log_media_request(
        title=title, media_type=media_type, action="download",
        tmdb_id=tmdb_id, tvdb_id=tvdb_id, year=year, genres=genres,
        rating=rating, overview=overview, poster_url=poster_url,
        source=source, added_to_library=True
    )


class MediaType(str, Enum):
    MOVIE = "movie"
    SERIES = "series"
    ANIME = "anime"
    UNKNOWN = "unknown"


@dataclass
class MediaConfig:
    """Configuration for media services.
    
    ARCHITECTURE NOTE:
    ML Backend runs on macvlan network (for Home Assistant access) which cannot
    reach the NAS host directly. Media requests are proxied through the Gateway 
    container which CAN reach the NAS host.
    
    URL Resolution:
    - USE_GATEWAY_PROXY=true (default in container): Routes through Gateway at aura-ia-gateway:9200
    - USE_GATEWAY_PROXY=false: Direct connection (for local development)
    """
    # Gateway proxy for media services (ML Backend → Gateway → NAS host)
    gateway_url: str = "http://aura-ia-gateway:9200"
    use_gateway_proxy: bool = True  # Set via USE_GATEWAY_PROXY env var
    
    # Direct URLs (used when use_gateway_proxy=False or by Gateway itself)
    # Set via SONARR_URL, RADARR_URL, SABNZBD_URL env vars
    sonarr_direct_url: str = ""
    radarr_direct_url: str = ""
    sabnzbd_direct_url: str = ""
    
    # API keys (still needed for direct calls, Gateway has its own from env)
    sonarr_api_key: str = ""
    radarr_api_key: str = ""
    sabnzbd_api_key: str = ""
    
    # Plex (can be reached via macvlan or direct)
    # Set via PLEX_URL env var
    plex_url: str = ""
    plex_token: str = ""
    
    # NAS Media Paths (Herman's NAS - as seen by Radarr/Sonarr containers)
    # These are the paths INSIDE the *arr containers, not host paths
    movie_path: str = "/mnt/library/movies"           # Radarr root folder ID 6
    kids_movie_path: str = "/mnt/library/kids/movies" # Radarr root folder ID 5
    series_path: str = "/mnt/library/tv"              # Sonarr root folder ID 9
    anime_path: str = "/mnt/library/anime"            # Sonarr root folder ID 7
    kids_series_path: str = "/mnt/library/kids/tv"    # Sonarr root folder ID 8
    
    # Quality profiles - Radarr
    # 1=Any, 2=SD, 3=HD-720p, 4=HD-1080p, 5=Ultra-HD, 6=HD-720p/1080p, 7=Remux+WEB 1080p
    radarr_quality_profile_id: int = 6  # HD - 720p/1080p (good default)
    
    # Quality profiles - Sonarr
    # 1=Any, 2=SD, 3=HD-720p, 4=HD-1080p, 5=Ultra-HD, 6=HD-720p/1080p, 7=WEB-1080p, 8=Remux-1080p-Anime
    sonarr_quality_profile_id: int = 6   # HD - 720p/1080p
    anime_quality_profile_id: int = 8    # Remux-1080p - Anime
    
    @property
    def radarr_url(self) -> str:
        """Get Radarr URL - via Gateway proxy or direct."""
        if self.use_gateway_proxy:
            return f"{self.gateway_url}/api/media/radarr"
        return f"{self.radarr_direct_url}/api/v3"
    
    @property
    def sonarr_url(self) -> str:
        """Get Sonarr URL - via Gateway proxy or direct."""
        if self.use_gateway_proxy:
            return f"{self.gateway_url}/api/media/sonarr"
        return f"{self.sonarr_direct_url}/api/v3"
    
    @property
    def sabnzbd_url(self) -> str:
        """Get SABnzbd URL - via Gateway proxy or direct."""
        if self.use_gateway_proxy:
            return f"{self.gateway_url}/api/media/sabnzbd"
        return self.sabnzbd_direct_url


class MediaAutomationService:
    """
    Unified media automation service.
    
    Handles:
    - Searching for movies/series/anime
    - Adding to Sonarr/Radarr
    - Monitoring download progress
    - Plex library updates
    """
    
    def __init__(self, config: Optional[MediaConfig] = None):
        # Determine if we should use Gateway proxy (default: true in container)
        use_proxy = os.getenv("USE_GATEWAY_PROXY", "true").lower() == "true"
        gateway_url = os.getenv("GATEWAY_URL", "http://aura-ia-gateway:9200")
        
        self.config = config or MediaConfig(
            gateway_url=gateway_url,
            use_gateway_proxy=use_proxy,
            sonarr_direct_url=os.getenv("SONARR_URL", ""),
            radarr_direct_url=os.getenv("RADARR_URL", ""),
            sabnzbd_direct_url=os.getenv("SABNZBD_URL", ""),
            plex_url=os.getenv("PLEX_URL", ""),
            sonarr_api_key=os.getenv("SONARR_API_KEY", ""),
            radarr_api_key=os.getenv("RADARR_API_KEY", ""),
            sabnzbd_api_key=os.getenv("SABNZBD_API_KEY", ""),
            plex_token=os.getenv("PLEX_TOKEN", ""),
        )
        
        proxy_status = "via Gateway" if use_proxy else "direct"
        logger.info(f"MediaAutomationService initialized ({proxy_status})")
    
    def _get_client(self) -> httpx.AsyncClient:
        """Create a fresh HTTP client for each request to avoid event loop issues."""
        return httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        """No-op - clients are created per-request now."""
        pass
    
    async def _radarr_get(self, endpoint: str, params: dict = None) -> httpx.Response:
        """Make GET request to Radarr (via proxy or direct)."""
        async with self._get_client() as client:
            if self.config.use_gateway_proxy:
                url = f"{self.config.radarr_url}/{endpoint}"
                return await client.get(url, params=params or {})
            else:
                url = f"{self.config.radarr_direct_url}/api/v3/{endpoint}"
                return await client.get(url, params=params or {}, 
                                        headers={"X-Api-Key": self.config.radarr_api_key})
    
    async def _radarr_post(self, endpoint: str, json_data: dict) -> httpx.Response:
        """Make POST request to Radarr (via proxy or direct)."""
        async with self._get_client() as client:
            if self.config.use_gateway_proxy:
                url = f"{self.config.radarr_url}/{endpoint}"
                return await client.post(url, json=json_data)
            else:
                url = f"{self.config.radarr_direct_url}/api/v3/{endpoint}"
                return await client.post(url, json=json_data,
                                         headers={"X-Api-Key": self.config.radarr_api_key})
    
    async def _sonarr_get(self, endpoint: str, params: dict = None) -> httpx.Response:
        """Make GET request to Sonarr (via proxy or direct)."""
        async with self._get_client() as client:
            if self.config.use_gateway_proxy:
                url = f"{self.config.sonarr_url}/{endpoint}"
                return await client.get(url, params=params or {})
            else:
                url = f"{self.config.sonarr_direct_url}/api/v3/{endpoint}"
                return await client.get(url, params=params or {},
                                        headers={"X-Api-Key": self.config.sonarr_api_key})
    
    async def _sonarr_post(self, endpoint: str, json_data: dict) -> httpx.Response:
        """Make POST request to Sonarr (via proxy or direct)."""
        async with self._get_client() as client:
            if self.config.use_gateway_proxy:
                url = f"{self.config.sonarr_url}/{endpoint}"
                return await client.post(url, json=json_data)
            else:
                url = f"{self.config.sonarr_direct_url}/api/v3/{endpoint}"
                return await client.post(url, json=json_data,
                                         headers={"X-Api-Key": self.config.sonarr_api_key})
    
    async def _sabnzbd_get(self, mode: str, extra_params: dict = None) -> httpx.Response:
        """Make GET request to SABnzbd (via proxy or direct)."""
        params = {"mode": mode, **(extra_params or {})}
        async with self._get_client() as client:
            if self.config.use_gateway_proxy:
                return await client.get(self.config.sabnzbd_url, params=params)
            else:
                params["apikey"] = self.config.sabnzbd_api_key
                params["output"] = "json"
                return await client.get(f"{self.config.sabnzbd_direct_url}/api", params=params)
    
    # ─────────────────────────────────────────────────────────────────────
    # INTENT DETECTION
    # ─────────────────────────────────────────────────────────────────────
    
    def detect_media_type(self, query: str) -> MediaType:
        """Detect if user wants movie, series, or anime."""
        query_lower = query.lower()
        
        # Anime indicators
        anime_keywords = ["anime", "sub", "dub", "japanese", "manga"]
        if any(kw in query_lower for kw in anime_keywords):
            return MediaType.ANIME
        
        # Series indicators
        series_keywords = ["series", "show", "tv", "season", "episode", "episodes"]
        if any(kw in query_lower for kw in series_keywords):
            return MediaType.SERIES
        
        # Movie indicators
        movie_keywords = ["movie", "film", "cinema"]
        if any(kw in query_lower for kw in movie_keywords):
            return MediaType.MOVIE
        
        return MediaType.UNKNOWN
    
    def extract_search_query(self, message: str) -> str:
        """Extract the actual search query from user message."""
        # Remove common prefixes and filler words
        prefixes = [
            r"^(download|get|find|search|add|grab|queue)\s+",
            r"^(can you |please |i want |i need |look for )",
            r"^for\s+",  # Remove leading "for"
            r"(movie|movies|series|show|shows|anime|tv|film)\s+",
            r"\s+(movie|movies|series|show|shows|anime|tv|film)$",
        ]
        
        query = message.strip()
        for prefix in prefixes:
            query = re.sub(prefix, "", query, flags=re.IGNORECASE)
        
        # Clean up any remaining "for" at the start
        query = re.sub(r"^for\s+", "", query, flags=re.IGNORECASE)
        
        return query.strip()
    
    # ─────────────────────────────────────────────────────────────────────
    # RADARR (MOVIES)
    # ─────────────────────────────────────────────────────────────────────
    
    async def search_movie(self, query: str) -> list[dict[str, Any]]:
        """Search for movies in Radarr."""
        # API key check only needed for direct mode
        if not self.config.use_gateway_proxy and not self.config.radarr_api_key:
            return [{"error": "Radarr API key not configured"}]
        
        try:
            response = await self._radarr_get("movie/lookup", {"term": query})
            
            if response.status_code == 200:
                movies = response.json()
                return [
                    {
                        "tmdbId": m.get("tmdbId"),
                        "title": m.get("title"),
                        "year": m.get("year"),
                        "overview": m.get("overview", "")[:200],
                        "rating": m.get("ratings", {}).get("imdb", {}).get("value"),
                        "runtime": m.get("runtime"),
                        "poster": m.get("remotePoster"),
                        "inLibrary": m.get("id") is not None,
                    }
                    for m in movies[:10]  # Limit to 10 results
                ]
            else:
                logger.error(f"Radarr search failed: {response.status_code}")
                return [{"error": f"Radarr returned {response.status_code}"}]
        except Exception as e:
            logger.error(f"Radarr search error: {e}")
            return [{"error": str(e)}]
    
    async def add_movie(
        self,
        tmdb_id: int,
        quality_profile_id: Optional[int] = None,
        search_now: bool = True
    ) -> dict[str, Any]:
        """Add a movie to Radarr and optionally trigger search."""
        if not self.config.use_gateway_proxy and not self.config.radarr_api_key:
            return {"success": False, "error": "Radarr API key not configured"}
        
        try:
            # First, get movie details from lookup
            lookup_response = await self._radarr_get("movie/lookup/tmdb", {"tmdbId": tmdb_id})
            
            if lookup_response.status_code != 200:
                return {"success": False, "error": "Movie not found"}
            
            movie_data = lookup_response.json()
            
            # Check if already in library
            existing = await self._radarr_get("movie")
            
            if existing.status_code == 200:
                for m in existing.json():
                    if m.get("tmdbId") == tmdb_id:
                        return {
                            "success": True,
                            "message": f"'{movie_data.get('title')}' is already in your library!",
                            "already_exists": True,
                            "movie": m
                        }
            
            # Add the movie
            add_payload = {
                "tmdbId": tmdb_id,
                "title": movie_data.get("title"),
                "qualityProfileId": quality_profile_id or self.config.radarr_quality_profile_id,
                "rootFolderPath": self.config.movie_path,
                "monitored": True,
                "addOptions": {
                    "searchForMovie": search_now
                }
            }
            
            add_response = await self._radarr_post("movie", add_payload)
            
            if add_response.status_code in [200, 201]:
                result = add_response.json()
                
                # Log download for recommendation system
                await log_media_download(
                    title=movie_data.get("title", "Unknown"),
                    media_type="movie",
                    tmdb_id=tmdb_id,
                    year=movie_data.get("year"),
                    genres=movie_data.get("genres", []),
                    rating=movie_data.get("ratings", {}).get("tmdb", {}).get("value"),
                    overview=movie_data.get("overview", "")[:500],
                    poster_url=movie_data.get("remotePoster"),
                    source="radarr"
                )
                
                return {
                    "success": True,
                    "message": f"✅ Added '{movie_data.get('title')}' ({movie_data.get('year')}) to Radarr!",
                    "searching": search_now,
                    "movie": {
                        "id": result.get("id"),
                        "title": result.get("title"),
                        "year": result.get("year"),
                    }
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to add movie: {add_response.text}"
                }
        except Exception as e:
            logger.error(f"Add movie error: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_radarr_queue(self) -> list[dict[str, Any]]:
        """Get current Radarr download queue."""
        if not self.config.use_gateway_proxy and not self.config.radarr_api_key:
            return []
        
        try:
            response = await self._radarr_get("queue")
            
            if response.status_code == 200:
                data = response.json()
                return [
                    {
                        "title": item.get("title"),
                        "status": item.get("status"),
                        "progress": round(100 - (item.get("sizeleft", 0) / max(item.get("size", 1), 1) * 100), 1),
                        "eta": item.get("timeleft"),
                        "quality": item.get("quality", {}).get("quality", {}).get("name"),
                    }
                    for item in data.get("records", [])
                ]
            return []
        except Exception as e:
            logger.error(f"Radarr queue error: {e}")
            return []
    
    # ─────────────────────────────────────────────────────────────────────
    # SONARR (TV SERIES)
    # ─────────────────────────────────────────────────────────────────────
    
    async def search_series(self, query: str) -> list[dict[str, Any]]:
        """Search for TV series in Sonarr."""
        if not self.config.use_gateway_proxy and not self.config.sonarr_api_key:
            return [{"error": "Sonarr API key not configured"}]
        
        try:
            response = await self._sonarr_get("series/lookup", {"term": query})
            
            if response.status_code == 200:
                series_list = response.json()
                return [
                    {
                        "tvdbId": s.get("tvdbId"),
                        "title": s.get("title"),
                        "year": s.get("year"),
                        "overview": s.get("overview", "")[:200],
                        "rating": s.get("ratings", {}).get("value"),
                        "seasons": s.get("seasonCount"),
                        "network": s.get("network"),
                        "status": s.get("status"),
                        "poster": s.get("remotePoster"),
                        "inLibrary": s.get("id") is not None,
                    }
                    for s in series_list[:10]
                ]
            else:
                return [{"error": f"Sonarr returned {response.status_code}"}]
        except Exception as e:
            logger.error(f"Sonarr search error: {e}")
            return [{"error": str(e)}]
    
    async def add_series(
        self,
        tvdb_id: int,
        quality_profile_id: Optional[int] = None,
        is_anime: bool = False,
        search_now: bool = True
    ) -> dict[str, Any]:
        """Add a TV series to Sonarr."""
        if not self.config.use_gateway_proxy and not self.config.sonarr_api_key:
            return {"success": False, "error": "Sonarr API key not configured"}
        
        try:
            # Get series details
            lookup_response = await self._sonarr_get("series/lookup", {"term": f"tvdb:{tvdb_id}"})
            
            if lookup_response.status_code != 200 or not lookup_response.json():
                return {"success": False, "error": "Series not found"}
            
            series_data = lookup_response.json()[0]
            
            # Check if already exists
            existing = await self._sonarr_get("series")
            
            if existing.status_code == 200:
                for s in existing.json():
                    if s.get("tvdbId") == tvdb_id:
                        return {
                            "success": True,
                            "message": f"'{series_data.get('title')}' is already in your library!",
                            "already_exists": True,
                            "series": s
                        }
                
                # Determine root folder and quality profile
                root_folder = self.config.anime_path if is_anime else self.config.series_path
                quality_id = quality_profile_id or (
                    self.config.anime_quality_profile_id if is_anime 
                    else self.config.sonarr_quality_profile_id
                )
                
            # Add the series
            add_payload = {
                "tvdbId": tvdb_id,
                "title": series_data.get("title"),
                "qualityProfileId": quality_id,
                "rootFolderPath": root_folder,
                "monitored": True,
                "seasonFolder": True,
                "seriesType": "anime" if is_anime else "standard",
                "addOptions": {
                    "searchForMissingEpisodes": search_now,
                    "searchForCutoffUnmetEpisodes": False
                }
            }
            
            add_response = await self._sonarr_post("series", add_payload)
                
            if add_response.status_code in [200, 201]:
                result = add_response.json()
                
                # Log download for recommendation system
                await log_media_download(
                    title=series_data.get("title", "Unknown"),
                    media_type="anime" if is_anime else "series",
                    tvdb_id=tvdb_id,
                    year=series_data.get("year"),
                    genres=series_data.get("genres", []),
                    rating=series_data.get("ratings", {}).get("value"),
                    overview=series_data.get("overview", "")[:500],
                    poster_url=series_data.get("remotePoster"),
                    source="sonarr"
                )
                
                return {
                    "success": True,
                    "message": f"✅ Added '{series_data.get('title')}' to Sonarr!",
                    "searching": search_now,
                    "series": {
                        "id": result.get("id"),
                        "title": result.get("title"),
                        "seasons": result.get("seasonCount"),
                    }
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to add series: {add_response.text}"
                }
        except Exception as e:
            logger.error(f"Add series error: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_sonarr_queue(self) -> list[dict[str, Any]]:
        """Get current Sonarr download queue."""
        if not self.config.use_gateway_proxy and not self.config.sonarr_api_key:
            return []
        
        try:
            response = await self._sonarr_get("queue")
            
            if response.status_code == 200:
                data = response.json()
                return [
                    {
                        "series": item.get("series", {}).get("title"),
                        "episode": f"S{item.get('episode', {}).get('seasonNumber', 0):02d}E{item.get('episode', {}).get('episodeNumber', 0):02d}",
                        "title": item.get("episode", {}).get("title"),
                        "status": item.get("status"),
                        "progress": round(100 - (item.get("sizeleft", 0) / max(item.get("size", 1), 1) * 100), 1),
                        "eta": item.get("timeleft"),
                    }
                    for item in data.get("records", [])
                ]
            return []
        except Exception as e:
            logger.error(f"Sonarr queue error: {e}")
            return []
    
    # ─────────────────────────────────────────────────────────────────────
    # SABNZBD (DOWNLOADER)
    # ─────────────────────────────────────────────────────────────────────
    
    async def get_download_queue(self) -> dict[str, Any]:
        """Get SABnzbd download queue status."""
        if not self.config.use_gateway_proxy and not self.config.sabnzbd_api_key:
            return {"error": "SABnzbd API key not configured"}
        
        try:
            response = await self._sabnzbd_get("queue")
            
            if response.status_code == 200:
                data = response.json().get("queue", {})
                return {
                    "status": data.get("status"),
                    "speed": data.get("speed"),
                    "timeleft": data.get("timeleft"),
                    "mb_left": data.get("mbleft"),
                    "downloads": [
                        {
                            "name": slot.get("filename"),
                            "progress": float(slot.get("percentage", 0)),
                            "size": slot.get("size"),
                            "timeleft": slot.get("timeleft"),
                            "status": slot.get("status"),
                        }
                        for slot in data.get("slots", [])
                    ]
                }
            return {"error": f"SABnzbd returned {response.status_code}"}
        except Exception as e:
            logger.error(f"SABnzbd queue error: {e}")
            return {"error": str(e)}
    
    async def get_download_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent download history from SABnzbd."""
        if not self.config.use_gateway_proxy and not self.config.sabnzbd_api_key:
            return []
        
        try:
            response = await self._sabnzbd_get("history", {"limit": limit})
            
            if response.status_code == 200:
                data = response.json().get("history", {})
                return [
                    {
                        "name": slot.get("name"),
                        "status": slot.get("status"),
                        "size": slot.get("size"),
                        "completed": slot.get("completed"),
                        "category": slot.get("category"),
                    }
                    for slot in data.get("slots", [])
                ]
            return []
        except Exception as e:
            logger.error(f"SABnzbd history error: {e}")
            return []
    
    # ─────────────────────────────────────────────────────────────────────
    # PLEX
    # ─────────────────────────────────────────────────────────────────────
    
    async def refresh_plex_library(self, library_id: Optional[int] = None) -> dict[str, Any]:
        """Trigger Plex library scan."""
        if not self.config.plex_token:
            return {"success": False, "error": "Plex token not configured"}
        
        try:
            async with self._get_client() as client:
                if library_id:
                    url = f"{self.config.plex_url}/library/sections/{library_id}/refresh"
                else:
                    url = f"{self.config.plex_url}/library/sections/all/refresh"
                
                response = await client.get(
                    url,
                    params={"X-Plex-Token": self.config.plex_token}
                )
                
                return {
                    "success": response.status_code in [200, 204],
                    "message": "Plex library scan triggered" if response.status_code in [200, 204] else f"Failed: {response.status_code}"
                }
        except Exception as e:
            logger.error(f"Plex refresh error: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_plex_recently_added(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recently added items from Plex."""
        if not self.config.plex_token:
            return []
        
        try:
            async with self._get_client() as client:
                response = await client.get(
                    f"{self.config.plex_url}/library/recentlyAdded",
                    params={
                        "X-Plex-Token": self.config.plex_token,
                        "X-Plex-Container-Size": limit
                    },
                    headers={"Accept": "application/json"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get("MediaContainer", {}).get("Metadata", [])
                    return [
                        {
                            "title": item.get("title"),
                            "type": item.get("type"),
                            "year": item.get("year"),
                            "added_at": item.get("addedAt"),
                            "grandparent_title": item.get("grandparentTitle"),  # For episodes
                        }
                        for item in items
                    ]
                return []
        except Exception as e:
            logger.error(f"Plex recently added error: {e}")
            return []
    
    # ─────────────────────────────────────────────────────────────────────
    # UNIFIED INTERFACE
    # ─────────────────────────────────────────────────────────────────────
    
    async def smart_search(self, query: str, log_search: bool = True) -> dict[str, Any]:
        """
        Smart search that detects media type and searches appropriate service.
        
        Returns combined results from Radarr and/or Sonarr.
        Logs search to PostgreSQL for recommendation learning.
        """
        media_type = self.detect_media_type(query)
        search_query = self.extract_search_query(query)
        
        results = {
            "query": search_query,
            "detected_type": media_type.value,
            "movies": [],
            "series": [],
            "tracking_mode": TRACKING_ONLY_MODE
        }
        
        # Search based on detected type
        if media_type in [MediaType.MOVIE, MediaType.UNKNOWN]:
            results["movies"] = await self.search_movie(search_query)
        
        if media_type in [MediaType.SERIES, MediaType.ANIME, MediaType.UNKNOWN]:
            results["series"] = await self.search_series(search_query)
        
        # Log the search for learning (best match only)
        if log_search and TRACKING_ONLY_MODE:
            best = None
            best_type = None
            if results["movies"] and "error" not in results["movies"][0]:
                best = results["movies"][0]
                best_type = "movie"
            elif results["series"] and "error" not in results["series"][0]:
                best = results["series"][0]
                best_type = "anime" if media_type == MediaType.ANIME else "series"
            
            if best:
                await log_media_request(
                    title=best.get("title", search_query),
                    media_type=best_type,
                    action="search",
                    tmdb_id=best.get("tmdbId"),
                    tvdb_id=best.get("tvdbId"),
                    year=best.get("year"),
                    genres=best.get("genres", []),
                    rating=best.get("rating"),
                    overview=best.get("overview", ""),
                    poster_url=best.get("poster"),
                    source="mcp",
                    added_to_library=False
                )
        
        return results
    
    async def smart_add(
        self,
        query: str,
        auto_select: bool = True,
        force_download: bool = False  # Must be True to bypass tracking mode
    ) -> dict[str, Any]:
        """
        Smart add that searches and adds the best match.
        
        TRACKING MODE (default):
            - Logs the request to PostgreSQL for learning
            - Does NOT add to Radarr/Sonarr
            - Returns search results for user to confirm
        
        To actually download, user must explicitly confirm with force_download=True
        or set MEDIA_TRACKING_ONLY=false environment variable.
        """
        search_results = await self.smart_search(query)
        media_type = self.detect_media_type(query)
        is_anime = media_type == MediaType.ANIME
        
        # Determine best match for logging
        best_match = None
        match_type = None
        
        if search_results["movies"] and media_type in [MediaType.MOVIE, MediaType.UNKNOWN]:
            best_movie = search_results["movies"][0]
            if "error" not in best_movie:
                best_match = best_movie
                match_type = "movie"
        
        if not best_match and search_results["series"] and media_type in [MediaType.SERIES, MediaType.ANIME, MediaType.UNKNOWN]:
            best_series = search_results["series"][0]
            if "error" not in best_series:
                best_match = best_series
                match_type = "anime" if is_anime else "series"
        
        # TRACKING MODE: Log request but don't download
        if TRACKING_ONLY_MODE and not force_download:
            if best_match:
                # Log the request for learning
                await log_media_request(
                    title=best_match.get("title", query),
                    media_type=match_type,
                    action="request",
                    tmdb_id=best_match.get("tmdbId"),
                    tvdb_id=best_match.get("tvdbId"),
                    year=best_match.get("year"),
                    genres=best_match.get("genres", []),
                    rating=best_match.get("rating"),
                    overview=best_match.get("overview", ""),
                    poster_url=best_match.get("poster"),
                    source="mcp",
                    added_to_library=False
                )
                
                return {
                    "success": True,
                    "tracking_mode": True,
                    "message": f"📊 **Tracked:** {best_match.get('title')} ({best_match.get('year', 'N/A')})\n\n"
                               f"⚠️ **Tracking Mode Active** - Downloads disabled for 15 days.\n"
                               f"Say \"confirm download {best_match.get('title')}\" to actually add it.",
                    "best_match": best_match,
                    "type": match_type,
                    "search_results": search_results,
                    "requires_confirmation": True
                }
            else:
                return {
                    "success": False,
                    "tracking_mode": True,
                    "message": "No results found to track.",
                    "search_results": search_results
                }
        
        # DOWNLOAD MODE: Actually add to Radarr/Sonarr
        if match_type == "movie" and auto_select:
            result = await self.add_movie(best_match["tmdbId"])
            result["type"] = "movie"
            result["search_results"] = search_results
            return result
        
        if match_type in ["series", "anime"] and auto_select:
            result = await self.add_series(best_match["tvdbId"], is_anime=is_anime)
            result["type"] = match_type
            result["search_results"] = search_results
            return result
        
        # No auto-add, return search results for user selection
        return {
            "success": False,
            "message": "Found results but need confirmation. Which would you like to add?",
            "search_results": search_results,
            "requires_selection": True
        }
    
    async def confirm_download(self, query: str) -> dict[str, Any]:
        """
        Explicitly confirm and execute a download request.
        Bypasses tracking mode for this specific request.
        """
        logger.info(f"📥 Confirmed download request: {query}")
        return await self.smart_add(query, auto_select=True, force_download=True)
    
    async def get_all_queues(self) -> dict[str, Any]:
        """Get combined download status from all services."""
        sabnzbd_queue, radarr_queue, sonarr_queue = await asyncio.gather(
            self.get_download_queue(),
            self.get_radarr_queue(),
            self.get_sonarr_queue(),
            return_exceptions=True
        )
        
        return {
            "timestamp": datetime.now().isoformat(),
            "sabnzbd": sabnzbd_queue if not isinstance(sabnzbd_queue, Exception) else {"error": str(sabnzbd_queue)},
            "radarr_queue": radarr_queue if not isinstance(radarr_queue, Exception) else [],
            "sonarr_queue": sonarr_queue if not isinstance(sonarr_queue, Exception) else [],
            "total_downloading": (
                len(sabnzbd_queue.get("downloads", []) if isinstance(sabnzbd_queue, dict) else []) +
                len(radarr_queue if isinstance(radarr_queue, list) else []) +
                len(sonarr_queue if isinstance(sonarr_queue, list) else [])
            )
        }
    
    async def get_status_summary(self) -> str:
        """Get a human-readable status summary."""
        queues = await self.get_all_queues()
        
        lines = ["📺 **Media Status**\n"]
        
        # SABnzbd status
        sab = queues.get("sabnzbd", {})
        if isinstance(sab, dict) and "error" not in sab:
            if sab.get("downloads"):
                lines.append(f"⬇️ **Downloading:** {len(sab['downloads'])} items")
                lines.append(f"   Speed: {sab.get('speed', 'N/A')} | ETA: {sab.get('timeleft', 'N/A')}")
                for dl in sab["downloads"][:3]:
                    lines.append(f"   • {dl['name'][:40]}... ({dl['progress']:.0f}%)")
            else:
                lines.append("⬇️ **Downloads:** Queue empty")
        
        # Radarr queue
        radarr = queues.get("radarr_queue", [])
        if radarr:
            lines.append(f"\n🎬 **Movies in queue:** {len(radarr)}")
            for m in radarr[:3]:
                lines.append(f"   • {m['title']} ({m['progress']:.0f}%)")
        
        # Sonarr queue
        sonarr = queues.get("sonarr_queue", [])
        if sonarr:
            lines.append(f"\n📺 **Episodes in queue:** {len(sonarr)}")
            for s in sonarr[:3]:
                lines.append(f"   • {s['series']} {s['episode']} ({s['progress']:.0f}%)")
        
        if not radarr and not sonarr and not sab.get("downloads"):
            lines.append("\n✨ All queues are empty!")
        
        return "\n".join(lines)


# Global singleton
_media_service: Optional[MediaAutomationService] = None


def get_media_service() -> MediaAutomationService:
    """Get or create the media automation service."""
    global _media_service
    if _media_service is None:
        _media_service = MediaAutomationService()
    return _media_service
