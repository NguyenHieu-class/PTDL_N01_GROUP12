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

# Extract product information from the page
def scrape_product_detail(url_html):
    soup = BeautifulSoup(url_html, 'html.parser') 
    products = []
    
    try:
        product_info = {}

        # Tìm block đầu tiên chứa thông tin cơ bản
        block_1 = soup.find('div', id='block-IH9e2k0K6L')
        product_title = None

        # Lấy tiêu đề sản phẩm từ block đầu tiên
        if block_1:
            title_tag = block_1.select_one('#module_product_title_1 .pdp-mod-product-badge-title')
            if title_tag:
                product_title = title_tag.get_text(strip=True)

        product_info.append({'product_title': product_title})

        # lấy danh sách option
        variant_option_count = None  # Mặc định là None nếu không tìm thấy

        if block_1:
            sku_block = block_1.find('div', id='module_sku-select')
            if sku_block:
                # Tìm tất cả biến thể sản phẩm hiển thị (có class sku-variable-img-wrap hoặc sku-variable-img-wrap-selected)
                variant_elements = sku_block.select('.sku-variable-img-wrap, .sku-variable-img-wrap-selected')
                variant_option_count = len(variant_elements) if variant_elements else 0

        product_info.append({'variant_option_count': variant_option_count})

        # Lấy giá sản phẩm
        price_final = None
        price_original = None
        discount_percent = None

        if block_1:
            price_block = block_1.find('div', id='module_product_price_1')
            if price_block:
                # Giá sau giảm (giá hiện tại)
                price_tag = price_block.select_one('.pdp-price.pdp-price_type_normal')
                if price_tag:
                    price_final = price_tag.get_text(strip=True)

                # Giá gốc (đã gạch)
                original_price_tag = price_block.select_one('.pdp-price.pdp-price_type_deleted')
                if original_price_tag:
                    price_original = original_price_tag.get_text(strip=True)

                # Phần trăm giảm giá (nếu có)
                discount_tag = price_block.select_one('.pdp-product-price__discount')
                if discount_tag:
                    discount_percent = discount_tag.get_text(strip=True)

        product_info.append({
            'price_final': price_final,
            'price_original': price_original,
            'discount_percent': discount_percent
        })

        # Lấy thông tin bảo hành
        warranty_info = None

        if block_1:
            warranty_block = block_1.find('div', id='module_seller_warranty')
            if warranty_block:
                options = warranty_block.select('.warranty__option-item .delivery-option-item__title')
                warranty_info = [opt.get_text(strip=True) for opt in options if opt.get_text(strip=True)]

        warranty_info = ' | '.join([w for w in warranty_info if w]) if warranty_info else None

        product_info.append({
            'warranty_info': warranty_info
        })

        # lấy thông tin shop bán
        seller_name = None
        seller_url = None

        if block_1:
            seller_block = block_1.find('div', id='module_seller_info')
            if seller_block:
                seller_name_tag = seller_block.find('a', class_='seller-name__detail-name')
                if seller_name_tag:
                    seller_name = seller_name_tag.get_text(strip=True)
                    seller_url = seller_name_tag.get('href')
                    if seller_url and seller_url.startswith('//'):
                        seller_url = 'https:' + seller_url

        product_info.append({
            'seller_name': seller_name,
            'seller_url': seller_url
        })

        # # Tìm phần chứa mô tả chi tiết sản phẩm
        # detail_content = soup.select_one("div.html-content.detail-content article.lzd-article")

        # # Nếu không tìm thấy thì bỏ qua
        # if detail_content:
        #     # Tìm tất cả thẻ có thể chứa mô tả
        #     description_blocks = detail_content.find_all(['ul', 'p', 'span', 'div'])

        #     for block in description_blocks:
        #         text = block.get_text(separator=" ", strip=True)
        #         if text:
        #             product_info.append({
        #                 'description_item': text
        #             })

    except Exception as e:
            print(f"Error extracting product info: {e}")

    return products


# Hàm lưu sản phẩm vào file CSV
def save_product_to_csv(product, filename=OUTPUT_CSV):
    file_exists = os.path.isfile(filename)

    # Mở file với mode append
    with open(filename, mode='a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=product.keys())

        # Ghi header nếu file chưa tồn tại
        if not file_exists:
            writer.writeheader()

        # Ghi dữ liệu sản phẩm
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
