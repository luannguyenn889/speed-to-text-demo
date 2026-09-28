from rag_module import index_documents, query_relevant_chunks, get_rag_status

print("=" * 60)
print("📄 KIỂM TRA QUÉT VÀ TRÍCH XUẤT TÀI LIỆU PDF TRONG RAG")
print("=" * 60)

# 1. Lập chỉ mục lại gồm cả .docx, .txt, .pdf
total = index_documents(force_reindex=True)
print(f"✅ Tổng số đoạn đã lập chỉ mục: {total}")

status = get_rag_status()
print(f"📂 Các tệp tài liệu trong thư mục document/ ({len(status['files'])} tệp):")
for f in status['files']:
    print(f"   • {f}")

# 2. Thử truy vấn kiến thức nằm chính xác trong file PDF vừa thêm
print("\n" + "-" * 60)
query = "Unit Testing và Integration Testing khác nhau như thế nào trong kiểm thử phần mềm?"
print(f"🔍 Truy vấn: \"{query}\"")
print("-" * 60)

results = query_relevant_chunks(query, top_k=2)
for i, r in enumerate(results, 1):
    print(f"[{i}] Tệp nguồn: {r['source']} | Độ tương đồng: {r['similarity']} ({r.get('method')})")
    print(f"    Nội dung trích xuất:\n    {r['text']}\n")

print("=" * 60)
print("✅ HOÀN TẤT BÀI TEST QUÉT FILE PDF!")
