"""YouTube Data API v3 Client with Quota Tracking and Batching."""

import logging
from typing import Dict, List, Optional
import requests

from src.config import YOUTUBE_API_KEY

logger = logging.getLogger("yt_client")

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"

# Quota costs as defined by Google YouTube Data API v3
QUOTA_COSTS = {
    "search": 100,
    "videos": 1,
    "channels": 1,
    "playlistItems": 1,
}


class YouTubeAPIError(Exception):
    """Custom exception for YouTube API errors."""
    pass


class YouTubeClient:
    """Client for querying the YouTube Data API v3."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or YOUTUBE_API_KEY
        if not self.api_key or self.api_key == "your_youtube_data_api_key_here":
            raise ValueError(
                "Missing valid YOUTUBE_API_KEY. Please set YOUTUBE_API_KEY in .env"
            )
        self.session = requests.Session()
        self.total_quota_used = 0

    def _get(self, endpoint: str, params: dict, cost: int = 1) -> dict:
        """Execute a GET request against the YouTube Data API."""
        url = f"{YOUTUBE_API_BASE}/{endpoint}"
        query_params = {"key": self.api_key, **params}

        try:
            resp = self.session.get(url, params=query_params, timeout=15)
            self.total_quota_used += cost
            if resp.status_code != 200:
                try:
                    error_json = resp.json().get("error", {})
                    msg = error_json.get("message", resp.text)
                    code = error_json.get("code", resp.status_code)
                    errors = error_json.get("errors", [])
                    reasons = [e.get("reason") for e in errors]
                    raise YouTubeAPIError(f"HTTP {code} error: {msg} (reasons: {reasons})")
                except ValueError:
                    raise YouTubeAPIError(f"HTTP {resp.status_code} error: {resp.text}")
            return resp.json()
        except requests.RequestException as e:
            raise YouTubeAPIError(f"Network request failed: {e}")

    def test_connection(self) -> bool:
        """Quick 1-unit quota test call to verify API key validity."""
        # Query YouTube channel ID for Google (UC_x5XG1OV2P6uZZ5FSM9Ttw)
        data = self._get("channels", {"part": "id", "id": "UC_x5XG1OV2P6uZZ5FSM9Ttw"}, cost=QUOTA_COSTS["channels"])
        return len(data.get("items", [])) > 0

    def get_videos(self, video_ids: List[str]) -> List[dict]:
        """Fetch details for a batch of video IDs (up to 50 per call). Cost: 1 quota unit."""
        if not video_ids:
            return []
        
        results = []
        # Chunk into groups of 50
        for i in range(0, len(video_ids), 50):
            chunk = video_ids[i:i + 50]
            params = {
                "part": "snippet,statistics,contentDetails",
                "id": ",".join(chunk)
            }
            data = self._get("videos", params, cost=QUOTA_COSTS["videos"])
            results.extend(data.get("items", []))
        return results

    def get_channels_by_id(self, channel_ids: List[str]) -> List[dict]:
        """Fetch details for a batch of channel IDs (up to 50 per call). Cost: 1 quota unit."""
        if not channel_ids:
            return []
        
        results = []
        for i in range(0, len(channel_ids), 50):
            chunk = channel_ids[i:i + 50]
            params = {
                "part": "snippet,statistics,brandingSettings",
                "id": ",".join(chunk)
            }
            data = self._get("channels", params, cost=QUOTA_COSTS["channels"])
            results.extend(data.get("items", []))
        return results

    def get_channel_by_handle(self, handle: str) -> Optional[dict]:
        """Fetch a single channel by its handle (e.g. @bytebytego). Cost: 1 quota unit."""
        clean_handle = handle if handle.startswith("@") else f"@{handle}"
        params = {
            "part": "snippet,statistics,brandingSettings",
            "forHandle": clean_handle
        }
        data = self._get("channels", params, cost=QUOTA_COSTS["channels"])
        items = data.get("items", [])
        return items[0] if items else None

    def search(
        self,
        query: str,
        max_results: int = 50,
        type_: str = "video",
        order: str = "relevance",
        published_after: Optional[str] = None
    ) -> List[dict]:
        """Search YouTube for videos or channels. Cost: 100 quota units."""
        params = {
            "part": "snippet",
            "q": query,
            "maxResults": min(max_results, 50),
            "type": type_,
            "order": order
        }
        if published_after:
            params["publishedAfter"] = published_after
            
        data = self._get("search", params, cost=QUOTA_COSTS["search"])
        return data.get("items", [])
