# Quy trình triển khai RAG dùng Markdown cho QNU AI VIVA

**Phiên bản:** 1.0  
**Ngày:** 26-09-2026  
**Tài liệu liên quan:** [Đề xuất RAG dùng Markdown](DE_XUAT_RAG_MARKDOWN.md)

## 1. Mục tiêu

Hướng dẫn triển khai theo từng giai đoạn để bổ sung kho Markdown có cấu trúc vào RAG hiện hữu của QNU AI VIVA. Sau triển khai, hệ thống cần:

- Nạp được `.md` UTF-8, giữ heading và metadata nguồn.
- Truy xuất được theo vector và BM25, có rerank như pipeline hiện tại.
- Đưa đoạn căn cứ kèm tên tài liệu, chương/mục và trang (khi có) vào kết quả chấm.
- Dùng được embedding local hiện tại cùng Ollama hoặc Gemini làm LLM sinh.
- Có thể đổi embedding về sau mà không trộn vector khác model hoặc làm mất index đang chạy.

Phạm vi giai đoạn đầu **không** gồm thay ChromaDB, chuyển toàn bộ giáo trình tự động sang Markdown, hoặc triển khai Gemini multimodal. Các phần đó chỉ thực hiện nếu retrieval benchmark cho thấy cần.

## 2. Nguyên tắc triển khai

1. Giữ nguyên PDF/DOCX gốc trong `document/`; Markdown là bản biên tập để index và kiểm tra bằng Git.
2. Giai đoạn đầu giữ encoder `paraphrase-multilingual-MiniLM-L12-v2`, ChromaDB, BM25/RRF và reranker hiện có.
3. Lưu cấu hình embedding cùng collection. Một collection chỉ chứa vector được tạo bởi cùng encoder và cùng dimension.
4. Index theo ID ổn định và hash nội dung; chạy lại ingestion không được nhân bản chunk.
5. Thử nghiệm với một chương đại diện trước khi chuyển toàn bộ tài liệu.
6. Trước mọi thao tác xóa/reindex, sao lưu `chroma_db/` và xác nhận đường dẫn sao lưu khác với thư mục database đang hoạt động.

## 3. Kết quả bàn giao

- Thư mục `knowledge/` có Markdown đã rà soát và quy ước front matter.
- Loader Markdown trong RAG ingestion, metadata đầy đủ và ID ổn định.
- Lệnh hoặc thao tác quản trị để index, xem trạng thái và tìm kiếm thử.
- Nguồn/heading/trang hiển thị trong kết quả RAG và context đưa vào chấm điểm.
- Bộ câu hỏi đánh giá retrieval cùng bảng kết quả baseline và sau thay đổi.
- Hướng dẫn backup, reindex và khôi phục.

## 4. Giai đoạn 0 — Chuẩn bị và ghi nhận baseline

### Thực hiện

1. Tạo nhánh Git riêng cho thay đổi RAG Markdown.
2. Ghi lại phiên bản Python/package, cấu hình model embedding, tên collection và số lượng chunk hiện tại từ chức năng trạng thái RAG.
3. Kiểm tra `document/` và `chroma_db/`; xác nhận dữ liệu nguồn hiện không bị chỉnh sửa bởi quy trình này.
4. Sao lưu ChromaDB trước khi phát triển hoặc reindex. Đóng ứng dụng trước khi sao chép thư mục DB để tránh tạo bản sao không nhất quán.
5. Chọn 20–50 câu hỏi đại diện từ đề thi/bộ câu hỏi. Với mỗi câu, ghi lại chương/đoạn nguồn kỳ vọng và các biến thể diễn đạt.
6. Chạy truy xuất hiện tại với các câu hỏi đó và lưu kết quả: nguồn trả về, thứ hạng, thời gian, có tìm thấy căn cứ đúng trong top 3/top 5 hay không.

### Tiêu chí hoàn thành

- Có bản sao lưu dùng được và ghi rõ vị trí.
- Có snapshot cấu hình/số chunk hiện tại.
- Có bảng baseline để so sánh; không đánh giá mô hình chỉ bằng vài câu hỏi thuận lợi.

## 5. Giai đoạn 1 — Thiết lập kho Markdown

### Thực hiện

1. Tạo cấu trúc ban đầu:

   ```text
   knowledge/
     cong-nghe-phan-mem/
     rubrics/
     images/
   ```

