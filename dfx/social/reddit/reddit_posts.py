"""Reddit posts component for fetching posts via Reddit API."""

import aiohttp
from typing import Any, Dict, Optional

from dfx import Component, Data, StrInput, IntInput, Output


class RedditAPIError(Exception):
    """Custom exception for Reddit API errors."""

    def __init__(self, message: str, error_code: Optional[int] = None):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class RedditHTTPError(Exception):
    """Custom exception for Reddit HTTP errors."""

    def __init__(self, message: str, error_code: Optional[int] = None):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class RedditAPI:
    """Reddit API client for making requests to the Reddit API."""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
            self.session = None

    async def _make_request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make a request to the Reddit API."""
        if not self.session:
            self.session = aiohttp.ClientSession()

        headers = {
            "User-Agent": "DFX-Social-Node/1.0"
        }

        try:
            async with self.session.get(url, headers=headers, params=params) as response:
                data = await response.json()

                if response.status == 404:
                    raise RedditAPIError("Resource not found", 404)
                elif response.status == 429:
                    raise RedditAPIError("Rate limit exceeded", 429)
                elif response.status != 200:
                    raise RedditAPIError(
                        data.get("message", "Unknown API error"),
                        response.status
                    )

                return data

        except aiohttp.ClientError as e:
            raise RedditHTTPError(f"HTTP error: {str(e)}")


class DFXRedditPostsComponent(Component):
    """Component for fetching posts from Reddit API.

    This component allows fetching posts from subreddits or user profiles
    using the Reddit public API.
    """

    display_name: str = "DFX Reddit Posts"
    description: str = "Fetch posts from Reddit via API"
    icon: str = "reddit"
    name: str = "DFXRedditPosts"

    inputs: list = [
        StrInput(
            name="resource_type",
            display_name="Resource Type",
            info="Type of resource: 'subreddit' or 'user'",
            value="subreddit",
            required=False
        ),
        StrInput(
            name="name",
            display_name="Name",
            info="Subreddit name (without r/) or username (without u/)",
            value="",
            required=True
        ),
        StrInput(
            name="sort",
            display_name="Sort Order",
            info="Sort order for subreddit: 'hot', 'new', 'top', or 'controversial'",
            value="hot",
            required=False
        ),
        IntInput(
            name="limit",
            display_name="Limit",
            info="Number of posts to fetch (1-100)",
            value=25,
            required=False
        )
    ]

    outputs: list = [
        Output(
            display_name="Posts Result",
            name="result",
            type_=Data,
            method="get_posts",
        )
    ]

    def __init__(self, **kwargs):
        """Initialize component."""
        super().__init__(**kwargs)

    def _validate_inputs(self) -> Dict[str, Any]:
        """Validate required inputs and return parsed data."""
        errors = []

        # Check required fields
        if not self.name or not self.name.strip():
            errors.append("name is required")

        # Validate resource_type
        if self.resource_type not in ["subreddit", "user"]:
            errors.append("resource_type must be 'subreddit' or 'user'")

        # Validate sort for subreddit
        if self.resource_type == "subreddit" and self.sort not in ["hot", "new", "top", "controversial"]:
            errors.append("sort must be 'hot', 'new', 'top', or 'controversial'")

        # Validate limit
        if not isinstance(self.limit, int) or self.limit < 1 or self.limit > 100:
            errors.append("limit must be between 1 and 100")

        if errors:
            return {"valid": False, "errors": errors}

        return {"valid": True}

    async def get_posts(self) -> Data:
        """Fetch posts from Reddit via API.

        Returns:
            Data: Contains the result of the posts fetching operation.
        """
        try:
            # Validate inputs
            validation = self._validate_inputs()
            if not validation["valid"]:
                error_message = "Validation failed: " + "; ".join(validation["errors"])
                self.status = error_message
                self.log(error_message)
                raise ValueError(error_message)

            # Build URL based on resource type
            if self.resource_type == "subreddit":
                url = f"https://www.reddit.com/r/{self.name.strip()}/{self.sort}.json"
                self.log(f"Fetching posts from r/{self.name} (sort: {self.sort})")
            else:  # user
                url = f"https://www.reddit.com/user/{self.name.strip()}/submitted.json"
                self.log(f"Fetching posts from u/{self.name}")

            params = {
                "limit": self.limit,
                "raw_json": 1
            }

            # Make API request
            async with RedditAPI() as api:
                response_data = await api._make_request(url, params=params)

            # Extract posts data
            posts_data = response_data.get("data", {}).get("children", [])
            post_count = len(posts_data)

            # Log success
            success_msg = f"Successfully fetched {post_count} posts from {self.resource_type} {self.name}"
            self.status = success_msg
            self.log(success_msg)

            # Return success result
            return Data(
                data={
                    "success": True,
                    "message": success_msg,
                    "resource_type": self.resource_type,
                    "name": self.name.strip(),
                    "post_count": post_count,
                    "posts": posts_data,
                    "operation": "get_posts",
                    "api_response": response_data
                }
            )

        except RedditAPIError as e:
            error_message = f"Reddit API error: {e.message}"
            self.status = error_message
            self.log(error_message)
            raise ValueError(error_message) from e

        except RedditHTTPError as e:
            error_message = f"HTTP error: {e.message}"
            self.status = error_message
            self.log(error_message)
            raise ValueError(error_message) from e

        except Exception as e:
            error_message = f"Unexpected error: {str(e)}"
            self.status = error_message
            self.log(error_message)
            raise ValueError(error_message) from e

    def build(self):
        """Return the main get_posts function."""
        return self.get_posts
