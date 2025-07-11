import pandas as pd
import requests
import json
import re
import csv
import os
from tqdm import tqdm

# ===== Cấu hình file =====
INPUT_PATH = "lazada_products_extracted_cleaned.csv"
OUTPUT_PATH = "processed_lazada.csv"
LOG_FAIL_PATH = "fail_log.txt"

FIELDNAMES = [
    "key_0", "main_image", "product_title", "seller_name",
    "price_final", "price_original", "discount_percent",
    "brand", "model", "RAM", "ROM", "OS", "screen_size", "warranty",
    "battery_capacity"
]

# ===== Chuẩn hóa số =====
def clean_price(price_str):
    if pd.isna(price_str) or price_str == "-1":
        return -1
    cleaned = re.sub(r"[^\d]", "", str(price_str))
    return int(cleaned) if cleaned else -1

def clean_percent(pct_str):
    if pd.isna(pct_str) or pct_str == "-1":
        return -1
    cleaned = re.sub(r"[^\d]", "", str(pct_str))
    return int(cleaned) if cleaned else -1

# ===== Cắt mô tả nếu quá dài =====
def truncate_description(desc, max_words=2000):
    words = str(desc).split()
    return " ".join(words[:max_words]) if len(words) > max_words else desc

# ===== Prompt yêu cầu thêm pin =====
def build_prompt(title, description):
    prompt = f"""
Trích xuất thông tin dưới dạng JSON gồm các trường sau:
- brand
- model
- RAM (số, VD: 8GB → 8)
- ROM (số, VD: 256 GB → 256)
- OS (giữ nguyên)
- screen_size (số thực, VD: 6.72 inches → 6.72)
- warranty (số, VD: 12 tháng → 12)
- battery_capacity (số, VD: 4500 mAh → 4500)

Nếu không có thông tin, trả về "-1". Không viết giải thích. Chỉ trả về JSON hợp lệ.

Tiêu đề: {title}
Mô tả: {description}
"""
    return prompt.strip()

# ===== Trích JSON an toàn =====
def extract_json_from_response(text):
    matches = re.findall(r"\{.*?\}", text, flags=re.DOTALL)
    for match in matches:
        try:
            parsed = json.loads(match)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    return None

# ===== Gọi mô hình DeepSeek-R1:8B với timeout =====
def call_deepseek(prompt):
    url = "http://localhost:11434/api/generate"
    headers = {"Content-Type": "application/json"}
    data = {
        "model": "deepseek-r1:8b",
        "prompt": prompt,
        "stream": False
    }

    try:
        res = requests.post(url, headers=headers, data=json.dumps(data), timeout=300)
        res.raise_for_status()
        result = res.json()["response"]
        return extract_json_from_response(result)
    except Exception as e:
        return str(e)

# ===== Ghi file mới từ đầu =====
with open(OUTPUT_PATH, mode="w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
    writer.writeheader()

# ===== Đọc toàn bộ dữ liệu =====
df = pd.read_csv(INPUT_PATH)

for _, row in tqdm(df.iterrows(), total=len(df)):
    truncated_desc = truncate_description(row["product_description"])
    prompt = build_prompt(row["product_title"], truncated_desc)
    extracted = call_deepseek(prompt)

    if not isinstance(extracted, dict):
        with open(LOG_FAIL_PATH, "a", encoding="utf-8") as f:
            f.write(f"[key_0 = {row['key_0']}] Lỗi: {extracted}\n")
        continue

    price_final = clean_price(row["price_final"])
    price_original = clean_price(row["price_original"])
    discount_percent = clean_percent(row["discount_percent"])

    output_row = {
        "key_0": row["key_0"],
        "main_image": row["main_image"],
        "product_title": row["product_title"],
        "seller_name": row["seller_name"],
        "price_final": price_final,
        "price_original": price_original,
        "discount_percent": discount_percent,
        "brand": extracted.get("brand", "-1"),
        "model": extracted.get("model", "-1"),
        "RAM": extracted.get("RAM", "-1"),
        "ROM": extracted.get("ROM", "-1"),
        "OS": extracted.get("OS", "-1"),
        "screen_size": extracted.get("screen_size", "-1"),
        "warranty": extracted.get("warranty", "-1"),
        "battery_capacity": extracted.get("battery_capacity", "-1")
    }

    with open(OUTPUT_PATH, mode="a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writerow(output_row)
