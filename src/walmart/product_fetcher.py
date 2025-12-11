"""Product fetching functions for Walmart.com (using HTML parsing)."""
import logging
import time
import requests
import re
import json
from urllib.parse import urljoin, urlparse, parse_qs

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    from tqdm.auto import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    # Simple progress bar replacement
    class tqdm:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def __iter__(self):
            return iter([])
        @staticmethod
        def write(*args, **kwargs):
            print(*args)

from .config import (
    BASE_URL,
    SEARCH_API_URL,
    DEFAULT_STORE_ID,
    DEFAULT_LIMIT,
    MAX_PRODUCTS,
    DEFAULT_PARAMS,
)
from .api_client import create_session, get_default_headers


def extract_product_data_from_html(product_element):
    """Extract product data from HTML element.
    
    Args:
        product_element: HTML element or dict with product info
    
    Returns:
        Dictionary with extracted product fields
    """
    # Extract from various possible HTML structures
    if isinstance(product_element, dict):
        return {
            'item_id': product_element.get('itemId') or product_element.get('id') or product_element.get('usItemId'),
            'name': product_element.get('name') or product_element.get('title') or product_element.get('productName'),
            'price': product_element.get('price') or product_element.get('salePrice') or product_element.get('currentPrice'),
            'store_id': product_element.get('storeId', DEFAULT_STORE_ID),
            'availability': product_element.get('availability') or product_element.get('inStock') or product_element.get('available'),
            'image_url': product_element.get('image') or product_element.get('thumbnailImage') or product_element.get('imageUrl'),
            'product_url': product_element.get('productUrl') or product_element.get('url') or product_element.get('canonicalUrl'),
        }
    
    # If it's a string (URL), extract item ID from URL
    if isinstance(product_element, str):
        # Extract from /ip/Product-Name/ITEM_ID URLs
        match = re.search(r'/ip/[^/]+/(\d+)', product_element)
        if match:
            return {
                'item_id': match.group(1),
                'product_url': urljoin(BASE_URL, product_element) if not product_element.startswith('http') else product_element,
            }
    
    return {}


def parse_search_page_html(html_content):
    """Parse Walmart search page HTML to extract product information.
    
    Args:
        html_content: HTML content of search page
    
    Returns:
        list: List of product dictionaries
    """
    products = []
    seen_ids = set()
    
    # Method 1: Extract product links (/ip/Product-Name/ITEM_ID)
    # Handle both with and without query parameters
    product_url_pattern = r'href=["\'](/ip/[^"\']+/(\d+))[^"\']*["\']'
    matches = re.findall(product_url_pattern, html_content)
    
    for url_path, item_id in matches:
        if item_id not in seen_ids:
            seen_ids.add(item_id)
            # Clean URL (remove query params for now, keep base path)
            clean_path = url_path.split('?')[0] if '?' in url_path else url_path
            full_url = urljoin(BASE_URL, clean_path)
            products.append({
                'item_id': item_id,
                'product_url': full_url,
            })
    
    # Method 2: Extract usItemId directly from HTML (Walmart uses this format)
    # Pattern: "usItemId":"12345678" or 'usItemId':"12345678"
    us_item_id_pattern = r'["\']usItemId["\']\s*:\s*["\']?(\d+)["\']?'
    us_item_ids = re.findall(us_item_id_pattern, html_content)
    
    for item_id in us_item_ids:
        if item_id not in seen_ids:
            seen_ids.add(item_id)
            products.append({
                'item_id': item_id,
                'product_url': f'{BASE_URL}/ip/{item_id}',  # Construct URL from ID
            })
    
    # Method 3: Look for JSON data in script tags
    script_pattern = r'<script[^>]*>(.*?)</script>'
    scripts = re.findall(script_pattern, html_content, re.DOTALL | re.IGNORECASE)
    
    for script_content in scripts:
        # Look for product data structures
        if 'itemId' in script_content or 'usItemId' in script_content:
            # Try to find JSON objects with product data - more flexible pattern
            # Look for objects that might span multiple lines
            json_pattern = r'\{(?:[^{}]|(?:\{[^{}]*\}))*["\'](?:itemId|usItemId)["\'][^}]*\}'
            json_matches = re.findall(json_pattern, script_content, re.DOTALL)
            for json_str in json_matches:
                try:
                    data = json.loads(json_str)
                    item_id = str(data.get('itemId') or data.get('usItemId', ''))
                    if item_id and item_id not in seen_ids:
                        seen_ids.add(item_id)
                        products.append(extract_product_data_from_html(data))
                except (json.JSONDecodeError, ValueError):
                    continue
    
    logging.info(f"Extracted {len(products)} products from HTML")
    return products


