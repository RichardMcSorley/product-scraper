"""Configuration constants for ALDI API client."""

# API Configuration
BASE_URL = 'https://api.aldi.us/v3/product-search'
PRODUCT_DETAILS_BASE_URL = 'https://api.aldi.us/v1/products'
DEFAULT_SERVICE_POINT = '440-018'
DEFAULT_LIMIT = 60  # Valid limit values: [12,16,24,30,32,48,60]
MAX_PRODUCTS = 1000  # Cap pagination to avoid API errors

# Default API Parameters
DEFAULT_PARAMS = {
    'currency': 'USD',
    'serviceType': 'pickup',
    'sort': 'relevance',
    'testVariant': 'A',
}
