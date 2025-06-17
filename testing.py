import csv
import os
import time
from selenium import webdriver
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def scrape_product_detail(url_html):
    soup = BeautifulSoup(url_html, 'html.parser') 
    try:
        product_info = {}

        # Product title
        block_1 = soup.find('div', id='block-IH9e2k0K6L')
        if block_1:
            title_tag = block_1.select_one('#module_product_title_1 .pdp-mod-product-badge-title')
            product_info['product_title'] = title_tag.get_text(strip=True) if title_tag else None
        else:
            product_info['product_title'] = None

        # Variant options
        if block_1:
            sku_block = block_1.find('div', id='module_sku-select')
            if sku_block:
                variant_elements = sku_block.select('.sku-variable-img-wrap, .sku-variable-img-wrap-selected')
                product_info['variant_option_count'] = len(variant_elements) if variant_elements else 0
            else:
                product_info['variant_option_count'] = None
        else:
            product_info['variant_option_count'] = None

        # Prices
        if block_1:
            price_block = block_1.find('div', id='module_product_price_1')
            if price_block:
                price_tag = price_block.select_one('.pdp-price.pdp-price_type_normal')
                product_info['price_final'] = price_tag.get_text(strip=True) if price_tag else None
                original_price_tag = price_block.select_one('.pdp-price.pdp-price_type_deleted')
                product_info['price_original'] = original_price_tag.get_text(strip=True) if original_price_tag else None
                discount_tag = price_block.select_one('.pdp-product-price__discount')
                product_info['discount_percent'] = discount_tag.get_text(strip=True) if discount_tag else None
            else:
                product_info['price_final'] = None
                product_info['price_original'] = None
                product_info['discount_percent'] = None
        else:
            product_info['price_final'] = None
            product_info['price_original'] = None
            product_info['discount_percent'] = None

        # Warranty
        if block_1:
            warranty_block = block_1.find('div', id='module_seller_warranty')
            if warranty_block:
                options = warranty_block.select('.warranty__option-item .delivery-option-item__title')
                warranty_info = [opt.get_text(strip=True) for opt in options if opt.get_text(strip=True)]
                product_info['warranty_info'] = ' | '.join(warranty_info) if warranty_info else None
            else:
                product_info['warranty_info'] = None
        else:
            product_info['warranty_info'] = None

        # Seller
        if block_1:
            seller_block = block_1.find('div', id='module_seller_info')
            if seller_block:
                seller_name_tag = seller_block.find('a', class_='seller-name__detail-name')
                if seller_name_tag:
                    product_info['seller_name'] = seller_name_tag.get_text(strip=True)
                    seller_url = seller_name_tag.get('href')
                    if seller_url and seller_url.startswith('//'):
                        seller_url = 'https:' + seller_url
                    product_info['seller_url'] = seller_url
                else:
                    product_info['seller_name'] = None
                    product_info['seller_url'] = None
            else:
                product_info['seller_name'] = None
                product_info['seller_url'] = None
        else:
            product_info['seller_name'] = None
            product_info['seller_url'] = None

        # Description
        detail_content = soup.select_one("div.html-content.detail-content article.lzd-article")
        if detail_content:
            description_blocks = detail_content.find_all(['ul', 'p', 'span', 'div'])
            description = ' '.join(block.get_text(separator=" ", strip=True) for block in description_blocks if block.get_text(strip=True))
            product_info['description'] = description if description else None
        else:
            product_info['description'] = None

        return product_info
    except Exception as e:
        print(f"Error extracting product info: {e}")
        return None
    
CSV_FILE = "lazada_products_raw.csv"
OUTPUT_CSV = "lazada_products_extracted.csv"

