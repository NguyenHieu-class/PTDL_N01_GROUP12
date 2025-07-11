import pandas as pd
import json
import re
import requests

# === Cấu hình ===
CSV_PATH = "processed_lazada_with_url.csv"
OLLAMA_URL = "http://localhost:11434/api/generate"

# === Gọi mô hình DeepSeek để phân tích truy vấn ===
def parse_query_with_deepseek(query: str) -> dict:
    prompt = f"""
Chuyển yêu cầu sau thành một JSON chứa các trường kỹ thuật sau:

- brand
- model
- product_title
- RAM
- ROM
- OS
- screen_size
- battery_capacity
- warranty
- price_final
- discount_percent
- maximize_field

Quy tắc bắt buộc:
1. Chỉ trả về **một JSON hợp lệ duy nhất**, bắt đầu bằng '{{' và kết thúc bằng '}}'.
2. Không viết thêm giải thích, nhận xét hoặc bất kỳ văn bản nào khác ngoài JSON.
3. Nếu không có thông tin → gán -1
4. Nếu yêu cầu chứa từ như “trên”, “từ”, “ít nhất” → ghi số để lọc `>=`
5. Nếu người dùng nói “màn hình nhỏ”, “giá rẻ”, “nhẹ nhất” → không gán maximize_field
6. Trường `maximize_field`: chỉ dùng khi người dùng yêu cầu “cao nhất”, “lớn nhất”. Gán chính xác một trong các giá trị sau:
   - "RAM"
   - "ROM"
   - "battery_capacity"
   - "screen_size"
   - "discount_percent"
   - "warranty"
   Nếu không có yêu cầu ưu tiên → gán -1
7. Giá trị số chỉ lấy phần số, không đơn vị (VD: "8GB" → 8, "5000mAh" → 5000)

Yêu cầu người dùng:
{query}

Trả về JSON duy nhất:
""".strip()

    data = {
        "model": "deepseek-r1:8b",
        "prompt": prompt,
        "stream": False
    }

    try:
        res = requests.post(
            OLLAMA_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(data),
            timeout=60
        )
        res.raise_for_status()
        matches = re.findall(r"\{.*?\}", res.json()["response"], re.DOTALL)
        for m in matches:
            try:
                parsed = json.loads(m)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue
    except Exception as e:
        print("❌ Lỗi khi gọi mô hình:", e)
    
    return {}

# === Lọc dữ liệu theo tiêu chí ===
def filter_products(df: pd.DataFrame, criteria: dict) -> pd.DataFrame:
    df_filtered = df.copy()
    numeric_fields = ["RAM", "ROM", "battery_capacity", "screen_size", "warranty", "price_final", "discount_percent"]

    for key, value in criteria.items():
        if value in [None, "", -1, "-1"] or key == "maximize_field":
            continue
        if key in numeric_fields:
            try:
                value = float(value)
                if key == "price_final":
                    df_filtered = df_filtered[(df_filtered[key] != -1) & (df_filtered[key] <= value)]
                elif key == "discount_percent":
                    df_filtered = df_filtered[(df_filtered[key] != -1) & (df_filtered[key] >= value)]
                else:
                    df_filtered = df_filtered[(df_filtered[key] != -1) & (df_filtered[key] >= value)]
            except:
                continue
        else:
            df_filtered = df_filtered[df_filtered[key].astype(str).str.lower().str.contains(str(value).lower())]

    return df_filtered

# === Xử lý hiển thị giá trị thiếu ===
def fmt(value, suffix='', unknown="Không rõ"):
    return f"{value}{suffix}" if str(value) != "-1" else unknown

# === Giao diện dòng lệnh ===
def recommend_products_cli():
    try:
        df = pd.read_csv(CSV_PATH)
    except Exception as e:
        print("❌ Không thể đọc file CSV:", e)
        return

    print("🎉 Hệ thống gợi ý sản phẩm Lazada")
    print("🔎 Nhập yêu cầu bằng tiếng Việt tự nhiên, ví dụ:")
    print("   ➤ Tìm điện thoại Samsung dưới 5 triệu, giảm giá ít nhất 20%")
    print("   ➤ Mua Xiaomi RAM 8GB, pin trâu, màn hình > 6.5 inch")
    print("   ➤ Tìm điện thoại có pin lớn nhất, RAM cao nhất\n")

    while True:
        query = input("🔍 Nhập yêu cầu của bạn (hoặc gõ 'exit' để thoát): ").strip()
        if query.lower() == 'exit':
            print("👋 Tạm biệt!")
            break

        print(f"\n🧠 Đang phân tích yêu cầu: {query}")
        criteria = parse_query_with_deepseek(query)
        print("🎯 Tiêu chí trích xuất:", criteria)

        maximize_field = criteria.get("maximize_field")
        if maximize_field and maximize_field in df.columns:
            df_valid = df[df[maximize_field] != -1]
            top = df_valid.sort_values(maximize_field, ascending=False).head(10)
            print(f"\n✅ Top 10 sản phẩm có '{maximize_field}' lớn nhất:\n")
        else:
            filtered = filter_products(df, criteria)
            if filtered.empty:
                print("❌ Không tìm thấy sản phẩm phù hợp.\n")
                continue
            top = filtered.sort_values("price_final").head(10)
            print(f"\n✅ Tìm thấy {len(filtered)} sản phẩm phù hợp. Hiển thị top 10:\n")

        for idx, row in top.iterrows():
            print(f"📱 {row['product_title']}")
            print(f"   ➤ Thương hiệu: {fmt(row['brand'])} | Model: {fmt(row['model'])}")
            print(f"   ➤ Giá: {fmt(row['price_final'], '₫')} | Giảm: {fmt(row['discount_percent'], '%')}")
            print(f"   ➤ RAM: {fmt(row['RAM'], 'GB')} | ROM: {fmt(row['ROM'], 'GB')} | Pin: {fmt(row['battery_capacity'], 'mAh')}")
            print(f"   ➤ Màn: {fmt(row['screen_size'])}\" | HĐH: {fmt(row['OS'])} | Bảo hành: {fmt(row['warranty'], ' tháng', 'Không có thông tin')}")
            print(f"   🔗 Link: {row['url']}\n")

if __name__ == "__main__":
    recommend_products_cli()
