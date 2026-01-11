import os
import streamlit as st
import chromadb
from google import genai

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
        🔎 **Dữ liệu**: https://dgnl.hcmue.edu.vn/  
        🧠 **Mô hình**: Gemini 2.5 Flash  
        📚 **Kỹ thuật**: RAG + ChromaDB
        """
    )

    st.markdown("---")
    st.caption("© 2026 – by b4db0ybachkhoa")

# ======================
# MAIN TITLE
# ======================
st.markdown(
    """
    <h2 style="text-align:center;">🤖 QUA MÔN XÓA WEB</h2>
    <p style="text-align:center; color: gray;">
    Tra cứu nhanh các thông tin về kì thi ĐGNLCB - ĐGNL Tiếng Việt
    </p>
    """,
    unsafe_allow_html=True
)

# ======================
# INIT CLIENTS
# ======================
@st.cache_resource
def init_clients():
    api_key = "YOUR_API_KEY_HERE"
    if not api_key:
        st.error("❌ Chưa cấu hình GEMINI_API_KEY")
        st.stop()

    client_ai = genai.Client(api_key=api_key)

    chroma_client = chromadb.PersistentClient(CHROMA_PATH)
    try:
        collection = chroma_client.get_collection(COLLECTION_NAME)
    except:
        st.error("❌ Không tìm thấy Chroma_db collection")
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
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

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

QUY TẮC BẮT BUỘC:
- Nếu CONTEXT chứa nhiều năm khác nhau → KHÔNG tự suy đoán
- Cung cấp câu trả lời phải đính kèm theo năm, ưu tiên năm gần nhất
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
    with st.chat_message("assistant"):
        st.markdown(answer)

        if sources:
            with st.expander("📌 Nguồn tham khảo"):
                for s in sources:
                    st.markdown(s)

    st.session_state.messages.append(
        {"role": "assistant", "content": answer}
    )