2. Chọn một chương có cấu trúc tương đối rõ, khuyến nghị chương 04 về System Modeling/UML, để làm pilot.
3. Chuyển nội dung PDF sang Markdown bằng quy trình phù hợp; giữ nguyên PDF nguồn. Rà soát thủ công tiêu đề, thuật ngữ, bảng, đánh số, sơ đồ và số trang.
4. Đặt metadata đầu file theo mẫu:

   ```yaml
   ---
   title: Mô hình hóa hệ thống bằng UML
   course: cong-nghe-phan-mem
   chapter: "04"
   source_file: "SE - Chương 04 - System-modeling.pdf"
   source_pages: "12-18"
   language: vi
   version: 1
   ---
   ```

5. Dùng heading Markdown có thứ bậc. Một mục nên tập trung vào một khái niệm; không đưa cả chương thành một khối lớn.
6. Với bảng, dùng Markdown table nếu cấu trúc vẫn dễ đọc. Với hình, giữ file riêng trong `knowledge/images/`, thêm caption có ý nghĩa và ghi trang nguồn.
7. So sánh ngẫu nhiên các mục Markdown với PDF; sửa lỗi OCR, dấu tiếng Việt, thứ tự cột và ký hiệu UML.

### Tiêu chí hoàn thành

- Pilot Markdown có front matter hợp lệ và encoding UTF-8.
- Nội dung quan trọng đối chiếu được với PDF nguồn; không mất bảng/hình cần cho câu hỏi môn học.
- Mỗi file có nguồn gốc rõ ràng.

## 6. Giai đoạn 2 — Bổ sung ingestion Markdown

### Thực hiện

1. Trong `rag_module.py`, cấu hình đường dẫn `KNOWLEDGE_DIR` riêng; không đổi `DOCS_DIR` để tránh nhập nhằng giữa file nguồn và tri thức đã biên tập.
2. Thêm quét đệ quy `knowledge/**/*.md`; bỏ qua file rỗng và file tạm.
3. Thêm parser front matter YAML. Nếu muốn tránh dependency mới, có thể bắt đầu với parser nhỏ có kiểm tra lỗi, nhưng quy ước front matter phải được xác định và không được parse bằng cách đoán tùy tiện.
4. Tạo parser heading để lưu `heading_path`, ví dụ `Mô hình hóa hệ thống > Biểu đồ tuần tự`.
5. Chia theo heading/đoạn trước, sau đó chia mục quá dài theo câu và giới hạn token/độ dài. Giữ nguyên bảng, code block, định nghĩa và danh sách rubric khi chúng còn vừa một chunk.
6. Đặt metadata cho mỗi chunk: `source_id`, `source_file`, `title`, `course`, `chapter`, `heading_path`, `page_start/page_end` nếu có, `chunk_index`, `content_hash`, `language`, `embedding_model`.
7. Sinh ID ổn định từ đường dẫn tương đối, heading, chỉ số chunk và hash. Cùng input tạo cùng ID; cập nhật nội dung phải thay chunk cũ tương ứng.
8. Nạp pilot Markdown vào **collection pilot riêng**, ví dụ `qnu_viva_markdown_pilot`; không xóa collection `qnu_viva_documents`.
9. Xác nhận BM25 được xây từ cùng những document ID và nội dung như dense index. Nếu BM25 vẫn được tái dựng trong bộ nhớ khi khởi động, bảo đảm thứ tự docs/metadatas thống nhất.
10. Ghi log rõ file thành công, file lỗi, số chunk, model, collection và thời gian.

### Tiêu chí hoàn thành

- Có thể nạp lại cùng một thư mục hai lần mà không nhân đôi dữ liệu.
- Mỗi kết quả truy xuất có source và heading; trang được hiển thị khi nguồn có cung cấp.
- Lỗi front matter/file không làm dừng toàn bộ ingestion; lỗi được báo cụ thể.
- Chỉ mục pilot riêng và collection hiện tại vẫn nguyên vẹn.

## 7. Giai đoạn 3 — Kết nối truy xuất và giao diện

### Thực hiện

1. Cập nhật trạng thái RAG để báo số file/chunk theo nguồn, collection, embedding model và thời điểm index.
2. Cập nhật hàm định dạng context để truyền `source_file`, `heading_path`, trang và nội dung; giữ format tương thích với prompt grading hiện tại.
3. Cập nhật kết quả tìm kiếm trong `app.py` để người dùng xem được nguồn/heading/trang kèm similarity/method.
4. Cập nhật prompt grading trong `pipeline_core.py`: chỉ dùng tài liệu làm căn cứ; nếu không thấy căn cứ phù hợp thì nêu rõ; không trình bày score truy xuất như độ chắc chắn.
5. Kiểm tra cả hai luồng sinh câu trả lời: Gemini API và Ollama. LLM sinh có thể đổi độc lập với embedding.
6. Nếu người dùng chọn chế độ Ollama, không cần gọi Gemini để embed query trong cấu hình local-first.