def fetch_products_by_search(query, store_id=None, session=None, max_products=1000):
    """Fetch products from Walmart.com search by parsing HTML.
    
    Args:
        query: Search query string
        store_id: Store ID to filter by (defaults to DEFAULT_STORE_ID, added as URL param)
        session: Optional requests session to reuse
        max_products: Maximum number of products to fetch
    
    Returns:
        DataFrame with products (or list if pandas not available)
    """
    if store_id is None:
        store_id = DEFAULT_STORE_ID
    
    if session is None:
        session = create_session()
    
    products = []
    page = 1
    
    while len(products) < max_products:
        # Build search URL
        params = {'q': query, 'page': page}
        if store_id:
            params['store'] = store_id
        
        url = f'{BASE_URL}/search'
        
        try:
            response = session.get(url, params=params, timeout=15)
            
            if response.status_code == 412:
                logging.warning("Request blocked (412). Walmart may be detecting automated requests.")
                logging.warning("Try using a browser with proper headers or add delays.")
                break
            
            response.raise_for_status()
            
            # Parse HTML to extract products
            page_products = parse_search_page_html(response.text)
            
            if not page_products:
                logging.info(f"No more products found on page {page}")
                break
            
            products.extend(page_products)
            logging.info(f"Page {page}: Found {len(page_products)} products (total: {len(products)})")
            
            # Check if we've reached max
            if len(products) >= max_products:
                products = products[:max_products]
                break
            
            page += 1
            time.sleep(1)  # Rate limiting
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching page {page}: {e}")
            break
    
    logging.info(f"Total products extracted: {len(products)}")
    
    if HAS_PANDAS:
        return pd.DataFrame(products)
    else:
        return products


def fetch_store_products(store_id=None, session=None, category=None):
    """Fetch products available at a specific store by browsing/searching.
    
    Args:
        store_id: Store ID (defaults to DEFAULT_STORE_ID)
        session: Optional requests session
        category: Optional category to filter by
    
    Returns:
        DataFrame with store products (or list if pandas not available)
    
    Note: This searches for common products. For comprehensive store inventory,
         you would need to iterate through categories or use a product catalog.
    """
    if store_id is None:
        store_id = DEFAULT_STORE_ID
    
    if session is None:
        session = create_session()
    
    # Common product searches to get store inventory
    common_searches = [
        'milk', 'bread', 'eggs', 'chicken', 'beef',
        'bananas', 'apples', 'lettuce', 'tomatoes',
        'cereal', 'pasta', 'rice', 'soup'
    ]
    
    all_products = []
    
    for search_term in common_searches:
        logging.info(f"Searching for '{search_term}' at store {store_id}")
        products = fetch_products_by_search(
            search_term, 
            store_id=store_id, 
            session=session, 
            max_products=100
        )
        
        if not products.empty:
            all_products.append(products)
        
        time.sleep(2)  # Rate limiting between searches
    
    if all_products:
        if HAS_PANDAS:
            combined = pd.concat(all_products, ignore_index=True)
            # Remove duplicates based on item_id
            combined = combined.drop_duplicates(subset=['item_id'], keep='first')
            return combined
        else:
            # Manual deduplication without pandas
            seen_ids = set()
            unique_products = []
            for product_list in all_products:
                for product in product_list:
                    item_id = product.get('item_id')
                    if item_id and item_id not in seen_ids:
                        seen_ids.add(item_id)
                        unique_products.append(product)
            return unique_products
    
    if HAS_PANDAS:
        return pd.DataFrame()
    else:
        return []