def load_product_urls(csv_file=CSV_FILE):
    urls = []
    if not os.path.exists(csv_file):
        print(f"File CSV không tồn tại: {csv_file}")
        return urls
    with open(csv_file, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if 'url' in row and row['url'].startswith('http'):
                urls.append(row['url'])
    print(f"Đã đọc {len(urls)} URL sản phẩm từ file CSV.")
    return urls

def start_browser():
    options = Options()
    options.add_argument('--start-maximized')
    driver = webdriver.Chrome(options=options)
    driver.execute_script("document.body.style.zoom='40%'")
    return driver

# Hàm cuộn và mở rộng nội dung
def scroll_and_expand(driver, scroll_pause=1.0):
    # Cuộn chuột từ từ
    last_height = driver.execute_script("return document.body.scrollHeight")

    for _ in range(5):
        driver.execute_script("window.scrollBy(0, document.body.scrollHeight / 5);")
        time.sleep(scroll_pause)

    # Thử click vào nút "XEM THÊM"
    try:
        # Chờ nút xuất hiện
        wait = WebDriverWait(driver, 5)
        xem_them_btn = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, ".pdp-view-more-btn")))
        
        # Scroll đến nút và click
        ActionChains(driver).move_to_element(xem_them_btn).perform()
        xem_them_btn.click()
        print("🟢 Đã click nút 'XEM THÊM'")
        time.sleep(1.5)
    except Exception as e:
        print("⚠️ Không tìm thấy hoặc không thể click nút 'XEM THÊM'.")

    # Cuộn xuống cuối để load thêm nếu có
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(scroll_pause)
    # Cuộn lên trên cùng để đảm bảo nội dung đã được tải đầy đủ
    driver.execute_script("window.scrollTo(0, 0);")

def run_manual(driver, urls, start_index=0, max_count=5):
    total = len(urls)
    end_index = min(total, start_index + max_count)

    for i in range(start_index, end_index):
        input(f"[MANUAL] [{i+1}/{total}] Nhấn Enter để mở sản phẩm...")
        print(f"→ Đang mở: {urls[i]}")
        driver.get(urls[i])
        driver.execute_script("document.body.style.zoom='30%'")
        time.sleep(2)
        scroll_and_expand(driver)

        html = driver.page_source
        product = scrape_product_detail(html)
        if product:
            save_product_to_csv(product)
            print("📥 Đã lưu sản phẩm.")
        else:
            print("❌ Sản phẩm không hợp lệ.")


def run_auto(driver, urls, start_index=0, delay=5, max_count=None):
    total = len(urls)
    end_index = min(total, start_index + (max_count if max_count else total))

    for i in range(start_index, end_index):
        print(f"[AUTO] [{i+1}/{total}] Đang mở: {urls[i]}")
        driver.get(urls[i])
        driver.execute_script("document.body.style.zoom='30%'")
        time.sleep(delay)
        scroll_and_expand(driver)

        html = driver.page_source
        product = scrape_product_detail(html)
        if product:
            save_product_to_csv(product)
            print("📥 Đã lưu sản phẩm.")
        else:
            print("❌ Sản phẩm không hợp lệ.")

def save_product_to_csv(product, filename=OUTPUT_CSV):
    file_exists = os.path.isfile(filename)
    fieldnames = ['product_title', 'variant_option_count', 'price_final', 'price_original', 'discount_percent', 'warranty_info', 'seller_name', 'seller_url', 'description']

    with open(filename, mode='a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        if not file_exists or os.path.getsize(filename) == 0:
            writer.writeheader()

        if product:
            writer.writerow(product)

def main():
    urls = load_product_urls()
    if not urls:
        return

    driver = start_browser()
    input("⚠️ Nếu có CAPTCHA, hãy xử lý xong rồi nhấn Enter để tiếp tục...")

    index = 0
    success_count = 0
    failed_count = 0

    while index < len(urls):
        mode = input("\n🔘 Chọn chế độ (m: thủ công, a: tự động): ").strip().lower()
        if mode == 'm':
            result, index, ok, fail = run_manual(driver, urls, start_index=index)
        elif mode == 'a':
            try:
                delay = int(input("⏱ Nhập thời gian chờ giữa các sản phẩm (giây): "))
                result, index, ok, fail = run_auto(driver, urls, start_index=index, delay=delay)
            except ValueError:
                print("❌ Vui lòng nhập số nguyên!")
                continue
        else:
            print("❌ Chỉ được nhập 'm' hoặc 'a'.")
            continue

        success_count += ok
        failed_count += fail

        if result in ['done', 'quit']:
            break

    driver.quit()
    print("\n🎉 KẾT THÚC THU THẬP DỮ LIỆU")
    print(f"✅ Thành công: {success_count}")
    print(f"❌ Thất bại: {failed_count}")

if __name__ == "__main__":
    main()