### Tiêu chí hoàn thành

- Câu hỏi tìm kiếm và bước chấm điểm cùng truy xuất được Markdown pilot.
- Kết quả trên UI hiển thị đủ thông tin để mở lại nguồn.
- Chuyển Gemini/Ollama không làm thay đổi collection hoặc model embedding.

## 8. Giai đoạn 4 — Đánh giá retrieval và điều chỉnh

### Thực hiện

1. Chạy lại bộ 20–50 câu hỏi từ baseline trên collection pilot.
2. Chấm thủ công liệu nguồn đúng có xuất hiện trong top 3 và top 5. Ghi false positive, false negative, câu hỏi thiếu nguồn.
3. So sánh các chế độ `dense`, `bm25`, `hybrid`, `hybrid + rerank` nếu app/module hỗ trợ.
4. Ghi `Recall@3`, `Recall@5`, MRR, độ trễ median và lỗi không có kết quả. Không dùng similarity score làm metric chất lượng duy nhất.
5. Điều chỉnh chunk size, overlap, top-k và cách phân đoạn theo lỗi quan sát được; thay từng nhóm tham số để biết nguyên nhân cải thiện.
6. Kiểm tra riêng câu hỏi có viết tắt/chính tả transcript sai, bảng/rubric, câu hỏi diễn đạt khác giáo trình.

### Tiêu chí hoàn thành

- Kết quả pilot bằng hoặc tốt hơn baseline trên các câu hỏi mục tiêu, hoặc có lý do rõ để tiếp tục điều chỉnh.
- Có ví dụ lỗi và thay đổi cấu hình tương ứng.
- Không chuyển toàn bộ corpus nếu chương pilot còn sai nội dung/metadata.

## 9. Giai đoạn 5 — Chuyển nội dung theo từng chương

### Thực hiện

1. Ưu tiên tài liệu thường dùng khi chấm: chương giáo trình, bộ câu hỏi ôn tập, rubric và tài liệu giảng viên xác nhận.
2. Chuyển từng chương; giữ cấu trúc `source_file`, trang và heading. Không đưa bản dịch/summary AI vào làm sự thật nguồn nếu chưa được rà soát.
3. Dùng collection pilot hoặc collection phiên bản mới để nhập dần. Theo dõi hash để chỉ cập nhật file thay đổi.
4. Với tài liệu PDF vẫn giữ loader cũ trong giai đoạn chuyển tiếp. Tránh ingest đồng thời PDF gốc và Markdown đã chuyển nếu nội dung trùng làm kết quả truy xuất lặp; chọn nguồn ưu tiên hoặc thêm metadata để lọc.
5. Chạy lại bộ câu hỏi đánh giá sau mỗi cụm chương và ghi nhận chất lượng.

### Tiêu chí hoàn thành

- Tài liệu ưu tiên đã được rà soát và truy xuất đúng.
- Kết quả trùng lặp được nhận diện/giảm thiểu.
- Có thể chỉ mục lại sau khi Markdown sửa mà không xóa nội dung không liên quan.

## 10. Giai đoạn 6 — Chốt collection và chuyển sang sử dụng

### Thực hiện

1. Tạo collection phát hành với tên có version/encoder, ví dụ `qnu_viva_md_st_v1`.
2. Reindex corpus đã phê duyệt vào collection mới; lưu cấu hình: embedding model, dimension, chunker version, ngày index.
3. Chạy bộ câu hỏi đánh giá lần cuối và kiểm tra trạng thái UI.
4. Chuyển cấu hình ứng dụng sang collection mới bằng một thay đổi có thể rollback nhanh.
5. Theo dõi lỗi truy xuất trong một thời gian vận hành; giữ collection cũ và backup cho đến khi xác nhận ổn định.
6. Chỉ dọn collection cũ theo quy trình riêng sau khi xác nhận backup và bản mới đủ tin cậy. Không xóa tự động khi khởi động app.

### Tiêu chí hoàn thành

- Collection phát hành được chọn rõ trong cấu hình.
- Rollback về collection cũ không cần dựng lại index.
- Đã ghi hướng dẫn index lại và phục hồi.

