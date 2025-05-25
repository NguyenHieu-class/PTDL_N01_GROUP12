from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
import csv
import os
from bs4 import BeautifulSoup


def extract_product_info(html_content):
    """Extract product information from the page HTML using BeautifulSoup."""
    soup = BeautifulSoup(html_content, 'html.parser')

    # Find all product items - Lazada's product grid items have class 'Bm3ON'
    product_items = soup.select('.Bm3ON')  # Main product card container

    print(f"Found {len(product_items)} product items")

    products = []

    for item in product_items:
        try:
            product = {}

            # Extract product URL - look for all links and find the product link
            links = item.select('a')
            for link in links:
                href = link.get('href')
                if href and ('/products/' in href or 'i' + str(item.get('data-item-id', '')) in href):
                    product['url'] = href
                    # Fix URL format - remove duplicate domain if present
                    if product['url'].startswith('//www.lazada.vn'):
                        product['url'] = 'https:' + product['url']
                    elif not product['url'].startswith('http'):
                        # Handle relative URLs
                        if product['url'].startswith('/'):
                            product['url'] = 'https://www.lazada.vn' + product['url']
                        else:
                            product['url'] = 'https://www.lazada.vn/' + product['url']
                    break

            # If we didn't find a URL in the links, try to construct it from data-item-id
            if 'url' not in product and item.has_attr('data-item-id'):
                item_id = item['data-item-id']
                product['url'] = f'https://www.lazada.vn/products/pdp-i{item_id}.html'

            # Extract product name - look for the title in the link or RfADt class
            name_element = item.select_one('.RfADt a')
            if name_element:
                product['name'] = name_element.get('title') or name_element.text.strip()
            else:
                # Try alternative selectors for name
                name_element = item.select_one('a[title]')
                if name_element and name_element.has_attr('title'):
                    product['name'] = name_element['title']
                else:
                    # Last resort - try to find any text that might be a product name
                    name_element = item.select_one('.RfADt')
                    if name_element:
                        product['name'] = name_element.text.strip()

            # Extract price - look for the price in ooOxS class
            price_element = item.select_one('.ooOxS')
            if price_element:
                product['price'] = price_element.text.strip()
            else:
                # Try alternative selectors for price
                price_element = item.select_one('.aBrP0')
                if price_element:
                    product['price'] = price_element.text.strip()

            # Extract discount if available
            discount_element = None
            discount_container = item.select_one('.WNoq3')

            if discount_container:
                spans = discount_container.find_all('span')
                for span in spans:
                    text = span.get_text(strip=True)
                    if 'Voucher giảm' in text:
                        discount_element = text
                        break

            if discount_element:
                product['discount'] = discount_element

            # Extract location if available
            location_element = item.select_one('.oa6ri')
            if location_element:
                product['location'] = location_element.get('title') or location_element.text.strip()

            # Extract image URL
            img_element = item.select_one('img[type="product"]')
            if img_element:
                product['image_url'] = img_element.get('src')
                if product['image_url'] and not product['image_url'].startswith('http'):
                    product['image_url'] = 'https:' + product['image_url']

            # Only add products that have at least a URL or name
            if ('url' in product or 'name' in product):
                products.append(product)

        except Exception as e:
            print(f"Error extracting product info: {e}")

    print(f"Extracted information for {len(products)} products")
    return products

# Function to save products to CSV
def save_products_to_csv(products, filename="lazada_products_raw.csv"):
    # Create list key 0
    existing_keys = set()

    # If file exists, read existing keys
    if os.path.exists(filename):
        with open(filename, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            key0 = reader.fieldnames[0] if reader.fieldnames else None
            for row in reader:
                if key0 and key0 in row:
                    existing_keys.add(row[key0])

    # Open the CSV file in append mode
    with open(filename, mode='a', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['url', 'name', 'discount', 'price', 'location', 'image_url']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        # If the file is empty, write the header
        if os.path.getsize(filename) == 0:
            writer.writeheader()

        new_count = 0
        for product in products:
            key_value = product.get('url')
            if key_value and key_value not in existing_keys:
                writer.writerow(product)
                existing_keys.add(key_value)
                new_count += 1

    print(f"Saved {new_count} new products")

# Function to start the browser
def start_browser():
    options = Options()
    options.add_argument('--start-maximized')
    driver = webdriver.Chrome(options=options)
    driver.get("https://www.lazada.vn/dien-thoai-may-tinh-bang/")
    return driver

# Manual mode
def run_manual(driver):
    while True:
        input("Press Enter to scrape the current page...")
        html = driver.page_source
        driver.execute_script("document.body.style.zoom='10%'")
        products = extract_product_info(html)
        save_products_to_csv(products)
        choice = input("Continue manual(Press m) or Auto(Press a) ").strip().lower()
        if choice == 'a':
            return 'auto'
        elif choice != 'm':
            print("manual")

# Auto mode
def run_auto(driver, start_page=1, num_pages=10, base_url='https://www.lazada.vn/dien-thoai-may-tinh-bang/?page='):
    for page in range(start_page, start_page + num_pages):
        print(f"Trying to access....page {page}")
        driver.get(f'{base_url}{page}')
        driver.execute_script("document.body.style.zoom='10%'")
        time.sleep(5)  # Wait for the page to load
        html = driver.page_source
        products = extract_product_info(html)
        save_products_to_csv(products)
        time.sleep(5)

# Main
def main():
    driver = start_browser()
    input("Open Lazada and acctive CAPTCHA, then press Enter to continue...")

    while True:
        mode = input("Choose mode (a: auto ) (m: manual): ").strip().lower()
        if mode == 'm':
            next_mode = run_manual(driver)
            if next_mode == 'auto':
                mode = 'a'
        elif mode == 'a':
            try:
                start_page = int(input("Start page: "))
                num_pages = int(input("Total page: "))
                run_auto(driver, start_page, num_pages)
            except ValueError:
                print("Enter Number!")
        else:
            print("Choose a or m")

if __name__ == "__main__":
    main()

