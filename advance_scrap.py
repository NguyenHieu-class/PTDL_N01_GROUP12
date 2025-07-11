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

FIELDNAMES = [
    'product_title', 'price_final', 'price_original', 'discount_percent',
    'color', 'main_image', 'thumbnails', 'seller_name', 'seller_url',
    'warranty_info', 'delivery_address', 'product_description'
]

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
    # driver.execute_script("window.scrollBy(0, document.body.scrollHeight / 5);")
    # driver.execute_script("document.body.style.zoom='10%'")
    return driver

def scroll_and_expand(driver, scroll_pause=1.0, max_scroll=30):
    # Luôn đảm bảo thu nhỏ 20%
    driver.execute_script("document.body.style.zoom='20%'")
    print("🔍 Đang cuộn xuống để tìm nút 'XEM THÊM'...")

    for i in range(max_scroll):
        try:
            # Kiểm tra sự tồn tại của nút "XEM THÊM"
            xem_them_btn = driver.find_element(By.CSS_SELECTOR, ".pdp-view-more-btn")
            if xem_them_btn.is_displayed():
                print(f"✅ Tìm thấy nút 'XEM THÊM' sau {i+1} lần cuộn.")
                # Scroll đến nút rồi click
                ActionChains(driver).move_to_element(xem_them_btn).perform()
                time.sleep(0.5)
                xem_them_btn.click()
                print("🟢 Đã click nút 'XEM THÊM'")
                
                # Cuộn lại về đầu sau khi click
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(scroll_pause)
                return
        except:
            pass

        # Cuộn thêm mỗi vòng
        driver.execute_script("window.scrollBy(0, 500);")
        time.sleep(scroll_pause)

    print("⚠️ Không tìm thấy nút 'XEM THÊM' sau khi cuộn tối đa.")
    print("↩️ Đang cuộn lại lên đầu...")

    # Luôn đảm bảo quay lại đầu và thu nhỏ
    driver.execute_script("window.scrollTo(0, 0);")
    driver.execute_script("document.body.style.zoom='20%'")
    time.sleep(scroll_pause)


def scrape_product_detail(url_html):
    soup = BeautifulSoup(url_html, 'html.parser') 
    product = {}

    try:
        product['product_title'] = soup.select_one('#module_product_title_1 .pdp-mod-product-badge-title')
        product['product_title'] = product['product_title'].get_text(strip=True) if product['product_title'] else None

        price_block = soup.find('div', id='module_product_price_1')
        if price_block:
            product['price_final'] = price_block.select_one('.pdp-price_type_normal').get_text(strip=True) if price_block.select_one('.pdp-price_type_normal') else None
            product['price_original'] = price_block.select_one('.pdp-price_type_deleted').get_text(strip=True) if price_block.select_one('.pdp-price_type_deleted') else None
            product['discount_percent'] = price_block.select_one('.pdp-product-price__discount').get_text(strip=True) if price_block.select_one('.pdp-product-price__discount') else None

        color_tag = soup.select_one('#module_sku-select .sku-name')
        product['color'] = color_tag.get_text(strip=True) if color_tag else None

        main_img_tag = soup.select_one('.gallery-preview-panel__image')
        product['main_image'] = main_img_tag['src'] if main_img_tag and main_img_tag.has_attr('src') else None

        thumbnails = soup.select('.item-gallery__thumbnail-image')
        product['thumbnails'] = ', '.join([img['src'] for img in thumbnails if img.has_attr('src')])

        seller_tag = soup.select_one('#module_seller_info .seller-name__detail-name')
        product['seller_name'] = seller_tag.get_text(strip=True) if seller_tag else None
        product['seller_url'] = 'https:' + seller_tag['href'] if seller_tag and seller_tag.has_attr('href') else None

        warranty_tags = soup.select('#module_seller_warranty .delivery-option-item__title')
        warranties = [w.get_text(strip=True) for w in warranty_tags]
        product['warranty_info'] = ' | '.join(warranties) if warranties else None

        delivery_tag = soup.select_one('.location__address')
        product['delivery_address'] = delivery_tag.get_text(strip=True) if delivery_tag else None

        description_block = soup.select_one('.html-content.detail-content article.lzd-article')
        description_text = []
        if description_block:
            for tag in description_block.find_all(['p', 'span']):
                if tag.find('img'):
                    continue
                text = tag.get_text(separator=' ', strip=True)
                if text:
                    description_text.append(text)
        product['product_description'] = '\n'.join(description_text) if description_text else None

    except Exception as e:
        print(f"❌ Error extracting product info: {e}")
        return None

    return product

FIELDNAMES = [
    'key_0',  # thêm dòng này vào đầu
    'product_title', 'price_final', 'price_original', 'discount_percent',
    'color', 'main_image', 'thumbnails', 'seller_name', 'seller_url',
    'warranty_info', 'delivery_address', 'product_description'
]

def save_product_to_csv(product, filename=OUTPUT_CSV):
    file_exists = os.path.isfile(filename)
    current_index = 1

    # Nếu file đã tồn tại, tính số dòng hiện có (bỏ header)
    if file_exists:
        with open(filename, newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            lines = list(reader)
            current_index = len(lines)  # index = số dòng hiện tại (bao gồm header)

    # Thêm key_0 vào sản phẩm
    product_with_key = {'key_0': current_index}
    for key in FIELDNAMES:
        if key != 'key_0':
            product_with_key[key] = product.get(key, '')

    # Ghi file
    with open(filename, mode='a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=FIELDNAMES)
        if not file_exists or os.path.getsize(filename) == 0:
            writer.writeheader()
        writer.writerow(product_with_key)



def run_auto(driver, urls, start_index=0, delay=5, max_count=None):
    success_count = 0
    failed_count = 0
    total = len(urls)
    end_index = min(total, start_index + (max_count if max_count else total))

    for i in range(start_index, end_index):
        print(f"\n[AUTO] [{i+1}/{total}] Đang mở: {urls[i]}")
        try:
            driver.get(urls[i])
            time.sleep(delay)

            # Thu nhỏ trang & xử lý tự động cuộn + click 'XEM THÊM'
            scroll_and_expand(driver)

            html = driver.page_source
            product = scrape_product_detail(html)

            if product:
                # Gắn thêm URL vào product nếu cần dùng làm key
                product['url'] = urls[i]
                save_product_to_csv(product)
                success_count += 1
                print("✅ Đã lưu sản phẩm.")
            else:
                failed_count += 1
                print("❌ Sản phẩm không hợp lệ hoặc không có dữ liệu.")
        except Exception as e:
            print(f"⚠️ Lỗi khi xử lý URL: {e}")
            failed_count += 1
            continue

    return 'done', end_index, success_count, failed_count


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
        if mode == 'a':
            try:
                delay = int(input("⏱ Nhập thời gian chờ giữa các sản phẩm (giây): "))
                result, index, ok, fail = run_auto(driver, urls, start_index=index, delay=delay)
            except ValueError:
                print("❌ Vui lòng nhập số nguyên!")
                continue
        else:
            print("❌ Hiện tại chỉ hỗ trợ chế độ tự động (a).")
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
