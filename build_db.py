import json
import chromadb
from chromadb.utils import embedding_functions

# ==========================
# 1️⃣ Cấu hình file và Collection
# ==========================
JSON_FILE = "data/all_data.json"
COLLECTION_NAME = "dgnl_hcmue"
EMBEDDING_MODEL = "BAAI/bge-m3"
CHROMA_PATH = "./chroma_db"
BATCH_SIZE = 20  # Chia nhỏ để tránh lỗi tràn bộ nhớ khi xử lý vector

# ==========================
# 2️⃣ Khởi tạo Embedding Function
# ==========================
# Sử dụng model BGE-M3 như bạn đã chọn
embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=EMBEDDING_MODEL
)

# ==========================
# 3️⃣ Khởi tạo ChromaDB client
# ==========================
client = chromadb.PersistentClient(path=CHROMA_PATH)

# ==========================
# 4️⃣ Tạo hoặc lấy Collection
# ==========================
collection = client.get_or_create_collection(
    name=COLLECTION_NAME,
    embedding_function=embedding_function
)

# ==========================
# 5️⃣ Đọc và Xử lý dữ liệu
# ==========================
try:
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    ids = []
    documents = []
    metadatas = []

    print(f"🔄 Đang chuẩn bị dữ liệu từ {len(data)} chunks...")

    for item in data:
        # Lấy ID: Ưu tiên 'id' sau đó đến 'chunk_id'
        chunk_id = item.get("id") or item.get("chunk_id")
        if not chunk_id:
            continue # Bỏ qua nếu không có định danh
            
        # Lấy Text
        text_content = item.get("text", "").strip()
        if not text_content:
            continue # Bỏ qua nếu chunk rỗng

        ids.append(str(chunk_id))
        documents.append(text_content)

        # Xử lý Metadata: Sao chép từ pipeline cũ và bổ sung alias
        meta = item.get("metadata", {}).copy()
        meta.update({
            "url": meta.get("source", ""),
            "breadcrumb": meta.get("breadcrumb", "Chưa rõ"),
            "title": meta.get("title", "Không tiêu đề"),
            "content_type": meta.get("content_type", "text")
        })
        metadatas.append(meta)

    # ==========================
    # 6️⃣ Nạp vào Chroma theo Batch
    # ==========================
    for i in range(0, len(ids), BATCH_SIZE):
        batch_ids = ids[i : i + BATCH_SIZE]
        batch_docs = documents[i : i + BATCH_SIZE]
        batch_metas = metadatas[i : i + BATCH_SIZE]

        collection.add(
            ids=batch_ids,
            documents=batch_docs,
            metadatas=batch_metas
        )
        print(f"Đã nạp thành công: {i + len(batch_ids)}/{len(ids)} chunks")

    print(f"\n HOÀN TẤT! Đã đẩy {len(ids)} chunks vào bộ nhớ vector.")

except FileNotFoundError:
    print(f"Lỗi: Không tìm thấy file {JSON_FILE}")
except Exception as e:
    print(f"Có lỗi xảy ra: {e}")