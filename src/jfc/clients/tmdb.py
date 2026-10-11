"""TMDb (The Movie Database) API client."""

from datetime import date
from typing import Any, Callable, Optional

from loguru import logger

from jfc.clients.base import BaseClient
from jfc.models.media import MediaItem, MediaType, Movie, Series


class TMDbClient(BaseClient):
    """Client for TMDb API v3."""

    BASE_URL = "https://api.themoviedb.org/3"

    def __init__(self, api_key: str, language: str = "fr", region: str = "FR"):
        """
        Initialize TMDb client.

        Args:
            api_key: TMDb API key
            language: Language for results
            region: Region for watch providers
        """
        super().__init__(base_url=self.BASE_URL)
        self.api_key = api_key
        self.language = language
        self.region = region

    def _params(self, **kwargs) -> dict[str, Any]:
        """Build request params with API key and language."""
        params = {
            "api_key": self.api_key,
            "language": self.language,
        }
        params.update(kwargs)
        return params

    def _log_items(
        self,
        source: str,
        items: list[MediaItem],
        params: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log fetched items with their IDs and titles."""
        # Log the API call parameters (excluding api_key for security)
        if params:
            filtered_params = {k: v for k, v in params.items() if k != "api_key"}
            logger.info(f"[TMDb] {source}: params={filtered_params}")

        logger.info(f"[TMDb] {source}: fetched {len(items)} items")
        for item in items:
            year_str = f" ({item.year})" if item.year else ""
            logger.debug(f"  - [tmdb:{item.tmdb_id}] {item.title}{year_str}")

    async def _fetch_paginated_results(
        self,
        endpoint: str,
        limit: int,
        parser: Callable[[dict[str, Any]], MediaItem],
        params: Optional[dict[str, Any]] = None,
    ) -> list[MediaItem]:
        """Fetch paginated TMDb endpoint results up to limit."""
        all_results: list[MediaItem] = []
        page = 1
        base_params = params.copy() if params else {}

        while len(all_results) < limit:
            request_params = self._params(page=page, **base_params)
            response = await self.get(endpoint, params=request_params)
            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])
            total_pages = data.get("total_pages", 1)

            for item in results:
                if len(all_results) >= limit:
                    break
                all_results.append(parser(item))

            if page >= total_pages or not results:
                break
            page += 1

        return all_results

    # =========================================================================
    # Trending
    # =========================================================================

    async def get_trending_movies(
        self,
        time_window: str = "week",
        limit: int = 20,
    ) -> list[Movie]:
        """
        Get trending movies.

        Args:
            time_window: 'day' or 'week'
            limit: Maximum results

        Returns:
            List of trending movies
        """
        params: dict[str, Any] = {}
        movies = await self._fetch_paginated_results(
            endpoint=f"/trending/movie/{time_window}",
            limit=limit,
            parser=self._parse_movie,
            params=params,
        )

        self._log_items(f"Trending Movies ({time_window})", movies, self._params(**params))
        return movies

    async def get_trending_series(
        self,
        time_window: str = "week",
        limit: int = 20,
    ) -> list[Series]:
        """
        Get trending TV series.

        Args:
            time_window: 'day' or 'week'
            limit: Maximum results

        Returns:
            List of trending series
        """
        params: dict[str, Any] = {}
        series = await self._fetch_paginated_results(
            endpoint=f"/trending/tv/{time_window}",
            limit=limit,
            parser=self._parse_series,
            params=params,
        )

        self._log_items(f"Trending Series ({time_window})", series, self._params(**params))
        return series

    # =========================================================================
    # Popular
    # =========================================================================

    async def get_popular_movies(self, limit: int = 20) -> list[Movie]:
        """Get popular movies."""
        params: dict[str, Any] = {}
        movies = await self._fetch_paginated_results(
            endpoint="/movie/popular",
            limit=limit,
            parser=self._parse_movie,
            params=params,
        )

        self._log_items("Popular Movies", movies, self._params(**params))
        return movies

    async def get_popular_series(self, limit: int = 20) -> list[Series]:
        """Get popular TV series."""
        params: dict[str, Any] = {}
        series = await self._fetch_paginated_results(
            endpoint="/tv/popular",
            limit=limit,
            parser=self._parse_series,
            params=params,
        )

        self._log_items("Popular Series", series, self._params(**params))
        return series

    async def get_now_playing_movies(self, limit: int = 20) -> list[Movie]:
        """Get movies currently in theaters (uses configured region)."""
        params: dict[str, Any] = {}
        movies = await self._fetch_paginated_results(
            endpoint="/movie/now_playing",
            limit=limit,
            parser=self._parse_movie,
            params=params,
        )

        self._log_items("Now Playing Movies", movies, self._params(**params))
        return movies

    async def get_airing_today_series(self, limit: int = 20) -> list[Series]:
        """Get TV series with an episode airing today."""
        params: dict[str, Any] = {}
        series = await self._fetch_paginated_results(
            endpoint="/tv/airing_today",
            limit=limit,
            parser=self._parse_series,
            params=params,
        )

        self._log_items("Airing Today Series", series, self._params(**params))
        return series

    async def get_on_the_air_series(self, limit: int = 20) -> list[Series]:
        """Get TV series with an episode airing in the next 7 days."""
        params: dict[str, Any] = {}
        series = await self._fetch_paginated_results(
            endpoint="/tv/on_the_air",
            limit=limit,
            parser=self._parse_series,
            params=params,
        )

        self._log_items("On The Air Series", series, self._params(**params))
        return series

    # =========================================================================
    # Discover
    # =========================================================================

    async def discover_movies(
        self,
        sort_by: str = "popularity.desc",
        with_genres: Optional[list[int]] = None,
        without_genres: Optional[list[int]] = None,
        vote_average_gte: Optional[float] = None,
        vote_average_lte: Optional[float] = None,
        vote_count_gte: Optional[int] = None,
        vote_count_lte: Optional[int] = None,
        primary_release_date_gte: Optional[date] = None,
        primary_release_date_lte: Optional[date] = None,
        with_watch_providers: Optional[list[int]] = None,
        watch_region: Optional[str] = None,
        with_watch_monetization_types: str = "flatrate",
        with_original_language: Optional[str] = None,
        with_release_type: Optional[str] = None,
        region: Optional[str] = None,
        limit: int = 20,
    ) -> list[Movie]:
        """
        Discover movies with filters.

        Args:
            sort_by: Sort order
            with_genres: Include genres (comma-separated IDs)
            without_genres: Exclude genres
            vote_average_gte: Minimum vote average
            vote_average_lte: Maximum vote average
            vote_count_gte: Minimum vote count
            vote_count_lte: Maximum vote count
            primary_release_date_gte: Released after date
            primary_release_date_lte: Released before date
            with_watch_providers: Watch provider IDs (OR with |)
            watch_region: Region for watch providers
            with_watch_monetization_types: flatrate, rent, buy, free
            with_original_language: Original language code
            with_release_type: Release type filter
            region: Region for release dates
            limit: Maximum results

        Returns:
            List of discovered movies
        """
        params = self._params(sort_by=sort_by)

        if with_genres:
            params["with_genres"] = ",".join(map(str, with_genres))
        if without_genres:
            params["without_genres"] = ",".join(map(str, without_genres))
        if vote_average_gte is not None:
            params["vote_average.gte"] = vote_average_gte
        if vote_average_lte is not None:
            params["vote_average.lte"] = vote_average_lte
        if vote_count_gte is not None:
            params["vote_count.gte"] = vote_count_gte
        if vote_count_lte is not None:
            params["vote_count.lte"] = vote_count_lte
        if primary_release_date_gte:
            params["primary_release_date.gte"] = primary_release_date_gte.isoformat()
        if primary_release_date_lte:
            params["primary_release_date.lte"] = primary_release_date_lte.isoformat()
        if with_watch_providers:
            params["with_watch_providers"] = "|".join(map(str, with_watch_providers))
            params["watch_region"] = watch_region or self.region
            params["with_watch_monetization_types"] = with_watch_monetization_types
        if with_original_language:
            params["with_original_language"] = with_original_language
        if with_release_type:
            params["with_release_type"] = with_release_type
        if region:
            params["region"] = region

        # Fetch with pagination if limit > 20
        all_results: list[Movie] = []
        page = 1

        while len(all_results) < limit:
            params["page"] = page
            response = await self.get("/discover/movie", params=params)
            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])
            total_pages = data.get("total_pages", 1)

            for item in results:
                if len(all_results) >= limit:
                    break
                all_results.append(self._parse_movie(item))

            # Stop if no more pages or we've fetched enough
            if page >= total_pages or not results:
                break
            page += 1

        self._log_items("Discover Movies", all_results, params)
        return all_results

    async def discover_series(
        self,
        sort_by: str = "popularity.desc",
        with_genres: Optional[list[int]] = None,
        without_genres: Optional[list[int]] = None,
        vote_average_gte: Optional[float] = None,
        vote_count_gte: Optional[int] = None,
        vote_count_lte: Optional[int] = None,
        first_air_date_gte: Optional[date] = None,
        first_air_date_lte: Optional[date] = None,
        with_watch_providers: Optional[list[int]] = None,
        watch_region: Optional[str] = None,
        with_status: Optional[int] = None,
        with_original_language: Optional[str] = None,
        with_origin_country: Optional[str] = None,
        limit: int = 20,
    ) -> list[Series]:
        """
        Discover TV series with filters.

        Args:
            sort_by: Sort order
            with_genres: Include genres
            without_genres: Exclude genres
            vote_average_gte: Minimum vote average
            vote_count_gte: Minimum vote count
            vote_count_lte: Maximum vote count
            first_air_date_gte: Aired after date
            first_air_date_lte: Aired before date
            with_watch_providers: Watch provider IDs
            watch_region: Region for watch providers
            with_status: Status filter (0=Returning, 3=Ended, etc.)
            with_original_language: Filter by original language (ISO 639-1)
            with_origin_country: Filter by origin country (ISO 3166-1)
            limit: Maximum results

        Returns:
            List of discovered series
        """
        params = self._params(sort_by=sort_by)

        if with_genres:
            params["with_genres"] = ",".join(map(str, with_genres))
        if without_genres:
            params["without_genres"] = ",".join(map(str, without_genres))
        if vote_average_gte is not None:
            params["vote_average.gte"] = vote_average_gte
        if vote_count_gte is not None:
            params["vote_count.gte"] = vote_count_gte
        if vote_count_lte is not None:
            params["vote_count.lte"] = vote_count_lte
        if first_air_date_gte:
            params["first_air_date.gte"] = first_air_date_gte.isoformat()
        if first_air_date_lte:
            params["first_air_date.lte"] = first_air_date_lte.isoformat()
        if with_watch_providers:
            params["with_watch_providers"] = "|".join(map(str, with_watch_providers))
            params["watch_region"] = watch_region or self.region
            params["with_watch_monetization_types"] = "flatrate"
        if with_status is not None:
            params["with_status"] = with_status
        if with_original_language:
            params["with_original_language"] = with_original_language
        if with_origin_country:
            params["with_origin_country"] = with_origin_country

        # Fetch with pagination if limit > 20
        all_results: list[Series] = []
        page = 1
        per_page = 20  # TMDb returns 20 results per page

        while len(all_results) < limit:
            params["page"] = page
            response = await self.get("/discover/tv", params=params)
            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])
            total_pages = data.get("total_pages", 1)

            for item in results:
                if len(all_results) >= limit:
                    break
                all_results.append(self._parse_series(item))

            # Stop if no more pages or we've fetched enough
            if page >= total_pages or not results:
                break
            page += 1

        self._log_items("Discover Series", all_results, params)
        return all_results

    # =========================================================================
    # Lists
    # =========================================================================

    async def get_list(
        self,
        list_id: str | int,
        media_type: Optional[MediaType] = None,
        limit: Optional[int] = None,
    ) -> list[MediaItem]:
        """
        Get items from a TMDb list.

        Args:
            list_id: TMDb list ID
            media_type: Optional filter by media type
            limit: Optional maximum number of items

        Returns:
            List of media items
        """
        all_results: list[MediaItem] = []
        page = 1

        while True:
            params = self._params(page=page)
            response = await self.get(f"/list/{list_id}", params=params)

            if response.status_code == 404:
                logger.warning(f"TMDb list not found: {list_id}")
                return []

            response.raise_for_status()

            data = response.json()
            results = data.get("items") or data.get("results", [])
            total_pages = data.get("total_pages", 1)

            for item in results:
                parsed_item = self._parse_list_item(item, media_type)
                if parsed_item:
                    all_results.append(parsed_item)

                if limit and len(all_results) >= limit:
                    self._log_items(f"List {list_id}", all_results, params)
                    return all_results

            if page >= total_pages or not results:
                break
            page += 1

        self._log_items(f"List {list_id}", all_results, self._params())
        return all_results

    def _parse_list_item(
        self,
        data: dict[str, Any],
        media_type: Optional[MediaType] = None,
    ) -> Optional[MediaItem]:
        """Parse a TMDb list item into Movie/Series."""
        item_type = (data.get("media_type") or "").lower()

        if item_type == "movie":
            if media_type is None or media_type == MediaType.MOVIE:
                return self._parse_movie(data)
            return None

        if item_type == "tv":
            if media_type is None or media_type == MediaType.SERIES:
                return self._parse_series(data)
            return None

        # Fallback for entries without media_type
        if media_type == MediaType.MOVIE:
            return self._parse_movie(data)
        if media_type == MediaType.SERIES:
            return self._parse_series(data)

        if data.get("title") or data.get("release_date"):
            return self._parse_movie(data)
        if data.get("name") or data.get("first_air_date"):
            return self._parse_series(data)

        logger.debug(f"Skipping TMDb list item with unknown type: {data.get('id')}")
        return None

    # =========================================================================
    # Airing / Now Playing
    # =========================================================================

    async def get_airing_today(self, limit: int = 20) -> list[Series]:
        """Get series airing today."""
        return await self._fetch_paginated_results(
            endpoint="/tv/airing_today",
            limit=limit,
            parser=self._parse_series,
            params={},
        )

    async def get_on_the_air(self, limit: int = 20) -> list[Series]:
        """Get series currently on the air (next 7 days)."""
        return await self._fetch_paginated_results(
            endpoint="/tv/on_the_air",
            limit=limit,
            parser=self._parse_series,
            params={},
        )

    # =========================================================================
    # Details
    # =========================================================================

    async def get_movie_details(self, tmdb_id: int) -> Optional[Movie]:
        """Get movie details by TMDb ID."""
        response = await self.get(
            f"/movie/{tmdb_id}",
            params=self._params(append_to_response="external_ids"),
        )

        if response.status_code == 404:
            return None

        response.raise_for_status()
        return self._parse_movie_details(response.json())

    async def is_movie_released(self, tmdb_id: int) -> bool:
        """
        Check if a movie is available at home (digital or physical release).

        Uses TMDb release dates (type 4 = digital, 5 = physical) in any country,
        so theatrical-only movies are reported as not released.
        """
        response = await self.get(f"/movie/{tmdb_id}/release_dates", params=self._params())

        if response.status_code == 404:
            return False

        response.raise_for_status()

        today = date.today().isoformat()
        for country in response.json().get("results", []):
            for release in country.get("release_dates", []):
                release_date = (release.get("release_date") or "")[:10]
                if release.get("type") in (4, 5) and release_date and release_date <= today:
                    return True

        return False

    async def get_series_details(self, tmdb_id: int) -> Optional[Series]:
        """Get TV series details by TMDb ID."""
        response = await self.get(
            f"/tv/{tmdb_id}",
            params=self._params(append_to_response="external_ids"),
        )

        if response.status_code == 404:
            return None

        response.raise_for_status()
        return self._parse_series_details(response.json())

    async def find_by_imdb_id(
        self,
        imdb_id: str,
        media_type: Optional[MediaType] = None,
    ) -> Optional[MediaItem]:
        """Resolve IMDb ID to TMDb movie/series item via /find endpoint."""
        response = await self.get(
            f"/find/{imdb_id}",
            params=self._params(external_source="imdb_id"),
        )

        if response.status_code == 404:
            return None

        response.raise_for_status()
        data = response.json()

        if media_type == MediaType.MOVIE:
            results = data.get("movie_results", [])
            if results:
                item = self._parse_movie(results[0])
                item.imdb_id = imdb_id
                return item
            return None

        if media_type == MediaType.SERIES:
            results = data.get("tv_results", [])
            if results:
                item = self._parse_series(results[0])
                item.imdb_id = imdb_id
                return item
            return None

        movie_results = data.get("movie_results", [])
        if movie_results:
            item = self._parse_movie(movie_results[0])
            item.imdb_id = imdb_id
            return item

        tv_results = data.get("tv_results", [])
        if tv_results:
            item = self._parse_series(tv_results[0])
            item.imdb_id = imdb_id
            return item

        return None

    # =========================================================================
    # Search
    # =========================================================================

    async def search_movies(
        self,
        query: str,
        year: Optional[int] = None,
        limit: int = 10,
    ) -> list[Movie]:
        """Search for movies."""
        params = self._params(query=query)
        if year:
            params["year"] = year

        response = await self.get("/search/movie", params=params)
        response.raise_for_status()

        return [
            self._parse_movie(item)
            for item in response.json().get("results", [])[:limit]
        ]

    async def search_series(
        self,
        query: str,
        year: Optional[int] = None,
        limit: int = 10,
    ) -> list[Series]:
        """Search for TV series."""
        params = self._params(query=query)
        if year:
            params["first_air_date_year"] = year

        response = await self.get("/search/tv", params=params)
        response.raise_for_status()

        return [
            self._parse_series(item)
            for item in response.json().get("results", [])[:limit]
        ]

    # =========================================================================
    # Parsers
    # =========================================================================

    def _parse_movie(self, data: dict[str, Any]) -> Movie:
        """Parse movie from API response."""
        release_date = None
        year = None
        if data.get("release_date"):
            try:
                release_date = date.fromisoformat(data["release_date"])
                year = release_date.year
            except ValueError:
                pass

        # Get genre IDs (available in discover/list endpoints)
        genre_ids = data.get("genre_ids", [])

        return Movie(
            title=data.get("title", "Unknown"),
            year=year,
            tmdb_id=data.get("id"),
            overview=data.get("overview"),
            genres=genre_ids,  # Store genre IDs for filtering
            original_language=data.get("original_language"),
            vote_average=data.get("vote_average"),
            vote_count=data.get("vote_count"),
            popularity=data.get("popularity"),
            release_date=release_date,
            poster_path=data.get("poster_path"),
            backdrop_path=data.get("backdrop_path"),
        )

    def _parse_movie_details(self, data: dict[str, Any]) -> Movie:
        """Parse movie from details endpoint."""
        movie = self._parse_movie(data)

        # Add additional fields
        movie.genres = [g["name"] for g in data.get("genres", [])]
        movie.runtime = data.get("runtime")
        movie.budget = data.get("budget")
        movie.revenue = data.get("revenue")
        movie.tagline = data.get("tagline")
        movie.status = data.get("status")

        # External IDs
        external_ids = data.get("external_ids", {})
        movie.imdb_id = external_ids.get("imdb_id")

        # Collection
        if data.get("belongs_to_collection"):
            movie.belongs_to_collection = data["belongs_to_collection"].get("name")

        return movie

    def _parse_series(self, data: dict[str, Any]) -> Series:
        """Parse TV series from API response."""
        first_air_date = None
        year = None
        if data.get("first_air_date"):
            try:
                first_air_date = date.fromisoformat(data["first_air_date"])
                year = first_air_date.year
            except ValueError:
                pass

        # Get genre IDs (available in discover/list endpoints)
        genre_ids = data.get("genre_ids", [])

        return Series(
            title=data.get("name", "Unknown"),
            year=year,
            tmdb_id=data.get("id"),
            overview=data.get("overview"),
            genres=genre_ids,  # Store genre IDs for filtering
            original_language=data.get("original_language"),
            original_country=data.get("origin_country", [None])[0],
            vote_average=data.get("vote_average"),
            vote_count=data.get("vote_count"),
            popularity=data.get("popularity"),
            first_air_date=first_air_date,
            poster_path=data.get("poster_path"),
            backdrop_path=data.get("backdrop_path"),
        )

    def _parse_series_details(self, data: dict[str, Any]) -> Series:
        """Parse TV series from details endpoint."""
        series = self._parse_series(data)

        # Add additional fields
        series.genres = [g["name"] for g in data.get("genres", [])]
        series.number_of_seasons = data.get("number_of_seasons")
        series.number_of_episodes = data.get("number_of_episodes")
        series.episode_run_time = data.get("episode_run_time", [])
        series.in_production = data.get("in_production", False)
        series.status = data.get("status")
        series.networks = [n["name"] for n in data.get("networks", [])]

        # Last air date
        if data.get("last_air_date"):
            try:
                series.last_air_date = date.fromisoformat(data["last_air_date"])
            except ValueError:
                pass

        # External IDs
        external_ids = data.get("external_ids", {})
        series.imdb_id = external_ids.get("imdb_id")
        series.tvdb_id = external_ids.get("tvdb_id")

        return series
