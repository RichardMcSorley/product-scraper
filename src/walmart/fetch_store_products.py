"""Main script to fetch products for a specific Walmart store."""
import os
import logging
import pandas as pd
from pathlib import Path

from .api_client import create_session
from .product_fetcher import (
    fetch_products_by_search,
    fetch_store_products,
)
from .config import DEFAULT_STORE_ID, DEFAULT_ZIPCODE

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def main():
    """Main function to fetch products for store 1426."""
    print("="*60)
    print("Walmart Store Product Fetcher")
    print(f"Store: {DEFAULT_STORE_ID} (Zipcode: {DEFAULT_ZIPCODE})")
    print("="*60)
    
    # Create session
    session = create_session()
    
    # Option 1: Search for specific products
    print("\n1. Testing product search...")
    print("   Searching for 'milk' at store 1426...")
    
    try:
        products = fetch_products_by_search(
            query='milk',
            store_id=DEFAULT_STORE_ID,
            session=session,
            max_products=50
        )
        
        if not products.empty:
            print(f"   ✓ Found {len(products)} products")
            print(f"   Sample products:")
            for idx, row in products.head(5).iterrows():
                print(f"     - {row.get('name', 'N/A')} (ID: {row.get('item_id', 'N/A')})")
        else:
            print("   ⚠ No products found. Walmart may be blocking requests.")
            print("   Note: Walmart uses bot protection. You may need to:")
            print("     - Add delays between requests")
            print("     - Use more realistic browser headers")
            print("     - Handle CAPTCHA challenges")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        logging.exception("Search failed")
    
    # Option 2: Fetch store products (multiple searches)
    print("\n2. Fetching store products (multiple searches)...")
    print("   This will search for common products at the store...")
    
    try:
        store_products = fetch_store_products(
            store_id=DEFAULT_STORE_ID,
            session=session
        )
        
        if not store_products.empty:
            print(f"   ✓ Found {len(store_products)} unique products")
            
            # Save to file
            output_dir = Path('public/walmart')
            output_dir.mkdir(parents=True, exist_ok=True)
            
            csv_path = output_dir / f'walmart_store_{DEFAULT_STORE_ID}_products.csv'
            json_path = output_dir / f'walmart_store_{DEFAULT_STORE_ID}_products.json'
            
            store_products.to_csv(csv_path, index=False)
            store_products.to_json(json_path, orient='records', indent=2)
            
            print(f"   ✓ Saved to:")
            print(f"     - {csv_path}")
            print(f"     - {json_path}")
        else:
            print("   ⚠ No products found")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        logging.exception("Store products fetch failed")
    
    print("\n" + "="*60)
    print("Done!")
    print("="*60)


if __name__ == '__main__':
    main()
