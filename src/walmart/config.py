"""Configuration constants for Walmart API client."""

# API Configuration - Using Walmart.com's internal/public APIs
# These are the APIs that Walmart.com uses internally (similar to ALDI approach)
BASE_URL = 'https://www.walmart.com'  # Base URL for Walmart.com
SEARCH_API_URL = 'https://www.walmart.com/search'  # Product search endpoint
STORE_PAGE_URL = 'https://www.walmart.com/store/{store_id}'  # Store page URL

# Store Configuration
DEFAULT_STORE_ID = 1426  # Store 1426 in Ashland, KY
DEFAULT_ZIPCODE = '41101'  # Zipcode for store 1426

# API Limits (to be determined based on actual API behavior)
DEFAULT_LIMIT = 40  # Products per page (typical for Walmart search)
MAX_PRODUCTS = 1000  # Cap to avoid excessive requests

# Default API Parameters
DEFAULT_PARAMS = {
    'query': '',  # Search query
    'page': 1,  # Page number
    'affinityOverride': 'default',  # Store affinity
}
