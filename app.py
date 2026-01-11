import os
import streamlit as st
import chromadb
from google import genai
from chromadb.utils import embedding_functions

CHROMA_PATH = "chroma_db"
COLLECTION_NAME = "dgnl_hcmue"
TOP_K = 3

# ======================
# PAGE CONFIG
# ======================
st.set_page_config(
    page_title="HCMUE Admission Chatbot",
    page_icon="🎓",
    layout="wide"
)



# ======================
# SIDEBAR
# ======================
with st.sidebar:
    st.markdown("## HCMUE Chatbot")
    st.markdown(
        """
        Hỗ trợ thông tin tuyển sinh kỳ thi Đánh giá năng lực chuyên biệt 
        **Trường ĐH Sư phạm TP.HCM**
        
        ---
        **Dữ liệu**: https://dgnl.hcmue.edu.vn/  
        **Mô hình**: Gemini 2.5 Flash  
        **Kỹ thuật**: RAG + ChromaDB
        """
    )

    st.markdown("---")
    st.caption("© 2026 – by b4db0ybachkhoa")

# ======================
# MAIN TITLE
# ======================
st.markdown(
    """
    <h2 style="text-align:center;">HCMUE CHATBOT AI</h2>
    <p style="text-align:center; color: gray;">
    Để giúp tôi qua môn, bạn vui lòng đặt câu hỏi đầy đủ và chi tiết. Chúc một ngày vui!
    </p>
    """,
    unsafe_allow_html=True
)

# ======================
# INIT CLIENTS
# ======================

from chromadb.utils import embedding_functions

@st.cache_resource
def init_clients():
    # 1. API Key

    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    if not GOOGLE_API_KEY:
        raise RuntimeError("Missing GOOGLE_API_KEY")
    
    api_key = GOOGLE_API_KEY
    client_ai = genai.Client(api_key=api_key)

    # 2. Khai báo đúng hàm embedding bạn đã dùng lúc tạo DB
    # Lưu ý: model_name phải giống hệt lúc bạn tạo (BAAI/bge-m3)
    bge_m3_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="BAAI/bge-m3"
    )

    # 3. Kết nối ChromaDB
    chroma_client = chromadb.PersistentClient(CHROMA_PATH)
    try:
        collection = chroma_client.get_collection(
            name=COLLECTION_NAME, 
            embedding_function=bge_m3_ef # Truyền hàm này vào đây
        )
    except Exception as e:
        st.error(f"❌ Không tìm thấy collection hoặc lỗi model: {e}")
        st.stop()

    return client_ai, collection


client_ai, collection = init_clients()

# ======================
# SESSION STATE
# ======================
if "messages" not in st.session_state:
    st.session_state.messages = []

# ======================
# CHAT HISTORY
# ======================
# ======================
# CHAT HISTORY
# ======================
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        
        # Nếu là tin nhắn của AI và có dữ liệu debug thì hiển thị lại
        if msg["role"] == "assistant" and "debug" in msg:
            with st.expander("🔍 Chi tiết Context & Metadata (RAG Chunks)"):
                for item in msg["debug"]:
                    st.info(f"**Chunk #{item['id']}**")
                    st.code(item['content'], language=None)
                    st.json(item['metadata'])
            
            if "sources" in msg:
                with st.expander("📌 Nguồn tham khảo"):
                    for s in msg["sources"]:
                        st.markdown(s)

# ======================
# USER INPUT
# ======================
query = st.chat_input("💬 Nhập câu hỏi của bạn...")

if query:
    # User message
    st.session_state.messages.append(
        {"role": "user", "content": query}
    )
    with st.chat_message("user"):
        st.markdown(query)

    # ======================
    # RAG SEARCH
    # ======================
    with st.spinner("🔍 Đang tìm thông tin phù hợp..."):
        results = collection.query(
            query_texts=[query],
            n_results=TOP_K,
            include=["documents", "metadatas"]
        )

        contexts = []
        sources = []

        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            contexts.append(doc)

            source_line = f"- **{meta.get('breadcrumb','')}** | {meta.get('source','')}"
            sources.append(source_line)

        context_text = "\n\n".join(contexts)

        # ======================
        # PROMPT
        # ======================
        prompt = f"""
Bạn là chuyên viên tư vấn tuyển sinh của Trường Đại học Sư phạm TP.HCM.

Chỉ sử dụng thông tin trong CONTEXT để trả lời.
Trả lời ngắn gọn, rõ ràng, đúng trọng tâm.


Thông tin:
{context_text}

CÂU HỎI:
{query}

Nếu không có thông tin, hãy nói:
"Tôi không tìm thấy thông tin phù hợp trong dữ liệu hiện có."
"""

        try:
            response = client_ai.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            answer = response.text
        except Exception as e:
            answer = f"❌ Lỗi hệ thống: {e}"

    # ======================
    # ASSISTANT MESSAGE
# ======================
    # ASSISTANT MESSAGE
    # ======================
    with st.chat_message("assistant"):
        st.markdown(answer)
        
        # Tạo phần Debug Content để hiển thị các Chunk và Metadata
        debug_info = []
        for i, (doc, meta) in enumerate(zip(results["documents"][0], results["metadatas"][0])):
            chunk_data = {
                "id": i + 1,
                "content": doc,
                "metadata": meta
            }
            debug_info.append(chunk_data)
            
        # Hiển thị cho người dùng thấy ngay lúc đó
        with st.expander("🔍 Chi tiết Context & Metadata (RAG Chunks)"):
            for item in debug_info:
                st.info(f"**Chunk #{item['id']}**")
                st.code(item['content'], language=None)
                st.json(item['metadata'])

        if sources:
            with st.expander("📌 Nguồn tham khảo"):
                for s in sources:
                    st.markdown(s)

    # Lưu vào session_state bao gồm cả phần debug để không bị mất khi refresh
    st.session_state.messages.append(
        {
            "role": "assistant", 
            "content": answer, 
            "debug": debug_info,
            "sources": sources
        }
    )
