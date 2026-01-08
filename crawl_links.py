import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
import urllib3
import time
import json
import os
# ===============================
# CẤU HÌNH & SSL
# ===============================
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
BASE_URL = "https://dgnl.hcmue.edu.vn"
HOME_URL = "https://dgnl.hcmue.edu.vn/index.php?lang=vi"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RAG-Crawler/1.0"}

session = requests.Session()
session.headers.update(HEADERS)
scraped_article_ids = set()

# ===============================
# UTILS
# ===============================
def fetch(url):
    try:
        r = session.get(url, timeout=20, verify=False)
        r.raise_for_status()
        r.encoding = "utf-8"
        return r.text
    except:
        return ""

def classify_url(url):
    p = urlparse(url)
    if p.netloc and BASE_URL not in url: return "external"
    qs = parse_qs(p.query)
    if qs.get("view") == ["category"]: return "category"
    if qs.get("view") == ["article"]: return "article"
    return "page"

def normalize_category_url(url):
    p = urlparse(url)
    qs = parse_qs(p.query)
    return f"{p.scheme}://{p.netloc}/index.php?option=com_content&view=category&id={qs.get('id',[''])[0]}&limitstart={qs.get('limitstart',['0'])[0]}"

def extract_article_id(url):
    qs = parse_qs(urlparse(url).query)
    try: return int(qs["id"][0].split(":")[0])
    except: return None

# ===============================
# CORE LOGIC
# ===============================
def crawl_menu_tree():
    html = fetch(HOME_URL)
    if not html: return []
    soup = BeautifulSoup(html, "html.parser")
    tree = []
    menu_root = soup.select_one("ul.sp-megamenu-parent")
    if not menu_root: return []
        
    for li in menu_root.find_all("li", class_="sp-menu-item", recursive=False):
        a = li.find("a", recursive=False)
        if not a: continue
        node = {
            "menu": a.get_text(strip=True),
            "url": urljoin(BASE_URL, a.get("href")),
            "children": []
        }
        dropdown = li.select_one("ul.sp-dropdown-items")
        if dropdown:
            for sub_a in dropdown.select("li.sp-menu-item > a"):
                node["children"].append({
                    "submenu": sub_a.get_text(strip=True),
                    "url": urljoin(BASE_URL, sub_a.get("href")),
                    "type": classify_url(sub_a.get("href"))
                })
        tree.append(node)
    return tree

def crawl_category(start_url, menu, submenu):
    queue = [start_url]
    visited = set()
    articles = []
    while queue:
        url = queue.pop(0)
        norm = normalize_category_url(url)
        if norm in visited: continue
        visited.add(norm)
        
        html = fetch(url)
        if not html: continue
        soup = BeautifulSoup(html, "html.parser")
        
        for a in soup.select("table.category td.list-title a"):
            full_url = urljoin(BASE_URL, a.get("href"))
            aid = extract_article_id(full_url)
            if aid and aid not in scraped_article_ids:
                scraped_article_ids.add(aid)
                # CHỈ LƯU 4 TRƯỜNG YÊU CẦU
                articles.append({
                    "menu": menu,
                    "submenu": submenu,
                    "type": "article",
                    "url": full_url
                })
        
        for a in soup.select("nav.pagination-wrapper a[href*='limitstart=']"):
            next_url = urljoin(BASE_URL, a.get("href"))
            if normalize_category_url(next_url) not in visited: queue.append(next_url)
        time.sleep(0.3) 
    return articles

# ===============================
# MAIN
# ===============================
if __name__ == "__main__":
    print("⏳ Đang quét danh sách link từ website...")
    menu_tree = crawl_menu_tree()
    all_items = []

    for node in menu_tree:
        menu_name = node["menu"]
        if not node["children"]:
            all_items.append({
                "menu": menu_name,
                "submenu": None,
                "type": classify_url(node["url"]),
                "url": node["url"]
            })
        else:
            for child in node["children"]:
                if child["type"] == "category":
                    all_items.extend(crawl_category(child["url"], menu_name, child["submenu"]))
                else:
                    all_items.append({
                        "menu": menu_name,
                        "submenu": child["submenu"],
                        "type": child["type"],
                        "url": child["url"]
                    })

# ✅ TẠO THƯ MỤC DATA NẾU CHƯA CÓ
    folder_path = "data"
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        print(f"📁 Đã tạo thư mục mới: {folder_path}")

    # ✅ XUẤT FILE VÀO THƯ MỤC DATA
    file_path = os.path.join(folder_path, "links.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=4)

    print(f"✨ Xong! Đã lưu {len(all_items)} mục vào: {file_path}")