"""Product fetching functions for ALDI API."""
import logging
import time
import ast
import requests
import pandas as pd
from tqdm.auto import tqdm

from .config import (
    BASE_URL,
    PRODUCT_DETAILS_BASE_URL,
    DEFAULT_SERVICE_POINT,
    DEFAULT_LIMIT,
    MAX_PRODUCTS,
    DEFAULT_PARAMS,
)
from .api_client import create_session, get_default_headers, get_product_details_headers


def extract_product_data(product):
    """Extract product data from API response (single source of truth).
    
    Args:
        product: Product dictionary from API response
    
    Returns:
        Dictionary with extracted product fields
    """
    return {
        'sku': product['sku'],
        'name': product['name'],
        'brand_name': product['brandName'],
        'price_unit': product.get('sellingSize', 'N/A'),
        'slug': product['urlSlugText'],
        'formatted_price': product.get('price', {}).get('amountRelevantDisplay', 'N/A'),
        'snap_eligible': product.get('countryExtensions', {}).get('usSnapEligible', False)
    }


def fetch_all_products(service_point=None, session=None):
    """Fetches all products from the ALDI API with pagination handling, rate limiting, and retry logic.
    
    Args:
        service_point: Service point ID (defaults to DEFAULT_SERVICE_POINT)
        session: Optional requests session to reuse (creates new if None)
    
    Returns:
        DataFrame with all products
    """
    if service_point is None:
        service_point = DEFAULT_SERVICE_POINT
    
    if session is None:
        session = create_session()
    
    params = DEFAULT_PARAMS.copy()
    params.update({
        'limit': DEFAULT_LIMIT,
        'offset': 0,
        'servicePoint': service_point,
    })
    
    # Initial request to get total count
    response = session.get(BASE_URL, params=params)
    response.raise_for_status()
    data = response.json()

    pagination = data['meta']['pagination']
    total_count = pagination['totalCount']
    products = []

    # Cap pagination at MAX_PRODUCTS to avoid API error
    max_offset = min(MAX_PRODUCTS, total_count)
    
    # Calculate number of pages needed (capped at MAX_PRODUCTS)
    num_pages = (max_offset + DEFAULT_LIMIT - 1) // DEFAULT_LIMIT  # Ceiling division
    
    logging.info(f"Total products available: {total_count}, fetching first {max_offset} products ({num_pages} pages)")
    
    # Track failed pages to retry later
    failed_pages = []

    # First pass: try all pages, skip failures
    for page in tqdm(range(num_pages), desc="Fetching products"):
        params['offset'] = page * DEFAULT_LIMIT
        
        try:
            response = session.get(BASE_URL, params=params)
            
            if response.status_code == 403:
                # Skip on first failure, add to retry list
                tqdm.write(f"Rate limited (403) on page {page + 1}. Skipping for now, will retry later.")
                failed_pages.append(page)
                continue
            
            response.raise_for_status()
            
            # Try to parse JSON, catch decode errors
            try:
                page_data = response.json()
            except (ValueError, KeyError) as json_error:
                tqdm.write(f"JSON decode error on page {page + 1}: {json_error}. Response status: {response.status_code}, Response text: {response.text[:200]}. Skipping for now, will retry later.")
                failed_pages.append(page)
                continue
            
            # Check if data key exists
            if 'data' not in page_data:
                tqdm.write(f"Missing 'data' key in response on page {page + 1}. Response keys: {list(page_data.keys())}. Skipping for now, will retry later.")
                failed_pages.append(page)
                continue
            
            for product in page_data['data']:
                products.append(extract_product_data(product))
                
        except requests.exceptions.RequestException as e:
            # Skip on first failure, add to retry list
            tqdm.write(f"Request error on page {page + 1}: {type(e).__name__}: {e}. Skipping for now, will retry later.")
            failed_pages.append(page)
            continue
        except Exception as e:
            # Catch any other unexpected errors
            tqdm.write(f"Unexpected error on page {page + 1}: {type(e).__name__}: {e}. Skipping for now, will retry later.")
            logging.error(f"Unexpected error on page {page + 1}: {type(e).__name__}: {e}", exc_info=True)
            failed_pages.append(page)
            continue

    # Second pass: retry failed pages with fresh session
    if failed_pages:
        tqdm.write(f"\nRetrying {len(failed_pages)} failed pages...")
        # Recreate session for retries in case session state was corrupted
        retry_session = create_session()
        
        for page in tqdm(failed_pages, desc="Retrying failed pages"):
            params['offset'] = page * DEFAULT_LIMIT
            
            max_retries = 3
            retry_count = 0
            success = False
            
            while retry_count < max_retries and not success:
                try:
                    response = retry_session.get(BASE_URL, params=params)
                    
                    if response.status_code == 403:
                        retry_count += 1
                        if retry_count < max_retries:
                            wait_time = 60 * retry_count  # 60s, 120s, 180s
                            tqdm.write(f"Rate limited (403) on page {page + 1}. Waiting {wait_time}s before retry {retry_count}/{max_retries}...")
                            time.sleep(wait_time)
                            continue
                        else:
                            tqdm.write(f"Rate limited (403) on page {page + 1} after {max_retries} retries. Skipping.")
                            logging.warning(f"Rate limited at page {page + 1}, offset {params['offset']}. Skipping.")
                            break
                    
                    response.raise_for_status()
                    
                    # Try to parse JSON, catch decode errors
                    try:
                        page_data = response.json()
                    except (ValueError, KeyError) as json_error:
                        retry_count += 1
                        if retry_count < max_retries:
                            wait_time = (2 ** retry_count) * 5
                            tqdm.write(f"JSON decode error on page {page + 1}: {json_error}. Waiting {wait_time}s before retry {retry_count}/{max_retries}...")
                            time.sleep(wait_time)
                            continue
                        else:
                            tqdm.write(f"JSON decode error on page {page + 1} after {max_retries} retries. Skipping.")
                            logging.error(f"JSON decode error on page {page + 1}: {json_error}")
                            break
                    
                    # Check if data key exists
                    if 'data' not in page_data:
                        retry_count += 1
                        if retry_count < max_retries:
                            wait_time = (2 ** retry_count) * 5
                            tqdm.write(f"Missing 'data' key on page {page + 1}. Waiting {wait_time}s before retry {retry_count}/{max_retries}...")
                            time.sleep(wait_time)
                            continue
                        else:
                            tqdm.write(f"Missing 'data' key on page {page + 1} after {max_retries} retries. Skipping.")
                            logging.error(f"Missing 'data' key on page {page + 1}. Response keys: {list(page_data.keys())}")
                            break
                    
                    for product in page_data['data']:
                        products.append(extract_product_data(product))
                    
                    success = True
                    
                except requests.exceptions.RequestException as e:
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = (2 ** retry_count) * 5
                        tqdm.write(f"Request error on page {page + 1}: {type(e).__name__}: {e}. Waiting {wait_time}s before retry {retry_count}/{max_retries}...")
                        time.sleep(wait_time)
                    else:
                        tqdm.write(f"Failed to fetch page {page + 1} after {max_retries} retries: {type(e).__name__}: {e}")
                        logging.error(f"Failed to fetch page {page + 1}: {type(e).__name__}: {e}")
                        break
                except Exception as e:
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = (2 ** retry_count) * 5
                        tqdm.write(f"Unexpected error on page {page + 1}: {type(e).__name__}: {e}. Waiting {wait_time}s before retry {retry_count}/{max_retries}...")
                        time.sleep(wait_time)
                    else:
                        tqdm.write(f"Unexpected error on page {page + 1} after {max_retries} retries: {type(e).__name__}: {e}. Skipping.")
                        logging.error(f"Unexpected error on page {page + 1}: {type(e).__name__}: {e}", exc_info=True)
                        break

    return pd.DataFrame(products)


