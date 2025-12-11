"""Script to fetch detailed product information from a Walmart product page."""
import sys
import json
from pathlib import Path

from .api_client import create_session
from .product_fetcher import fetch_product_details
from .config import DEFAULT_STORE_ID


def main():
    """Fetch product details for a specific item."""
    if len(sys.argv) < 2:
        print("Usage: python -m src.walmart.fetch_product <item_id> [store_id]")
        print("\nExample:")
        print("  python -m src.walmart.fetch_product 2274077370")
        print("  python -m src.walmart.fetch_product 2274077370 1426")
        sys.exit(1)
    
    item_id = sys.argv[1]
    store_id = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_STORE_ID
    
    print(f"Fetching product details for item ID: {item_id}")
    if store_id:
        print(f"Store ID: {store_id} (for store-specific availability)")
    print("="*60)
    
    session = create_session()
    product_data = fetch_product_details(item_id, store_id=store_id, session=session)
    
    if product_data:
        print("\nProduct Details:")
        print("="*60)
        print(f"Item ID: {product_data.get('item_id')}")
        print(f"Name: {product_data.get('name', 'N/A')}")
        print(f"Price: ${product_data.get('price', 'N/A')}")
        if product_data.get('price_per_unit'):
            print(f"Price per unit: {product_data.get('price_per_unit')}")
        if product_data.get('rating'):
            print(f"Rating: {product_data.get('rating')} stars ({product_data.get('review_count', 0)} reviews)")
        print(f"Availability: {product_data.get('availability', 'N/A')}")
        if product_data.get('store_availability'):
            print(f"Store Availability: {product_data.get('store_availability')}")
        
        if product_data.get('description'):
            print(f"\nDescription:")
            print(f"  {product_data.get('description')[:200]}...")
        
        if product_data.get('specifications'):
            print(f"\nSpecifications:")
            for key, value in product_data.get('specifications', {}).items():
                print(f"  {key}: {value}")
        
        if product_data.get('ingredients'):
            print(f"\nIngredients:")
            print(f"  {product_data.get('ingredients')[:200]}...")
        
        if product_data.get('directions'):
            print(f"\nDirections:")
            print(f"  {product_data.get('directions')[:200]}...")
        
        if product_data.get('image_urls'):
            print(f"\nImages: {len(product_data.get('image_urls', []))} found")
            for i, img_url in enumerate(product_data.get('image_urls', [])[:3], 1):
                print(f"  {i}. {img_url}")
        
        print(f"\nProduct URL: {product_data.get('product_url')}")
        
        # Save to JSON file
        output_file = Path(f'public/walmart/product_{item_id}.json')
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(product_data, f, indent=2)
        
        print(f"\n✓ Full product data saved to: {output_file}")
    else:
        print("\n⚠️  Failed to fetch product details")
        print("This could be due to:")
        print("  - Invalid item ID")
        print("  - Walmart bot protection blocking the request")
        print("  - Network error")


if __name__ == '__main__':
    main()
