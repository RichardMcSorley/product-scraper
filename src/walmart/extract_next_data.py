"""Script to extract and display __NEXT_DATA__ from a Walmart product page."""
import sys
import json
import re
from pathlib import Path

from .api_client import create_session


def extract_next_data(item_id, store_id=None):
    """Extract __NEXT_DATA__ from Walmart product page.
    
    Args:
        item_id: Walmart item ID
        store_id: Optional store ID
    
    Returns:
        dict: Parsed __NEXT_DATA__ JSON
    """
    session = create_session()
    url = f'https://www.walmart.com/ip/{item_id}'
    params = {}
    
    if store_id:
        params['store'] = store_id
        params['fulfillmentIntent'] = 'In-store'
    
    response = session.get(url, params=params, timeout=15)
    
    if response.status_code != 200:
        print(f"Error: Status code {response.status_code}")
        return None
    
    # Extract __NEXT_DATA__
    next_data_pattern = r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>'
    match = re.search(next_data_pattern, response.text, re.DOTALL)
    
    if not match:
        print("__NEXT_DATA__ not found in page")
        return None
    
    try:
        next_data = json.loads(match.group(1))
        return next_data
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return None


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python -m src.walmart.extract_next_data <item_id> [store_id]")
        print("\nExample:")
        print("  python -m src.walmart.extract_next_data 2274077370")
        print("  python -m src.walmart.extract_next_data 2274077370 1426")
        sys.exit(1)
    
    item_id = sys.argv[1]
    store_id = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    print(f"Extracting __NEXT_DATA__ for item ID: {item_id}")
    if store_id:
        print(f"Store ID: {store_id}")
    print("="*60)
    
    next_data = extract_next_data(item_id, store_id)
    
    if next_data:
        # Save to file
        output_file = Path(f'public/walmart/next_data_{item_id}.json')
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(next_data, f, indent=2)
        
        print(f"\n✓ __NEXT_DATA__ saved to: {output_file}")
        print(f"\nTop-level keys: {list(next_data.keys())}")
        
        # Show structure
        if 'props' in next_data:
            print(f"\nprops keys: {list(next_data['props'].keys())}")
            if 'pageProps' in next_data['props']:
                print(f"pageProps keys: {list(next_data['props']['pageProps'].keys())}")
        
        print(f"\nFull JSON ({len(json.dumps(next_data))} characters) saved to file.")
        print("View the file to see complete structure.")
    else:
        print("\n⚠️  Failed to extract __NEXT_DATA__")


if __name__ == '__main__':
    main()
