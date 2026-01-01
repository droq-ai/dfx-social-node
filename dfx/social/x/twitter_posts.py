"""X (Twitter) posts component for fetching posts via X API."""

import aiohttp
from typing import Any, Dict, Optional

from dfx import Component, Data, StrInput, IntInput, Output


class TwitterAPIError(Exception):
    """Custom exception for Twitter API errors."""

    def __init__(self, message: str, error_code: Optional[int] = None):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class TwitterHTTPError(Exception):
    """Custom exception for Twitter HTTP errors."""

    def __init__(self, message: str, error_code: Optional[int] = None):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class TwitterAPI:
    """Twitter API client for making requests to the X API."""

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
        bearer_token: str,
        url: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make a request to the Twitter API."""
        if not self.session:
            self.session = aiohttp.ClientSession()

        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "User-Agent": "DFX-Social-Node/1.0"
        }

        try:
            async with self.session.get(url, headers=headers, params=params) as response:
                data = await response.json()

                if response.status == 404:
                    raise TwitterAPIError("Resource not found", 404)
                elif response.status == 429:
                    raise TwitterAPIError("Rate limit exceeded", 429)
                elif response.status == 401:
                    raise TwitterAPIError("Unauthorized - invalid bearer token", 401)
                elif response.status != 200:
                    raise TwitterAPIError(
                        data.get("detail", "Unknown API error"),
                        response.status
                    )

                return data

        except aiohttp.ClientError as e:
            raise TwitterHTTPError(f"HTTP error: {str(e)}")


class DFXTwitterPostsComponent(Component):
    """Component for fetching posts from X (Twitter) API.

    This component allows fetching tweets from a user's timeline using
    the X API v2. It supports various tweet fields and expansions.
    """

    display_name: str = "DFX Twitter Posts"
    description: str = "Fetch posts from X (Twitter) via API"
    icon: str = "twitter"
    name: str = "DFXTwitterPosts"

    inputs: list = [
        StrInput(
            name="bearer_token",
            display_name="Bearer Token",
            info="X API Bearer Token (get from X Developer Portal)",
            value="",
            required=True
        ),
        StrInput(
            name="username",
            display_name="Username",
            info="Twitter username without @",
            value="",
            required=True
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            info="Maximum number of tweets to fetch (1-100)",
            value=10,
            required=False
        )
    ]

    outputs: list = [
        Output(
            display_name="Posts Result",
            name="result",
            type_=Data,
            method="get_tweets",
        )
    ]

    def __init__(self, **kwargs):
        """Initialize component."""
        super().__init__(**kwargs)

    def _validate_inputs(self) -> Dict[str, Any]:
        """Validate required inputs and return parsed data."""
        errors = []

        # Check required fields
        if not self.bearer_token or not self.bearer_token.strip():
            errors.append("bearer_token is required")

        if not self.username or not self.username.strip():
            errors.append("username is required")

        # Validate max_results
        if not isinstance(self.max_results, int) or self.max_results < 1 or self.max_results > 100:
            errors.append("max_results must be between 1 and 100")

        if errors:
            return {"valid": False, "errors": errors}

        return {"valid": True}

    async def get_tweets(self) -> Data:
        """Fetch tweets from a user's timeline via X API.

        Returns:
            Data: Contains the result of the tweets fetching operation.
        """
        try:
            # Validate inputs
            validation = self._validate_inputs()
            if not validation["valid"]:
                error_message = "Validation failed: " + "; ".join(validation["errors"])
                self.status = error_message
                self.log(error_message)
                raise ValueError(error_message)

            # Log the operation
            self.log(f"Fetching tweets for user @{self.username}")

            # Make API request
            async with TwitterAPI() as api:
                # Step 1: Get user ID from username
                user_url = "https://api.twitter.com/2/users/by/username/" + self.username.strip()
                user_params = {
                    "user.fields": "verified,profile_image_url"
                }

                user_data = await api._make_request(
                    bearer_token=self.bearer_token.strip(),
                    url=user_url,
                    params=user_params
                )

                user_id = user_data.get("data", {}).get("id")
                if not user_id:
                    raise ValueError(f"User @{self.username} not found")

                # Step 2: Get user's tweets
                tweets_url = f"https://api.twitter.com/2/users/{user_id}/tweets"
                tweets_params = {
                    "max_results": self.max_results,
                    "tweet.fields": "created_at,public_metrics,attachments",
                    "expansions": "author_id,attachments.media_keys",
                    "user.fields": "verified,profile_image_url",
                    "media.fields": "url,preview_image_url,type"
                }

                tweets_data = await api._make_request(
                    bearer_token=self.bearer_token.strip(),
                    url=tweets_url,
                    params=tweets_params
                )

            # Log success
            tweet_count = len(tweets_data.get("data", []))
            success_msg = f"Successfully fetched {tweet_count} tweets from @{self.username}"
            self.status = success_msg
            self.log(success_msg)

            # Return success result
            return Data(
                data={
                    "success": True,
                    "message": success_msg,
                    "username": self.username.strip(),
                    "user_id": user_id,
                    "tweet_count": tweet_count,
                    "tweets": tweets_data.get("data", []),
                    "includes": tweets_data.get("includes", {}),
                    "operation": "get_tweets",
                    "api_response": tweets_data
                }
            )

        except TwitterAPIError as e:
            error_message = f"Twitter API error: {e.message}"
            self.status = error_message
            self.log(error_message)
            raise ValueError(error_message) from e

        except TwitterHTTPError as e:
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
        """Return the main get_tweets function."""
        return self.get_tweets
