"""
Reddit API Client
Access Reddit posts, comments, and subreddit data for sentiment analysis
"""

import requests
import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import base64
import os


class RedditClient:
    """Complete Reddit API Client for sentiment analysis data collection"""

    def __init__(self,
                 client_id: str,
                 client_secret: str,
                 user_agent: str,
                 username: str,
                 password: str,
                 db_path: Optional[str] = None,
                 rate_limit_delay: float = 1.0):
        """
        Initialize Reddit client with OAuth2 authentication

        Args:
            client_id: Reddit app client ID
            client_secret: Reddit app client secret
            user_agent: User agent string for API requests
            username: Reddit username
            password: Reddit password
            db_path: Path to Reddit database (optional)
            rate_limit_delay: Delay between requests (seconds)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        self.username = username
        self.password = password
        self.db_path = db_path
        self.rate_limit_delay = rate_limit_delay
        self._last_request_time = 0
        self._access_token = None
        self._token_expires_at = None

        # Initialize session
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.user_agent})

        # Authenticate on initialization
        self._authenticate()

    def _authenticate(self):
        """Authenticate with Reddit API using OAuth2"""
        auth_url = "https://www.reddit.com/api/v1/access_token"

        # Basic auth with client_id and client_secret
        auth_string = f"{self.client_id}:{self.client_secret}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')

        headers = {
            'Authorization': f'Basic {auth_b64}',
            'User-Agent': self.user_agent
        }

        data = {
            'grant_type': 'password',
            'username': self.username,
            'password': self.password
        }

        response = requests.post(auth_url, headers=headers, data=data, timeout=15)
        response.raise_for_status()

        token_data = response.json()
        self._access_token = token_data['access_token']
        expires_in = token_data.get('expires_in', 3600)  # Default 1 hour
        self._token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)  # Refresh 1 min early

        # Update session headers with token
        self.session.headers.update({'Authorization': f'Bearer {self._access_token}'})

    def _is_token_expired(self) -> bool:
        """Check if access token is expired"""
        if not self._token_expires_at:
            return True
        return datetime.now() >= self._token_expires_at

    def _ensure_authenticated(self):
        """Ensure we have a valid access token"""
        if self._is_token_expired():
            self._authenticate()

    def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> Dict:
        """
        Make authenticated API request with rate limiting

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            params: URL parameters
            data: Request body data

        Returns:
            JSON response data
        """
        self._ensure_authenticated()

        # Rate limiting
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)

        url = f"https://oauth.reddit.com{endpoint}"

        if method.upper() == 'GET':
            response = self.session.get(url, params=params, timeout=15)
        elif method.upper() == 'POST':
            response = self.session.post(url, params=params, json=data, timeout=15)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        self._last_request_time = time.time()
        response.raise_for_status()

        return response.json()

    # =========================================================================
    # SUBREDDIT METHODS
    # =========================================================================

    def get_subreddit_posts(self,
                          subreddit: str,
                          sort: str = 'hot',
                          time_filter: str = 'day',
                          limit: int = 100) -> List[Dict]:
        """
        Get posts from a subreddit

        Args:
            subreddit: Subreddit name
            sort: Sort method (hot, new, top, rising)
            time_filter: Time filter for top posts (hour, day, week, month, year, all)
            limit: Number of posts to retrieve (max 100)

        Returns:
            List of post data
        """
        endpoint = f"/r/{subreddit}/new"
        params = {
            'sort': sort,
            't': time_filter,
            'limit': min(limit, 100)
        }

        response = self._request('GET', endpoint, params=params)
        return response.get('data', {}).get('children', [])

    def get_post_comments(self, post_id: str, sort: str = 'top', limit: int = 500) -> List[Dict]:
        """
        Get comments for a specific post

        Args:
            post_id: Reddit post ID (without t3_)
            sort: Sort method (top, new, controversial, old)
            limit: Number of comments to retrieve

        Returns:
            List of comment data
        """
        endpoint = f"/comments/{post_id}"
        params = {
            'sort': sort,
            'limit': min(limit, 500)
        }

        response = self._request('GET', endpoint, params=params)
        # Comments are in the second element of the response
        if len(response) > 1:
            return response[1].get('data', {}).get('children', [])
        return []

    def search_posts(self,
                    query: str,
                    subreddit: Optional[str] = None,
                    sort: str = 'relevance',
                    time_filter: str = 'week',
                    limit: int = 100) -> List[Dict]:
        """
        Search for posts matching a query

        Args:
            query: Search query
            subreddit: Limit search to specific subreddit (optional)
            sort: Sort method (relevance, hot, top, new, comments)
            time_filter: Time filter (hour, day, week, month, year, all)
            limit: Number of results

        Returns:
            List of post data
        """
        endpoint = "/search"
        params = {
            'q': query,
            'type': 'link',
            'sort': sort,
            't': time_filter,
            'limit': min(limit, 100)
        }

        if subreddit:
            params['q'] = f"{query} subreddit:{subreddit}"

        response = self._request('GET', endpoint, params=params)
        return response.get('data', {}).get('children', [])

    # =========================================================================
    # SENTIMENT ANALYSIS SPECIFIC METHODS
    # =========================================================================

    def get_wallstreetbets_posts(self,
                                sort: str = 'hot',
                                limit: int = 100,
                                keywords: Optional[List[str]] = None) -> List[Dict]:
        """
        Get posts from r/wallstreetbets for sentiment analysis

        Args:
            sort: Sort method (hot, new, top)
            limit: Number of posts to retrieve
            keywords: Optional keywords to filter by

        Returns:
            List of relevant posts with sentiment analysis data
        """
        posts = self.get_subreddit_posts('wallstreetbets', sort=sort, limit=limit)

        # Filter by keywords if provided
        if keywords:
            filtered_posts = []
            for post in posts:
                post_data = post.get('data', {})
                title = post_data.get('title', '').lower()
                text = post_data.get('selftext', '').lower()

                if any(keyword.lower() in title or keyword.lower() in text for keyword in keywords):
                    filtered_posts.append(post)
            posts = filtered_posts

        return posts

    def get_stock_related_posts(self,
                               symbols: List[str],
                               subreddits: List[str] = ['wallstreetbets', 'stocks', 'investing'],
                               limit_per_subreddit: int = 50) -> Dict[str, List[Dict]]:
        """
        Get posts related to specific stock symbols

        Args:
            symbols: List of stock symbols (e.g., ['GME', 'AMC', 'TSLA'])
            subreddits: List of subreddits to search
            limit_per_subreddit: Number of posts per subreddit

        Returns:
            Dictionary mapping symbols to relevant posts
        """
        results = {}

        for symbol in symbols:
            results[symbol] = []

            for subreddit in subreddits:
                # Search for symbol mentions
                posts = self.search_posts(
                    query=symbol,
                    subreddit=subreddit,
                    sort='hot',
                    time_filter='day',
                    limit=limit_per_subreddit
                )

                # Filter for posts actually mentioning the symbol
                relevant_posts = []
                for post in posts:
                    post_data = post.get('data', {})
                    title = post_data.get('title', '')
                    text = post_data.get('selftext', '')

                    # Check if symbol is mentioned as a whole word
                    import re
                    pattern = r'\b' + re.escape(symbol) + r'\b'
                    if re.search(pattern, title, re.IGNORECASE) or re.search(pattern, text, re.IGNORECASE):
                        relevant_posts.append(post)

                results[symbol].extend(relevant_posts)

        return results

    def get_post_with_comments(self, post_id: str, comment_limit: int = 100) -> Dict:
        """
        Get a post with its comments for comprehensive analysis

        Args:
            post_id: Reddit post ID
            comment_limit: Maximum number of comments to retrieve

        Returns:
            Dictionary containing post data and comments
        """
        # Get post details
        endpoint = f"/comments/{post_id}"
        params = {'limit': 1}  # Just the post, no comments initially

        response = self._request('GET', endpoint, params=params)
        post_data = response[0].get('data', {}).get('children', [{}])[0].get('data', {})

        # Get comments
        comments = self.get_post_comments(post_id, limit=comment_limit)

        return {
            'post': post_data,
            'comments': [comment.get('data', {}) for comment in comments],
            'comment_count': len(comments),
            'retrieved_at': datetime.now().isoformat()
        }

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def extract_post_text(self, post: Dict) -> str:
        """
        Extract text content from a post for sentiment analysis

        Args:
            post: Post data from API

        Returns:
            Combined text content (title + body)
        """
        post_data = post.get('data', {})
        title = post_data.get('title', '')
        body = post_data.get('selftext', '')

        if body:
            return f"{title}\n\n{body}"
        return title

    def extract_comment_text(self, comment: Dict) -> str:
        """
        Extract text content from a comment for sentiment analysis

        Args:
            comment: Comment data from API

        Returns:
            Comment text content
        """
        return comment.get('data', {}).get('body', '')

    def rate_limit_info(self) -> Dict:
        """
        Get rate limit information from API headers

        Returns:
            Dictionary with rate limit data
        """
        endpoint = "/r/test"
        try:
            response = self.session.get(f"https://oauth.reddit.com{endpoint}", timeout=5)
            headers = response.headers

            return {
                'used': int(headers.get('x-ratelimit-used', 0)),
                'remaining': int(headers.get('x-ratelimit-remaining', 0)),
                'reset': int(headers.get('x-ratelimit-reset', 0))
            }
        except:
            return {'error': 'Could not retrieve rate limit info'}

    def __del__(self):
        """Cleanup when object is destroyed"""
        if hasattr(self, 'session'):
            self.session.close()


# Convenience function to create client from environment variables
def create_reddit_client_from_env(rate_limit_delay: float = 1.0) -> RedditClient:
    """
    Create Reddit client using environment variables

    Args:
        rate_limit_delay: Delay between requests

    Returns:
        Configured RedditClient instance
    """
    return RedditClient(
        client_id=os.getenv('REDDIT_CLIENT_ID', ''),
        client_secret=os.getenv('REDDIT_CLIENT_SECRET', ''),
        user_agent=os.getenv('REDDIT_USER_AGENT', ''),
        username=os.getenv('REDDIT_USERNAME', ''),
        password=os.getenv('REDDIT_PASSWORD', ''),
        db_path=os.getenv('REDDIT_DB_PATH'),
        rate_limit_delay=rate_limit_delay
    )