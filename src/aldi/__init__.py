"""ALDI API client package."""
from .product_fetcher import (
    fetch_all_products,
    fetch_products_by_category,
    fetch_product_details,
    extract_category_keys_from_details,
    extract_product_data,
)
from .api_client import create_session, get_default_headers, get_product_details_headers
from .config import (
    BASE_URL,
    PRODUCT_DETAILS_BASE_URL,
    DEFAULT_SERVICE_POINT,
    DEFAULT_LIMIT,
    MAX_PRODUCTS,
)
from .fetch_all_products import main

__all__ = [
    'fetch_all_products',
    'fetch_products_by_category',
    'fetch_product_details',
    'extract_category_keys_from_details',
    'extract_product_data',
    'create_session',
    'get_default_headers',
    'get_product_details_headers',
    'main',
    'BASE_URL',
    'PRODUCT_DETAILS_BASE_URL',
    'DEFAULT_SERVICE_POINT',
    'DEFAULT_LIMIT',
    'MAX_PRODUCTS',
]