def fetch_products_by_category(category_key, service_point=None, session=None, max_products=1000):
    """Fetch products filtered by a specific category key.
    
    Args:
        category_key: The category key/ID to filter by
        service_point: Service point ID (defaults to DEFAULT_SERVICE_POINT)
        session: Optional requests session to reuse (creates new if None)
        max_products: Maximum number of products to fetch (default 1000 to avoid API limit)
    
    Returns:
        DataFrame with products from the category
    """
    if service_point is None:
        service_point = DEFAULT_SERVICE_POINT
    
    if session is None:
        session = create_session()
    
    limit = 12
    params = DEFAULT_PARAMS.copy()
    params.update({
        'limit': limit,
        'offset': 0,
        'servicePoint': service_point,
        'categoryKey': str(category_key)  # Try categoryKey parameter
    })
    
    products = []
    
    try:
        # Initial request to get total count for this category
        response = session.get(BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        pagination = data.get('meta', {}).get('pagination', {})
        total_count = pagination.get('totalCount', 0)
        
        # Cap at max_products to avoid API limit
        max_offset = min(max_products, total_count)
        num_pages = (max_offset + limit - 1) // limit
        
        logging.info(f"Category {category_key}: {total_count} products available, fetching up to {max_offset} ({num_pages} pages)")
        
        # Fetch all pages for this category
        for page in range(num_pages):
            params['offset'] = page * limit
            
            try:
                response = session.get(BASE_URL, params=params)
                
                if response.status_code == 403:
                    logging.warning(f"Rate limited (403) on category {category_key}, page {page + 1}. Skipping remaining pages.")
                    break
                
                response.raise_for_status()
                page_data = response.json()
                
                if 'data' not in page_data:
                    logging.warning(f"Missing 'data' key in response for category {category_key}, page {page + 1}")
                    break
                
                for product in page_data['data']:
                    products.append(extract_product_data(product))
                    
            except requests.exceptions.RequestException as e:
                logging.warning(f"Request error on category {category_key}, page {page + 1}: {e}. Skipping remaining pages.")
                break
            except Exception as e:
                logging.warning(f"Unexpected error on category {category_key}, page {page + 1}: {e}. Skipping remaining pages.")
                break
                
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch products for category {category_key}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error fetching products for category {category_key}: {e}")
    
    return pd.DataFrame(products)


def extract_category_keys_from_details(detailed_info):
    """Extract unique category keys from product details.
    
    Args:
        detailed_info: List of product detail dictionaries (from fetch_product_details) or DataFrame
    
    Returns:
        Set of unique category keys
    """
    category_keys = set()
    
    # Handle both list of dicts and DataFrame
    if isinstance(detailed_info, pd.DataFrame):
        for idx, row in detailed_info.iterrows():
            cat_keys = row.get('category_keys', [])
            if isinstance(cat_keys, list):
                category_keys.update(cat_keys)
            elif isinstance(cat_keys, str):
                # Handle case where it might be stored as string representation
                try:
                    cat_keys = ast.literal_eval(cat_keys)
                    if isinstance(cat_keys, list):
                        category_keys.update(cat_keys)
                except:
                    pass
    else:
        # List of dictionaries
        for detail in detailed_info:
            if 'category_keys' in detail and isinstance(detail['category_keys'], list):
                category_keys.update(detail['category_keys'])
    
    # Filter out empty/None values
    category_keys = {k for k in category_keys if k and str(k).strip()}
    return category_keys


def fetch_product_details(sku, service_point=None, max_retries=3):
    """Fetch detailed product information based on SKU with retry logic.
    
    Args:
        sku: Product SKU
        service_point: Service point ID (defaults to DEFAULT_SERVICE_POINT)
        max_retries: Maximum number of retry attempts
    
    Returns:
        Dictionary with product details
    """
    if service_point is None:
        service_point = DEFAULT_SERVICE_POINT
    
    headers = get_product_details_headers()
    product_details_url = f'{PRODUCT_DETAILS_BASE_URL}/{sku}'
    product_params = {'servicePoint': service_point, 'serviceType': 'pickup'}
    
    empty_result = {
        'sku': sku,
        'description': '',
        'categories': '',
        'category_keys': [],
        'country_origin': '',
        'image_url': None,
        'warning_code': None,
        'warning_desc': None
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.get(product_details_url, headers=headers, params=product_params)
            
            if response.status_code == 403:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 2  # Exponential backoff: 2s, 4s, 8s
                    time.sleep(wait_time)
                    continue
                else:
                    logging.warning(f"Rate limited (403) when fetching details for SKU {sku} after {max_retries} retries")
                    return empty_result
            
            response.raise_for_status()
            product_data = response.json()['data']

            # Extract category keys and names
            category_list = product_data.get('categories', [])
            category_keys = [cat.get('key', cat.get('id', '')) for cat in category_list if cat.get('key') or cat.get('id')]
            category_names = [cat.get('name', '') for cat in category_list if cat.get('name')]
            
            return {
                'sku': product_data['sku'],
                'description': product_data.get('description', ''),
                'categories': ', '.join(category_names),
                'category_keys': category_keys,  # Store category keys for filtering
                'country_origin': product_data.get('countryOrigin', ''),
                'image_url': product_data['assets'][0]['url'] if product_data.get('assets') and len(product_data['assets']) > 0 else None,
                'warning_code': product_data['warnings'][0]['key'] if product_data.get('warnings') and len(product_data['warnings']) > 0 else None,
                'warning_desc': product_data['warnings'][0]['message'] if product_data.get('warnings') and len(product_data['warnings']) > 0 else None
            }
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 2
                time.sleep(wait_time)
            else:
                logging.error(f"Failed to fetch details for SKU {sku} after {max_retries} retries: {e}")
                return empty_result
    
    # Fallback return (shouldn't reach here, but just in case)
    return empty_result
