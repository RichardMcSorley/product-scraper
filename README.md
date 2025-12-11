# Product Scraper

A Python tool to fetch and aggregate product data from various retail chains. Currently only ALDI is supported.

## Features

- Fetches products from ALDI US API with pagination support
- Discovers products through category exploration
- Handles rate limiting and retries failed requests
- Extracts detailed product information including categories, descriptions, and images
- Saves results in JSON format

## Requirements

- Python 3.7+
- Required packages:
  - `pandas`
  - `requests`
  - `tqdm`

## Installation

Install required dependencies:
   ```bash
   pip install pandas requests tqdm
   ```

## Usage

### Running the Script

From the project root directory, run:

```bash
python src/aldi/fetch_all_products.py
```

### What the Script Does

The script performs the following steps:

1. **Initial Product Fetch**: Fetches the first 1000 products from ALDI's product search API
2. **Product Details**: Retrieves detailed information for each product (categories, descriptions, images, etc.)
3. **Category Discovery**: Extracts category keys from products and fetches additional products by category
4. **Iterative Discovery**: Continues discovering new categories and products up to 10 iterations
5. **Data Aggregation**: Combines all products, removes duplicates, and saves to output files

### Output

The script saves two files to `public/aldi/`:

- `aldi_products_detailed.json` - Product data in JSON format

The output directory (`public/aldi/`) will be created automatically if it doesn't exist.

## Project Structure

```
aldi/
├── src/
│   └── aldi/
│       ├── __init__.py           # Package exports
│       ├── api_client.py          # HTTP session and header utilities
│       ├── config.py              # API configuration constants
│       ├── product_fetcher.py     # Core product fetching functions
│       └── fetch_all_products.py  # Main script entry point
├── public/
│   └── aldi/                      # Output directory (created on run)
│       └── aldi_products_detailed.json
└── README.md
```

## Configuration

Default settings can be modified in `src/aldi/config.py`:

- `DEFAULT_SERVICE_POINT`: Store location ID (default: '440-018')
- `DEFAULT_LIMIT`: Products per page (default: 60)
- `MAX_PRODUCTS`: Maximum products to fetch (default: 1000)

## Notes

- The script includes rate limiting handling and will retry failed requests
- Product fetching is capped at 1000 products to avoid API errors
- Category discovery is limited to 10 iterations to prevent infinite loops
- The script uses exponential backoff for retries when rate limited
