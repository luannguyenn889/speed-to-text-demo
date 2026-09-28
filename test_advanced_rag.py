import time
from rag_module import get_rag_status, query_relevant_chunks, format_rag_context

print("=" * 70)
print("🎯 BÀI TEST THỰC NGHIỆM NÂNG CẤP ADVANCED RAG (HYBRID SEARCH + RE-RANKING)")
print("=" * 70)

# 1. Kiểm tra trạng thái hệ thống RAG nâng cao
status = get_rag_status()
print("\n📊 1. TRẠNG THÁI HỆ THỐNG RAG HIỆN TẠI:")
for k, v in status.items():
    print(f"  • {k}: {v}")

# 2. Câu hỏi test chứa cả thuật ngữ viết tắt và giải thích quy trình
test_query = "Quy trình phát triển phần mềm Scrum có các vai trò chính nào và sự kiện Sprint Planning là gì?"
print(f"\n🔍 2. CÂU HỎI TRUY VẤN: \"{test_query}\"")

# --- Kịch bản 1: Chỉ dùng Dense Vector (ChromaDB cũ) ---
print("\n" + "-" * 70)
print("1️⃣ KỊCH BẢN 1: DENSE VECTOR SEARCH (ChromaDB đơn thuần)")
print("-" * 70)
t0 = time.time()
dense_results = query_relevant_chunks(test_query, top_k=2, search_mode="dense", use_rerank=False)
t_dense = round((time.time() - t0) * 1000, 1)
print(f"⏱️ Thời gian: {t_dense} ms | Số kết quả: {len(dense_results)}")
for i, r in enumerate(dense_results, 1):
    print(f"  [{i}] Độ khớp: {r.get('similarity')} | Nguồn: {r.get('source')}")
    print(f"      Nội dung: {r.get('text')[:140]}...\n")

# --- Kịch bản 2: Chỉ dùng BM25 Keyword Search ---
print("-" * 70)
print("2️⃣ KỊCH BẢN 2: SPARSE BM25 SEARCH (Từ khóa từ vựng)")
print("-" * 70)
t0 = time.time()
bm25_results = query_relevant_chunks(test_query, top_k=2, search_mode="bm25", use_rerank=False)
t_bm25 = round((time.time() - t0) * 1000, 1)
print(f"⏱️ Thời gian: {t_bm25} ms | Số kết quả: {len(bm25_results)}")
for i, r in enumerate(bm25_results, 1):
    print(f"  [{i}] Điểm BM25: {r.get('bm25_score')} | Nguồn: {r.get('source')}")
    print(f"      Nội dung: {r.get('text')[:140]}...\n")

# --- Kịch bản 3: Advanced Two-Stage Retrieval (Hybrid + Cross-Encoder Rerank) ---
print("-" * 70)
print("3️⃣ KỊCH BẢN 3: ADVANCED RAG (Hybrid Dense+BM25 + Cross-Encoder Reranking)")
print("-" * 70)
t0 = time.time()
adv_results = query_relevant_chunks(test_query, top_k=2, search_mode="hybrid", use_rerank=True)
t_adv = round((time.time() - t0) * 1000, 1)
print(f"⏱️ Thời gian: {t_adv} ms | Số kết quả: {len(adv_results)}")
for i, r in enumerate(adv_results, 1):
    print(f"  [{i}] Điểm Rerank: {r.get('rerank_score')} | Sigmoid Sim: {r.get('similarity')} | Phương thức: {r.get('method')}")
    print(f"      Nguồn: {r.get('source')}")
    print(f"      Nội dung: {r.get('text')[:160]}...\n")

print("-" * 70)
print("📋 ĐỊNH DẠNG CONTEXT ĐỂ NẠP VÀO PROMPT CHO LLM CHẤM ĐIỂM:")
print("-" * 70)
print(format_rag_context(adv_results))
print("=" * 70)
print("✅ HOÀN TẤT BÀI THỬ NGHIỆM ĐỐI CHUẨN RAG!")
