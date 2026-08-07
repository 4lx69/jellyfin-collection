"""MDBList API client."""

import re
from typing import Any, Optional

from loguru import logger

from jfc.clients.base import BaseClient
from jfc.models.media import MediaItem, MediaType, Movie, Series


class MDBListClient(BaseClient):
    """Client for MDBList API."""

    BASE_URL = "https://api.mdblist.com"
    LIST_URL_RE = re.compile(
        r"(?:https?://)?(?:www\.)?mdblist\.com/lists/(?P<user>[^/]+)/(?P<slug>[^/?#]+)",
        re.IGNORECASE,
    )

    def __init__(self, api_key: str):
        """
        Initialize MDBList client.

        Args:
            api_key: MDBList API key
        """
        super().__init__(base_url=self.BASE_URL)
        self.api_key = api_key

    def _params(self, **kwargs: Any) -> dict[str, Any]:
        """Build request params with API key."""
        params: dict[str, Any] = {"apikey": self.api_key}
        for key, value in kwargs.items():
            if value is not None:
                params[key] = value
        return params

    def _log_items(
        self,
        source: str,
        items: list[MediaItem],
        params: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log fetched items with their IDs and titles."""
        if params:
            filtered = {k: v for k, v in params.items() if k != "apikey"}
            logger.info(f"[MDBList] {source}: params={filtered}")

        logger.info(f"[MDBList] {source}: fetched {len(items)} items")
        for item in items:
            year_str = f" ({item.year})" if item.year else ""
            tmdb_str = f"tmdb:{item.tmdb_id}" if item.tmdb_id else "no-tmdb"
            imdb_str = f"imdb:{item.imdb_id}" if item.imdb_id else ""
            ids = ", ".join(filter(None, [tmdb_str, imdb_str]))
            logger.debug(f"  - [{ids}] {item.title}{year_str}")

    # =========================================================================
    # Connection
    # =========================================================================

    async def test_connection(self) -> bool:
        """Verify API key via GET /user."""
        response = await self.get("/user", params=self._params())
        response.raise_for_status()
        return True

    # =========================================================================
    # Lists
    # =========================================================================

    async def get_list_items(
        self,
        *,
        username: Optional[str] = None,
        listname: Optional[str] = None,
        list_id: Optional[int] = None,
        media_type: Optional[MediaType] = None,
        limit: Optional[int] = None,
        sort_by: Optional[str] = None,
    ) -> list[MediaItem]:
        """
        Fetch items from an MDBList list with cursor pagination.

        Args:
            username: List owner username
            listname: List slug
            list_id: Numeric list ID (alternative to username/listname)
            media_type: Optional movie/show filter
            limit: Max items to return
            sort_by: Kometa-style sort (e.g. imdbrating.desc)

        Returns:
            List of media items
        """
        if list_id is not None:
            endpoint = f"/lists/{list_id}/items"
            source = f"List {list_id}"
        elif username and listname:
            endpoint = f"/lists/{username}/{listname}/items"
            source = f"List {username}/{listname}"
        else:
            logger.warning("[MDBList] Missing list id or username/listname")
            return []

        all_items: list[MediaItem] = []
        cursor: Optional[str] = None
        max_items = int(limit) if limit else None
        page_limit = min(max_items or 100, 1000)
        sort_field, sort_order = self._parse_sort_by(sort_by)
        params: dict[str, Any] = {}

        while True:
            params = self._params(
                limit=page_limit,
                cursor=cursor,
                sort=sort_field,
                order=sort_order,
                mediatype=self._mediatype_param(media_type),
            )
            response = await self.get(endpoint, params=params)

            if response.status_code == 404:
                logger.warning(f"[MDBList] List not found: {source}")
                return []

            response.raise_for_status()
            data = response.json()
            page_items = self._parse_items_response(data, media_type)

            for item in page_items:
                all_items.append(item)
                if max_items and len(all_items) >= max_items:
                    self._log_items(source, all_items, params)
                    return all_items

            cursor = self._next_cursor(data, response.headers)
            if not cursor or not page_items:
                break

        self._log_items(source, all_items, params)
        return all_items

    def parse_list_ref(self, value: str) -> dict[str, Any]:
        """
        Parse list URL, user/slug, or numeric id.

        Returns:
            Dict with either list_id or username+listname
        """
        raw = value.strip()
        if raw.isdigit():
            return {"list_id": int(raw)}

        match = self.LIST_URL_RE.search(raw)
        if match:
            return {
                "username": match.group("user"),
                "listname": match.group("slug").rstrip("/"),
            }

        if "/" in raw and "://" not in raw:
            user, slug = raw.split("/", 1)
            if user and slug:
                return {"username": user, "listname": slug.strip("/")}

        logger.warning(f"[MDBList] Invalid list reference '{value}'")
        return {}

    def _parse_sort_by(
        self, sort_by: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Split Kometa sort_by (field.direction) into API sort/order params."""
        if not sort_by:
            return None, None

        raw = str(sort_by).strip()
        if not raw:
            return None, None

        if "." in raw:
            sort_field, order = raw.rsplit(".", 1)
            if order.lower() in {"asc", "desc"}:
                return sort_field, order.lower()

        return raw, None

    def _mediatype_param(self, media_type: Optional[MediaType]) -> Optional[str]:
        if media_type == MediaType.MOVIE:
            return "movie"
        if media_type == MediaType.SERIES:
            return "show"
        return None

    def _next_cursor(self, data: dict[str, Any], headers: Any) -> Optional[str]:
        """Extract next pagination cursor from body or headers."""
        pagination = data.get("pagination") or {}
        cursor = pagination.get("next_cursor") or data.get("next_cursor")
        if cursor:
            return str(cursor)

        header_cursor = None
        if headers is not None:
            header_cursor = headers.get("X-Next-Cursor") or headers.get("x-next-cursor")
        return str(header_cursor) if header_cursor else None

    def _parse_items_response(
        self,
        data: dict[str, Any],
        media_type: Optional[MediaType],
    ) -> list[MediaItem]:
        items: list[MediaItem] = []

        if media_type is None or media_type == MediaType.MOVIE:
            for row in data.get("movies") or []:
                parsed = self._parse_item(row, MediaType.MOVIE)
                if parsed:
                    items.append(parsed)

        if media_type is None or media_type == MediaType.SERIES:
            for row in data.get("shows") or []:
                parsed = self._parse_item(row, MediaType.SERIES)
                if parsed:
                    items.append(parsed)

        return items

    def _parse_item(
        self,
        data: dict[str, Any],
        media_type: MediaType,
    ) -> Optional[MediaItem]:
        """Parse a list item. Never treat top-level id as TMDb id."""
        ids = data.get("ids") or {}
        tmdb_id = ids.get("tmdb") if isinstance(ids, dict) else None
        if tmdb_id is None:
            tmdb_id = data.get("tmdb_id")

        imdb_id = None
        if isinstance(ids, dict):
            imdb_id = ids.get("imdb")
        imdb_id = imdb_id or data.get("imdb_id")

        tvdb_id = None
        if isinstance(ids, dict):
            tvdb_id = ids.get("tvdb")
        tvdb_id = tvdb_id if tvdb_id is not None else data.get("tvdb_id")

        title = data.get("title") or "Unknown"
        year = data.get("release_year")

        if media_type == MediaType.MOVIE:
            return Movie(
                title=title,
                year=year,
                tmdb_id=tmdb_id,
                imdb_id=imdb_id,
                tvdb_id=tvdb_id,
            )
        return Series(
            title=title,
            year=year,
            tmdb_id=tmdb_id,
            imdb_id=imdb_id,
            tvdb_id=tvdb_id,
        )
