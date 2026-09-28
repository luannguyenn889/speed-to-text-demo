import os
import json
import time
from rag_module import query_relevant_chunks, format_rag_context
from pipeline_core import grade_with_gemini

# Câu hỏi nằm CHÍNH XÁC trong file "Bộ câu hỏi ôn tập CNPM.docx"
question = "Khung quy trình phát triển phần mềm Scrum gồm những giai đoạn và sự kiện nào? Trình bày vai trò của Scrum Master và Product Owner."

rubric = """- Nêu đầy đủ các sự kiện trong Scrum: Sprint, Sprint Planning, Daily Scrum, Sprint Review, Sprint Retrospective (4 điểm)
- Trình bày rõ vai trò của Product Owner và Scrum Master (4 điểm)
- Kỹ năng diễn đạt và thuật ngữ chuyên ngành (2 điểm)"""

# Câu trả lời của sinh viên (trả lời đúng 1 phần, thiếu nhiều sự kiện cốt lõi)
student_transcript = "Dạ thưa thầy, mô hình Scrum là quy trình linh hoạt. Trong Scrum có Product Owner chịu trách nhiệm về yêu cầu của khách hàng, còn Scrum Master là người hướng dẫn nhóm tuân thủ quy tắc. Về sự kiện thì em nhớ có họp hàng ngày và họp đánh giá sprint."

print("======================================================================")
print("🎯 BÀI KIỂM THỬ ĐỐI CHIẾU: CÓ RAG vs KHÔNG CÓ RAG")
print("======================================================================")
print(f"📌 Câu hỏi: {question}\n")
print(f"🎙️ Bài làm sinh viên:\n\"{student_transcript}\"\n")

# --- 1. CHẠY KHI BẬT RAG ---
print("----------------------------------------------------------------------")
print("1️⃣ TRƯỜNG HỢP 1: BẬT ĐỐI CHIẾU RAG (Truy xuất từ file Word trong document/)")
print("----------------------------------------------------------------------")
chunks = query_relevant_chunks(f"{question} {student_transcript}", top_k=2)
print(f"🔍 RAG đã tìm thấy {len(chunks)} đoạn chuẩn trong giáo trình:")
for i, c in enumerate(chunks, 1):
    print(f"  [{i}] File: {c['source']} | Độ tương đồng: {c['similarity']}")
    print(f"      Trích đoạn: {c['text'][:160]}...\n")

rag_context = format_rag_context(chunks)

print("🤖 Đang chấm bằng gemma3:4b (Có RAG Context)...")
start_time = time.time()
result_with_rag = grade_with_gemini(
    question=question,
    rubric=rubric,
    transcript=student_transcript,
    api_key="",
    gemini_model="gemma3:4b (Local - Ollama)",
    rag_context=rag_context
)
time_with_rag = round(time.time() - start_time, 1)

print(f"\n📊 KẾT QUẢ KHI CÓ RAG (Thời gian: {time_with_rag}s):")
print(f"Điểm số: {result_with_rag.get('score')}/10")
print(f"Nhận xét chung:\n{result_with_rag.get('summary')}")
print(f"Điểm yếu/thiếu sót:\n" + "\n".join([f"- {w}" for w in result_with_rag.get('weaknesses', [])]))

# --- 2. CHẠY KHI TẮT RAG ---
print("\n----------------------------------------------------------------------")
print("2️⃣ TRƯỜNG HỢP 2: TẮT RAG (Chỉ dựa vào kiến thức có sẵn của mô hình)")
print("----------------------------------------------------------------------")
print("🤖 Đang chấm bằng gemma3:4b (Không RAG)...")
start_time = time.time()
result_no_rag = grade_with_gemini(
    question=question,
    rubric=rubric,
    transcript=student_transcript,
    api_key="",
    gemini_model="gemma3:4b (Local - Ollama)",
    rag_context=""
)
time_no_rag = round(time.time() - start_time, 1)

print(f"\n📊 KẾT QUẢ KHI KHÔNG CÓ RAG (Thời gian: {time_no_rag}s):")
print(f"Điểm số: {result_no_rag.get('score')}/10")
print(f"Nhận xét chung:\n{result_no_rag.get('summary')}")
print(f"Điểm yếu/thiếu sót:\n" + "\n".join([f"- {w}" for w in result_no_rag.get('weaknesses', [])]))

# Lưu kết quả ra file JSON để xem lại
with open("demo_rag_comparison_result.json", "w", encoding="utf-8") as f:
    json.dump({
        "with_rag": result_with_rag,
        "without_rag": result_no_rag,
        "retrieved_chunks": chunks
    }, f, indent=2, ensure_ascii=False)

print("\n✅ Đã hoàn tất bài kiểm thử đối chiếu!")
