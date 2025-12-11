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


def fetch_product_details(item_id, store_id=None, session=None):
    """Fetch detailed product information from a Walmart product page.
    
    Args:
        item_id: Walmart item ID (e.g., 2274077370)
        store_id: Store ID for store-specific availability (optional)
        session: Optional requests session to reuse
    
    Returns:
        dict: Product details including name, price, description, specs, etc.
    """
    if session is None:
        session = create_session()
    
    # Build product URL
    url = f'{BASE_URL}/ip/{item_id}'
    params = {}
    
    if store_id:
        params['store'] = store_id
        params['fulfillmentIntent'] = 'In-store'
    
    try:
        response = session.get(url, params=params, timeout=15)
        
        if response.status_code == 412:
            logging.warning("Request blocked (412). Walmart may be detecting automated requests.")
            return {}
        
        response.raise_for_status()
        
        # Parse HTML to extract product details
        return parse_product_page_html(response.text, item_id)
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching product details for item {item_id}: {e}")
        return {}


def parse_product_page_html(html_content, item_id):
    """Parse Walmart product page HTML to extract detailed product information.
    
    Args:
        html_content: HTML content of product page
        item_id: Item ID for reference
    
    Returns:
        dict: Extracted product details
    """
    product_data = {
        'item_id': item_id,
        'us_item_id': None,
        'name': None,
        'price': None,
        'original_price': None,
        'price_per_unit': None,
        'price_per_unit_string': None,
        'description': None,
        'short_description': None,
        'specifications': {},
        'ingredients': None,
        'directions': None,
        'warranty': None,
        'warnings': None,
        'rating': None,
        'review_count': None,
        'image_urls': [],
        'category_paths': [],
        'product_location': [],
        'availability_status': None,
        'product_url': f'{BASE_URL}/ip/{item_id}',
        'availability': None,
        'store_availability': None,
    }
    
    # Method 1: Extract from __NEXT_DATA__ JSON (Next.js embedded data) - PRIMARY METHOD
    next_data_match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html_content, re.DOTALL)
    if next_data_match:
        try:
            next_data = json.loads(next_data_match.group(1))
            # Navigate: props.pageProps.initialData.data.product
            props = next_data.get('props', {})
            page_props = props.get('pageProps', {})
            initial_data = page_props.get('initialData', {})
            data_section = initial_data.get('data', {})
            product_info = data_section.get('product', {})
            
            if isinstance(product_info, dict):
                # Extract basic product info
                product_data['us_item_id'] = product_info.get('usItemId') or product_info.get('primaryUsItemId')
                product_data['name'] = product_info.get('name')
                product_data['short_description'] = product_info.get('shortDescription')
                
                # Extract price info
                price_info = product_info.get('priceInfo', {})
                if price_info:
                    current_price = price_info.get('currentPrice', {})
                    if current_price:
                        product_data['price'] = current_price.get('price')
                    
                    unit_price = price_info.get('unitPrice', {})
                    if unit_price:
                        product_data['price_per_unit'] = unit_price.get('price')
                        product_data['price_per_unit_string'] = unit_price.get('priceString')
                
                # Extract availability
                product_data['availability_status'] = product_info.get('availabilityStatus')
                
                # Extract category paths
                category = product_info.get('category', {})
                if category:
                    category_path = category.get('path', [])
                    if isinstance(category_path, list):
                        product_data['category_paths'] = [
                            {'name': cat.get('name'), 'url': cat.get('url')}
                            for cat in category_path
                            if isinstance(cat, dict) and cat.get('url')
                        ]
                
                # Extract image URLs
                image_info = product_info.get('imageInfo', {})
                if image_info:
                    all_images = image_info.get('allImages', [])
                    if isinstance(all_images, list):
                        product_data['image_urls'] = [
                            img.get('url') for img in all_images
                            if isinstance(img, dict) and img.get('url')
                        ]
                
                # Extract product location
                product_location = product_info.get('productLocation', [])
                if isinstance(product_location, list):
                    product_data['product_location'] = [
                        loc.get('displayValue') for loc in product_location
                        if isinstance(loc, dict) and loc.get('displayValue')
                    ]
            
            # Extract from idml section for detailed info
            idml = data_section.get('idml', {})
            if isinstance(idml, dict):
                product_data['description'] = idml.get('longDescription') or idml.get('shortDescription')
                if not product_data['short_description']:
                    product_data['short_description'] = idml.get('shortDescription')
                
                # Extract specifications
                specifications = idml.get('specifications', [])
                if isinstance(specifications, list):
                    for spec in specifications:
                        if isinstance(spec, dict):
                            name = spec.get('name') or spec.get('key')
                            value = spec.get('value') or spec.get('displayValue')
                            if name and value:
                                product_data['specifications'][name] = value
                
                # Extract ingredients
                ingredients = idml.get('ingredients', {})
                if isinstance(ingredients, dict):
                    # Try different possible keys
                    ingredient_text = (ingredients.get('ingredients') or 
                                     ingredients.get('activeIngredients') or
                                     ingredients.get('inactiveIngredients') or
                                     ingredients.get('text'))
                    if ingredient_text:
                        product_data['ingredients'] = ingredient_text
                elif isinstance(ingredients, str):
                    product_data['ingredients'] = ingredients
                
                # Extract directions
                directions = idml.get('directions', [])
                if isinstance(directions, list) and len(directions) > 0:
                    # Get first direction or combine all
                    if isinstance(directions[0], dict):
                        product_data['directions'] = directions[0].get('text') or directions[0].get('value')
                    elif isinstance(directions[0], str):
                        product_data['directions'] = directions[0]
                elif isinstance(directions, str):
                    product_data['directions'] = directions
                
                # Extract warnings
                warnings = idml.get('warnings', [])
                if isinstance(warnings, list) and len(warnings) > 0:
                    if isinstance(warnings[0], dict):
                        product_data['warnings'] = warnings[0].get('text') or warnings[0].get('message')
                    elif isinstance(warnings[0], str):
                        product_data['warnings'] = warnings[0]
                
                # Extract warranty
                warranty = idml.get('warranty', {})
                if isinstance(warranty, dict):
                    product_data['warranty'] = warranty.get('text') or warranty.get('description') or warranty.get('information')
            
            # Extract reviews/rating
            reviews = data_section.get('reviews', {})
            if isinstance(reviews, dict):
                product_data['rating'] = reviews.get('averageOverallRating')
                product_data['review_count'] = reviews.get('totalReviewCount')
                
        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            logging.warning(f"Error parsing __NEXT_DATA__: {e}")
            # Fall back to HTML parsing
            pass
    
    # Method 2: Extract name from title tag or h1 (fallback)
    if not product_data['name']:
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.IGNORECASE | re.DOTALL)
        if title_match:
            title = title_match.group(1).strip()
            # Remove " - Walmart.com" suffix
            product_data['name'] = title.replace(' - Walmart.com', '').strip()
    
    # Extract price - look for various price patterns
    price_patterns = [
        r'["\']currentPrice["\'][^}]*["\']currencyAmount["\']\s*:\s*["\']?([\d.]+)["\']?',
        r'["\']price["\'][^}]*["\']amount["\']\s*:\s*["\']?([\d.]+)["\']?',
        r'\$([\d.]+)\s*(?:per|/|\|)',
        r'current price[^$]*\$([\d.]+)',
    ]
    
    for pattern in price_patterns:
        price_match = re.search(pattern, html_content, re.IGNORECASE)
        if price_match:
            try:
                product_data['price'] = float(price_match.group(1))
                break
            except (ValueError, IndexError):
                continue
    
    # Extract price per unit
    unit_price_match = re.search(r'([\d.]+)\s*[¢$]/[^<]*', html_content, re.IGNORECASE)
    if unit_price_match:
        product_data['price_per_unit'] = unit_price_match.group(1)
    
    # Extract rating and review count
    rating_match = re.search(r'(\d+\.?\d*)\s*(?:stars?|out of 5)', html_content, re.IGNORECASE)
    if rating_match:
        try:
            product_data['rating'] = float(rating_match.group(1))
        except ValueError:
            pass
    
    review_match = re.search(r'(\d+(?:,\d+)*)\s*(?:ratings?|reviews?)', html_content, re.IGNORECASE)
    if review_match:
        review_str = review_match.group(1).replace(',', '')
        try:
            product_data['review_count'] = int(review_str)
        except ValueError:
            pass
    
    # Extract description - look for "About this item" section
    desc_pattern = r'(?:About this item|Product details)[^<]*<[^>]*>(.*?)(?:<h[1-6]|</section|</div>)'
    desc_match = re.search(desc_pattern, html_content, re.IGNORECASE | re.DOTALL)
    if desc_match:
        desc_text = desc_match.group(1)
        # Clean HTML tags
        desc_text = re.sub(r'<[^>]+>', ' ', desc_text)
        desc_text = re.sub(r'\s+', ' ', desc_text).strip()
        if desc_text:
            product_data['description'] = desc_text[:1000]  # Limit length
    
    # Extract specifications from JSON-LD structured data first
    json_ld_pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
    json_ld_matches = re.findall(json_ld_pattern, html_content, re.DOTALL | re.IGNORECASE)
    
    for json_ld_str in json_ld_matches:
        try:
            json_ld_data = json.loads(json_ld_str)
            if isinstance(json_ld_data, dict):
                # Extract from Product schema
                if json_ld_data.get('@type') == 'Product':
                    if 'name' in json_ld_data and not product_data['name']:
                        product_data['name'] = json_ld_data['name']
                    if 'description' in json_ld_data and not product_data['description']:
                        product_data['description'] = json_ld_data['description']
                    if 'aggregateRating' in json_ld_data:
                        rating_info = json_ld_data['aggregateRating']
                        if 'ratingValue' in rating_info:
                            product_data['rating'] = float(rating_info['ratingValue'])
                        if 'reviewCount' in rating_info:
                            product_data['review_count'] = int(rating_info['reviewCount'])
                    if 'offers' in json_ld_data:
                        offer = json_ld_data['offers']
                        if isinstance(offer, list) and len(offer) > 0:
                            offer = offer[0]
                        if 'price' in offer:
                            try:
                                product_data['price'] = float(offer['price'])
                            except (ValueError, TypeError):
                                pass
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    
    # Extract specifications - look for structured data sections
    # Try to find specification tables or lists
    spec_patterns = [
        (r'<dt[^>]*>Scent</dt>\s*<dd[^>]*>([^<]+)</dd>', 'Scent'),
        (r'<dt[^>]*>Net content statement</dt>\s*<dd[^>]*>([^<]+)</dd>', 'Net content'),
        (r'<dt[^>]*>Household cleaner type</dt>\s*<dd[^>]*>([^<]+)</dd>', 'Type'),
        (r'<dt[^>]*>Features</dt>\s*<dd[^>]*>([^<]+)</dd>', 'Features'),
        (r'<dt[^>]*>Weight</dt>\s*<dd[^>]*>([^<]+)</dd>', 'Weight'),
        (r'<dt[^>]*>Cleanser form</dt>\s*<dd[^>]*>([^<]+)</dd>', 'Form'),
    ]
    
    for pattern, key in spec_patterns:
        match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
        if match:
            value = match.group(1).strip()
            # Clean up HTML entities and extra whitespace
            value = re.sub(r'&[^;]+;', ' ', value)
            value = re.sub(r'\s+', ' ', value).strip()
            # Skip if it looks like JavaScript or invalid data
            if value and len(value) < 200 and not value.startswith('{') and 'function' not in value.lower():
                product_data['specifications'][key] = value
    
    # Extract net content from visible text (e.g., "41 fl oz")
    if 'Net content' not in product_data['specifications']:
        net_content_match = re.search(r'(\d+\s*(?:fl\s*oz|oz|fl\.?\s*oz))', html_content, re.IGNORECASE)
        if net_content_match:
            product_data['specifications']['Net content'] = net_content_match.group(1)
    
    # Extract scent from visible text patterns
    if 'Scent' not in product_data['specifications'] or not product_data['specifications']['Scent']:
        scent_patterns = [
            r'Meadows\s*[&\s]*Rain',
            r'Lavender',
            r'Lemon',
            r'Gain',
            r'Unstopables',
        ]
        for pattern in scent_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                product_data['specifications']['Scent'] = match.group(0)
                break
    
    # Extract ingredients - look for ingredient list pattern
    # Pattern: Water followed by chemical names ending with Colorants or Fragrances
    ingredient_pattern = r'(Water[^<]{100,800}(?:Colorants|Fragrances)[^<]*)'
    ingredient_match = re.search(ingredient_pattern, html_content, re.IGNORECASE | re.DOTALL)
    
    if ingredient_match:
        ingredients_text = ingredient_match.group(1)
        # Remove HTML tags and clean up
        ingredients_text = re.sub(r'<[^>]+>', ', ', ingredients_text)
        ingredients_text = re.sub(r'&amp;', '&', ingredients_text)
        ingredients_text = re.sub(r'&nbsp;', ' ', ingredients_text)
        ingredients_text = re.sub(r'\s+', ' ', ingredients_text)
        ingredients_text = re.sub(r',\s*,', ',', ingredients_text)
        ingredients_text = ingredients_text.strip()
        
        # Extract just the ingredient list (before any JSON or extra text)
        # Look for the pattern: Water, ...chemicals..., Colorants
        # Try to find a clean list ending with Colorants or Fragrances
        ingredient_list_match = re.search(
            r'(Water[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*Colorants?)',
            ingredients_text, re.IGNORECASE
        )
        if ingredient_list_match:
            product_data['ingredients'] = ingredient_list_match.group(1).strip()
        else:
            # Try simpler pattern - just get everything up to Colorants
            simple_match = re.search(r'(Water[^}]{50,400}Colorants?)', ingredients_text, re.IGNORECASE)
            if simple_match:
                clean_ingredients = simple_match.group(1)
                # Remove any JSON-like structures
                clean_ingredients = re.sub(r'["\']\s*:\s*["\']', '', clean_ingredients)
                clean_ingredients = re.sub(r'["\']', '', clean_ingredients)
                clean_ingredients = re.sub(r'\s+', ' ', clean_ingredients).strip()
                if len(clean_ingredients) > 50 and len(clean_ingredients) < 500:
                    product_data['ingredients'] = clean_ingredients
    
    # Extract directions/instructions - look for FLOORS pattern or Instructions section
    # Try to find the full directions text
    directions_patterns = [
        r'FLOORS[^<]{100,1000}(?:Rinse|Wipe|Not recommended)',
        r'(?:Directions|Instructions)[^<]*:?\s*([^<]{50,1500})',
    ]
    
    for pattern in directions_patterns:
        directions_match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
        if directions_match:
            directions_text = directions_match.group(1) if directions_match.groups() else directions_match.group(0)
            
            # Remove HTML tags
            directions_text = re.sub(r'<[^>]+>', ' ', directions_text)
            # Decode HTML entities
            directions_text = re.sub(r'&amp;', '&', directions_text)
            directions_text = re.sub(r'&nbsp;', ' ', directions_text)
            directions_text = re.sub(r'\s+', ' ', directions_text).strip()
            
            # Check if it contains direction keywords
            direction_keywords = ['FLOORS', 'DILUTE', 'Mix', 'cup', 'gallon', 'bucket', 'water', 'Rinse', 'Wipe']
            has_directions = any(keyword.lower() in directions_text.lower() for keyword in direction_keywords)
            
            if has_directions and len(directions_text) > 30 and not directions_text.startswith('{'):
                # Clean up common prefixes
                directions_text = re.sub(r'^(?:Directions|Instructions)[:\s]*', '', directions_text, flags=re.IGNORECASE)
                # Extract the main directions (before any extra text)
                # Look for pattern: FLOORS/DILUTE CLEANING: ... instructions ...
                main_directions = re.search(r'(FLOORS[^<]{50,800})', directions_text, re.IGNORECASE)
                if main_directions:
                    product_data['directions'] = main_directions.group(1).strip()[:2000]
                else:
                    product_data['directions'] = directions_text[:2000]
                break
    
    # Extract image URLs
    image_patterns = [
        r'src=["\'](https://i5\.walmartimages\.com[^"\']+\.(?:jpg|jpeg|png|webp))["\']',
        r'data-src=["\'](https://i5\.walmartimages\.com[^"\']+\.(?:jpg|jpeg|png|webp))["\']',
        r'url\(["\']?(https://i5\.walmartimages\.com[^"\']+\.(?:jpg|jpeg|png|webp))["\']?\)',
    ]
    
    seen_images = set()
    for pattern in image_patterns:
        matches = re.findall(pattern, html_content, re.IGNORECASE)
        for img_url in matches:
            if img_url not in seen_images:
                seen_images.add(img_url)
                product_data['image_urls'].append(img_url)
    
    # Extract availability information
    availability_patterns = [
        (r'In stock|Available', 'in_stock'),
        (r'Out of stock|Not available', 'out_of_stock'),
        (r'Limited availability', 'limited'),
    ]
    
    for pattern, status in availability_patterns:
        if re.search(pattern, html_content, re.IGNORECASE):
            product_data['availability'] = status
            break
    
    # Look for store-specific availability
    if 'Pickup' in html_content or 'pickup' in html_content.lower():
        product_data['store_availability'] = 'pickup_available'
    if 'Delivery' in html_content or 'delivery' in html_content.lower():
        if product_data['store_availability']:
            product_data['store_availability'] += ', delivery_available'
        else:
            product_data['store_availability'] = 'delivery_available'
    
    return product_data


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
