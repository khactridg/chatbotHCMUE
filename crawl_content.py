import requests
from bs4 import BeautifulSoup
import html2text
import urllib3
import re
import json
import os
import fitz  # Thư viện PyMuPDF
import hashlib # Bổ sung để làm ID Hash
from datetime import datetime
from langchain_text_splitters import RecursiveCharacterTextSplitter

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def extract_pdf_content(pdf_url):
    """Tải và trích xuất chữ từ PDF"""
    try:
        clean_url = pdf_url.split('#')[0].split('?')[0]
        response = requests.get(clean_url, verify=False, timeout=25)
        with fitz.open(stream=response.content, filetype="pdf") as doc:
            return "\n[NỘI DUNG PDF NHÚNG]\n" + "".join([page.get_text() for page in doc]) + "\n[KẾT THÚC PDF]\n"
    except:
        return f"\n[Lỗi: Không thể đọc nội dung PDF nhúng tại {pdf_url}]\n"

def get_raw_document(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=20)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        article_section = soup.find('div', class_='article-details') or \
                          soup.find('article') or soup.find('main')
        if not article_section: return None

        # Xử lý PDF nhúng
        embed_tags = article_section.find_all(['iframe', 'embed', 'object'])
        for tag in embed_tags:
            src = tag.get('src') or tag.get('data')
            if src and '.pdf' in src.lower():
                full_pdf_url = requests.compat.urljoin(url, src)
                pdf_text = extract_pdf_content(full_pdf_url)
                tag.replace_with(pdf_text)

        # Xử lý Ảnh
        for img in article_section.find_all('img'):
            src = img.get('src')
            if src:
                alt = img.get('alt', 'Hình ảnh minh họa').strip()
                full_img_url = requests.compat.urljoin(url, src)
                img_marker = f"\n[HÌNH ẢNH: {alt} | Link: {full_img_url}]\n"
                img.replace_with(img_marker)

        # Lọc rác
        for unwanted in article_section.find_all(['script', 'style', 'nav', 'header', 'footer']):
            unwanted.decompose()

        converter = html2text.HTML2Text()
        converter.ignore_links = False 
        converter.ignore_images = True
        converter.body_width = 0
        raw_markdown = converter.handle(str(article_section))

        return {
            "title": soup.title.get_text(strip=True) if soup.title else "No Title",
            "content": re.sub(r'\n{3,}', '\n\n', raw_markdown).strip()
        }
    except Exception as e:
        print(f"✘ Lỗi: {e}")
        return None

# --- BỔ SUNG: CLASSIFICATION, HASH ID, DATE, TOKEN COUNT ---
def split_into_chunks(raw_doc, url, menu, submenu, index_num):
    if not raw_doc: return []
    
    # 1. Logic Classification
    if menu == "Đánh giá Năng lực Chuyên biệt":
        classification = "Đánh giá Năng lực Chuyên biệt"
    elif menu == "ĐGNL Tiếng việt":
        classification = "ĐGNL Tiếng việt"
    else:
        classification = "Thông tin chung"

    # 2. Tạo ID Hash từ URL
    article_hash = hashlib.md5(url.encode()).hexdigest()

    # Cấu hình bộ chia (Sử dụng tham số tường minh để tránh lỗi size/overlap)
    splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=200)
    text_chunks = splitter.split_text(raw_doc["content"])
    
    return [{
        "chunk_id": f"{article_hash}_p{i}",
        "text": chunk,
        "metadata": {
            "source": url, 
            "title": raw_doc["title"], 
            "breadcrumb": f"{menu} > {submenu}" if submenu else menu,
            "classification": classification,
            "scraped_at": datetime.now().isoformat(),
            "token_count": len(chunk.split()) # Đếm số từ (Word count) làm token ước lượng
        }
    } for i, chunk in enumerate(text_chunks)]

if __name__ == "__main__":
    if not os.path.exists("data/content"): os.makedirs("data/content")
    
    # Đọc danh sách link
    with open("data/links.json", "r", encoding="utf-8") as f:
        items = [item for item in json.load(f) if item.get('type') != "external"]

    total_chunks = 0
    for i, item in enumerate(items, 1):
        file_path = f"data/content/dgnl_{i}.json"
        if os.path.exists(file_path): continue
        
        print(f"🌐 Đang xử lý ({i}/{len(items)}): {item['url']}")
        doc = get_raw_document(item['url'])
        if doc:
            chunks = split_into_chunks(doc, item['url'], item['menu'], item.get('submenu'), i)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(chunks, f, ensure_ascii=False, indent=2)
            total_chunks += len(chunks)
            print(f"✔ Đã lưu dgnl_{i}.json - {len(chunks)} chunks")

    print(f"\n✅ HOÀN TẤT! Tổng số chunk: {total_chunks}")