## 11. Quy trình thử embedding khác hoặc Gemini

Đây là nhánh đánh giá riêng, không nằm trong điều kiện cần để hoàn thành Markdown RAG.

1. Chọn bộ câu hỏi đánh giá cố định, khóa phiên bản corpus và chunker.
2. Tạo collection mới cho từng embedding, ví dụ `qnu_viva_gemini_embedding2_v1`; tuyệt đối không thêm vector model khác vào collection hiện tại.
3. Tạo embedding cho cả tài liệu và query bằng cùng provider/model/cấu hình dimension.
4. Đo Recall@k, MRR, latency, chi phí index/query, độ ổn định API và yêu cầu dữ liệu cloud.
5. Nếu model cải thiện đủ để chấp nhận chi phí/vận hành, chuyển bằng cấu hình collection. Nếu không, giữ encoder local.
6. Khi dùng Gemini API, quản lý API key qua biến môi trường/secret; không commit key. Ghi rõ rằng query, context và file ảnh gửi lên cloud.

**Kiểm tra tương thích:** tên model, model availability, SDK và quota cần được kiểm tra tại thời điểm triển khai theo tài liệu chính thức; không sao chép tên model cũ trong ví dụ codelab mà chưa xác nhận.

## 12. Vận hành thường ngày

### Khi thêm/sửa Markdown

1. Sửa file Markdown, giữ front matter và nguồn.
2. Đối chiếu phần thay đổi với PDF gốc.
3. Chạy ingestion ở chế độ cập nhật; xem log file/chunk thay đổi.
4. Tìm thử một số câu hỏi liên quan và xác nhận kết quả vẫn dẫn đến đúng heading/trang.
5. Commit Markdown và thay đổi cấu hình/prompt liên quan; không commit API key.

### Khi đổi embedding model

1. Tạo collection mới với tên version mới.
2. Index lại toàn bộ corpus bằng encoder mới.
3. Embed query bằng chính encoder mới.
4. So sánh với baseline trên cùng bộ câu hỏi.
5. Chuyển cấu hình và giữ collection cũ để rollback.

### Khi phục hồi sau sự cố

1. Dừng ứng dụng.
2. Lưu bản database hỏng để điều tra; không ghi đè bản sao lưu duy nhất.
3. Khôi phục bản `chroma_db/` đã sao lưu hoặc tạo collection mới rồi reindex từ `knowledge/`.
4. Khởi động app, xem trạng thái và chạy truy vấn kiểm tra theo checklist triển khai.

## 13. Checklist phát hành

- [ ] PDF/DOCX gốc được giữ nguyên.
- [ ] Markdown UTF-8, front matter và nguồn đã được rà soát.
- [ ] Loader đọc `.md` đệ quy và báo lỗi rõ ràng.
- [ ] Chunk giữ heading, bảng/định nghĩa quan trọng và metadata nguồn.
- [ ] ID ổn định; chạy lại index không nhân bản dữ liệu.
- [ ] Dense embedding và query dùng cùng model/dimension.
- [ ] BM25 và dense index tham chiếu cùng corpus.
- [ ] UI hiển thị nguồn/heading/trang khi có dữ liệu.
- [ ] Câu trả lời/chấm điểm thể hiện căn cứ và xử lý trường hợp thiếu căn cứ.
- [ ] Bộ câu hỏi đánh giá đạt tiêu chí nhóm thống nhất.
- [ ] Có backup, hướng dẫn rollback và không xóa collection cũ tự động.
- [ ] API key không nằm trong repo; chế độ cloud/local được xác định rõ.

## 14. Ước lượng thứ tự công việc

| Đợt | Nội dung | Phụ thuộc |
| --- | --- | --- |
| A | Baseline, backup, chọn pilot | Không |
| B | Markdown pilot và rà soát nội dung | A |
| C | Loader, metadata, stable IDs, collection pilot | B |
| D | Kết nối UI/context và nguồn trích dẫn | C |
| E | Đánh giá retrieval, chỉnh chunk/top-k | C–D |
| F | Chuyển từng chương và phát hành | E |
| G | Benchmark embedding/Gemini multimodal hoặc DB khác | F hoặc nhu cầu riêng |

Không gắn thời lượng cố định cho việc biên tập tài liệu vì khối lượng rà soát PDF, bảng và sơ đồ khác nhau theo từng chương. Có thể phát hành sau đợt F mà không cần đợt G.
