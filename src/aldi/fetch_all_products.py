import os
import logging
import pandas as pd
from tqdm.auto import tqdm

from .product_fetcher import (
    fetch_all_products,
    fetch_products_by_category,
    fetch_product_details,
    extract_category_keys_from_details,
)
from .api_client import create_session

today = pd.Timestamp("today").strftime("%Y_%m_%d")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def main():
    # Directories and file paths - save to public/aldi/
    output_dir = "public/aldi/"
    os.makedirs(output_dir, exist_ok=True)
    json_file = f"{output_dir}aldi_products_detailed.json"
    
    # Step 1: Fetch first 1000 products
    print("Step 1: Fetching first 1000 products...")
    all_products_df = fetch_all_products()
    print(f"Fetched {len(all_products_df)} products from initial pagination")
    
    # Step 2: Fetch product details to extract categories
    print("\nStep 2: Fetching product details to extract categories...")
    detailed_info = []
    for sku in tqdm(all_products_df['sku'], desc="Hydrating products"):
        details = fetch_product_details(sku)
        detailed_info.append(details)
    
    detailed_df = pd.DataFrame(detailed_info)
    full_df = all_products_df.merge(detailed_df, on='sku', how='left')
    
    # Step 3: Extract category keys and fetch products by category
    print("\nStep 3: Extracting categories and fetching products by category...")
    discovered_categories = extract_category_keys_from_details(detailed_df)
    fetched_categories = set()
    all_category_products = []
    fetched_skus = set(all_products_df['sku'].tolist())  # Track SKUs to avoid duplicates
    
    print(f"Discovered {len(discovered_categories)} unique categories from initial products: {sorted(discovered_categories)[:10]}...")
    
    # Create a shared session for category fetching
    category_session = create_session()
    
    # Iterative category discovery
    categories_to_fetch = discovered_categories.copy()
    iteration = 0
    max_iterations = 10  # Safety limit to prevent infinite loops
    
    while categories_to_fetch and iteration < max_iterations:
        iteration += 1
        print(f"\nIteration {iteration}: Fetching products for {len(categories_to_fetch)} categories...")
        
        new_categories = set()
        current_batch = list(categories_to_fetch)
        categories_to_fetch = set()
        
        for category_key in tqdm(current_batch, desc=f"Fetching category products (iter {iteration})"):
            if category_key in fetched_categories:
                continue
                
            fetched_categories.add(category_key)
            
            # Fetch products for this category
            category_products_df = fetch_products_by_category(category_key, session=category_session)
            
            if len(category_products_df) > 0:
                # Filter out products we've already seen
                new_products = category_products_df[~category_products_df['sku'].isin(fetched_skus)]
                
                if len(new_products) > 0:
                    all_category_products.append(new_products)
                    fetched_skus.update(new_products['sku'].tolist())
                    
                    # Fetch details for new products to discover more categories
                    print(f"  Fetching details for {len(new_products)} new products from category {category_key}...")
                    for sku in tqdm(new_products['sku'], desc=f"  Details for cat {category_key}", leave=False):
                        details = fetch_product_details(sku)
                        if 'category_keys' in details and isinstance(details['category_keys'], list):
                            for cat_key in details['category_keys']:
                                if cat_key and str(cat_key).strip():  # Only add non-empty category keys
                                    if cat_key not in fetched_categories and cat_key not in discovered_categories:
                                        new_categories.add(cat_key)
        
        # Add newly discovered categories to the queue
        if new_categories:
            print(f"  Discovered {len(new_categories)} new categories")
            discovered_categories.update(new_categories)
            categories_to_fetch.update(new_categories)
        else:
            print("  No new categories discovered")
    
    # Step 4: Combine all products and deduplicate
    print(f"\nStep 4: Combining and deduplicating products...")
    if all_category_products:
        category_products_df = pd.concat(all_category_products, ignore_index=True)
        # Final deduplication by SKU
        category_products_df = category_products_df.drop_duplicates(subset=['sku'], keep='first')
        print(f"Fetched {len(category_products_df)} additional products from categories")
        
        # Fetch details for category products
        print("Fetching details for category products...")
        category_detailed_info = []
        for sku in tqdm(category_products_df['sku'], desc="Hydrating category products"):
            details = fetch_product_details(sku)
            category_detailed_info.append(details)
        
        category_detailed_df = pd.DataFrame(category_detailed_info)
        category_full_df = category_products_df.merge(category_detailed_df, on='sku', how='left')
        
        # Combine with initial products
        full_df = pd.concat([full_df, category_full_df], ignore_index=True)
        # Final deduplication
        full_df = full_df.drop_duplicates(subset=['sku'], keep='first')
    else:
        print("No additional products found from categories")
    
    print(f"\nTotal products fetched: {len(full_df)}")
    
    # Clean up category_keys column for final output (it's a list, not ideal for CSV)
    if 'category_keys' in full_df.columns:
        full_df = full_df.drop(columns=['category_keys'])

    # Save to public/aldi/
    full_df.to_json(json_file, orient='records', indent=4)

    print(f"Data saved to {json_file}. Process completed.")


if __name__ == "__main__":
    main()
