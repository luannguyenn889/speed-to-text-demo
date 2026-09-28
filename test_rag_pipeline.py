import os
import sys
from rag_module import index_documents, query_relevant_chunks, format_rag_context, get_rag_status
from pipeline_core import grade_with_gemini

print("=== 1. KIỂM TRA TRẠNG THÁI DOCUMENT & RAG ===")
status = get_rag_status()
print(f"Trạng thái: {status}")

print("\n=== 2. THỰC HIỆN INDEX TÀI LIỆU ===")
total = index_documents(force_reindex=False)
print(f"Tổng số chunks đã index: {total}")

print("\n=== 3. THỬ TRUY VẤN VỀ KIẾN THỨC CNPM ===")
test_query = "Mô hình Agile và Scrum có các đặc điểm và vai trò gì?"
results = query_relevant_chunks(test_query, top_k=2)
print(f"Tìm thấy {len(results)} đoạn liên quan:")
for i, r in enumerate(results, 1):
    print(f"\n--- Đoạn {i} (Nguồn: {r['source']}, Độ khớp: {r['similarity']}) ---")
    print(r['text'][:250] + ("..." if len(r['text']) > 250 else ""))

rag_context = format_rag_context(results)

print("\n=== 4. THỬ GỌI CHẤM ĐIỂM BẰNG GEMMA3:4B QUA OLLAMA KÈM RAG CONTEXT ===")
test_question = "Trình bày mô hình Agile và Scrum trong phát triển phần mềm."
test_rubric = "- Nêu rõ khái niệm Agile và Scrum (3 điểm)\n- Nêu các vai trò chính trong Scrum: Product Owner, Scrum Master, Dev Team (4 điểm)\n- Kỹ năng diễn đạt (3 điểm)"
test_student_answer = "Dạ thưa thầy, mô hình Agile là mô hình phát triển phần mềm linh hoạt, chia nhỏ công việc thành các chu kỳ ngắn gọi là sprint. Trong Scrum có các vai trò như Product Owner là người đại diện khách hàng quản lý backlog, Scrum Master là người hỗ trợ nhóm tuân thủ quy trình, và Development Team là đội ngũ trực tiếp lập trình và kiểm thử sản phẩm."

try:
    eval_result = grade_with_gemini(
        question=test_question,
        rubric=test_rubric,
        transcript=test_student_answer,
        api_key="",
        gemini_model="gemma3:4b (Local - Ollama)",
        rag_context=rag_context
    )
    print("\n✅ KẾT QUẢ CHẤM ĐIỂM TỪ GEMMA3:4B LOCAL:")
    import json
    print(json.dumps(eval_result, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"\n❌ Lỗi khi gọi gemma3:4b: {str(e)}")
