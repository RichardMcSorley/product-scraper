"""API client utilities for Walmart API requests (public/internal APIs, no auth required)."""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def get_default_headers():
    """Returns standard headers for Walmart.com API requests."""
    return {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'en-US,en;q=0.9',
        'origin': 'https://www.walmart.com',
        'referer': 'https://www.walmart.com/',
        'sec-ch-ua': '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    }


def create_session(headers=None):
    """Creates a requests session with retry strategy.
    
    Args:
        headers: Optional headers dictionary. If None, uses default headers.
    
    Returns:
        Configured requests.Session object
    """
    if headers is None:
        headers = get_default_headers()
    
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.headers.update(headers)
    
    return session
