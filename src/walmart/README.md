# Walmart Store Product Fetcher

A Python tool to fetch store-specific product data from Walmart.com by parsing HTML search results (similar to the ALDI approach, but using HTML parsing since Walmart uses client-side rendering).

## Current Status

✅ **IMPLEMENTED**: This module parses Walmart.com search pages to extract product information. It works by:
1. Making requests to Walmart search URLs with store filters
2. Parsing the HTML response to extract product data
3. Extracting product IDs, names, URLs, and other information

## Approach

This module uses HTML parsing to extract product data from Walmart.com search pages, since:
- Walmart uses client-side rendering (Next.js/React)
- Product data is embedded in the HTML or loaded via JavaScript
- Direct API endpoints require authentication/partnership
- HTML parsing allows us to extract product information without API access

## How It Works

1. **Search URL Format**: `https://www.walmart.com/search?q=QUERY&store=STORE_ID&page=PAGE`
2. **HTML Parsing**: Extracts product information from:
   - Product links (`/ip/Product-Name/ITEM_ID`)
   - Embedded JSON data in script tags
   - HTML attributes and data structures
3. **Store Filtering**: Uses `store` parameter in search URL to filter by store ID
4. **Pagination**: Iterates through pages to fetch more products

## Usage

### Basic Product Search

```python
from walmart.api_client import create_session
from walmart.product_fetcher import fetch_products_by_search
from walmart.config import DEFAULT_STORE_ID

session = create_session()
products = fetch_products_by_search(
    query='milk',
    store_id=DEFAULT_STORE_ID,
    session=session,
    max_products=100
)

print(f"Found {len(products)} products")
```

### Fetch Store Products

```python
from walmart.product_fetcher import fetch_store_products

# Searches for common products at the store
store_products = fetch_store_products(store_id=1426)
```

### Running the Script

```bash
# From project root
python -m src.walmart.fetch_store_products
```

## Important Notes

⚠️ **Bot Protection**: Walmart.com uses bot protection (PerimeterX). You may encounter:
- 412 status codes (request blocked)
- CAPTCHA challenges
- Rate limiting

**Solutions**:
- Add delays between requests
- Use realistic browser headers (already implemented)
- Handle errors gracefully
- Consider using a headless browser (Selenium/Playwright) for more complex scenarios

## Project Structure

```
walmart/
├── __init__.py
├── config.py              # API endpoints (to be determined)
├── api_client.py          # HTTP client with headers (similar to ALDI)
├── product_fetcher.py     # Product fetching functions (placeholder)
└── README.md              # This file
```

## Next Steps

1. Use browser DevTools to capture actual API calls
2. Identify the search/product API endpoint
3. Understand request/response format
4. Implement product fetching functions
5. Add store filtering capability
6. Test with store 1426 (zipcode 41101)

## Similar to ALDI Module

This module follows the same pattern as the ALDI module:
- No authentication required
- Uses public/internal APIs
- Browser-like headers
- Session management with retries
- Pagination handling

Once the actual API endpoints are identified, the implementation will mirror the ALDI approach.
