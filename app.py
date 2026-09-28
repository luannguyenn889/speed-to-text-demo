import os
import json
import time
import gradio as gr
from dotenv import load_dotenv

# Nạp biến môi trường từ .env nếu có
load_dotenv()

# Import các hàm core xử lý logic từ pipeline_core
from pipeline_core import (
    MODEL_QUOTAS,
    get_device,
    unload_whisper_models,
    load_whisper_model,
    transcribe_audio,
    load_phowhisper_pipeline,
    transcribe_with_phowhisper,
    transcribe_with_gemini_cloud,
    transcribe_with_groq,
    correct_transcript_with_gemini,
    grade_with_gemini,
    load_questions_from_file,
)
from test_models_excel import run_benchmark
from rag_module import (
    query_relevant_chunks,
    format_rag_context,
    get_rag_status,
    index_documents,
)

# --- Hàm xử lý các bước (Step Handlers) ---

# Xử lý Bước 1: Nhận diện giọng nói (Chỉ lấy văn bản thô)
def process_stt_step(audio_path, file_path, whisper_model, api_key, gemini_model, groq_api_key):
    try:
        media_path = file_path if file_path else audio_path
        if not media_path:
            raise ValueError("Không tìm thấy file âm thanh. Vui lòng tải lên hoặc ghi âm trực tiếp.")
            
        # Nhận diện giọng nói thô
        if whisper_model == "Gemini API (Cloud - Siêu Nhanh)":
            unload_whisper_models() # Giải phóng Whisper local để giải phóng RAM/VRAM
            # Nếu mô hình được chọn là gemma3:4b (Local - Ollama), ta ép dùng mô hình Cloud tương thích
            stt_model = gemini_model
            if stt_model == "gemma3:4b (Local - Ollama)":
                stt_model = "gemini-2.5-flash"
            transcript = transcribe_with_gemini_cloud(media_path, api_key, stt_model)
        elif whisper_model == "Groq API (Cloud - whisper-large-v3)":
            unload_whisper_models()
            transcript = transcribe_with_groq(media_path, groq_api_key)
        elif whisper_model == "PhoWhisper-small (Local - Tối ưu Tiếng Việt)":
            transcript = transcribe_with_phowhisper(media_path, "vinai/PhoWhisper-small")
        else:
            transcript = transcribe_audio(media_path, whisper_model)
            
        return (
            transcript,
            gr.update(visible=False, value="") # Ẩn panel lỗi nếu thành công
        )
    except Exception as e:
        error_msg = f"❌ **Lỗi ở Bước 1 (STT):** {str(e)}"
        print(error_msg)
        return (
            "", # transcript
            gr.update(visible=True, value=error_msg) # Hiện panel lỗi
        )
# Xử lý bước sửa lỗi chính tả bằng AI
def process_correction_ui(transcript, question, rubric, api_key, gemini_model):
    try:
        if not transcript or not transcript.strip():
            raise ValueError("Không tìm thấy văn bản để sửa lỗi chính tả. Vui lòng chạy Bước 1 trước.")
        corrected = correct_transcript_with_gemini(transcript, question, rubric, api_key, gemini_model)
        return (
            corrected,
            gr.update(visible=False, value="")
        )
    except Exception as e:
        error_msg = f"❌ **Lỗi sửa lỗi chính tả:** {str(e)}"
        print(error_msg)
        return (
            transcript,
            gr.update(visible=True, value=error_msg)
        )

# Hàm chuyển đổi nhận xét và điểm số thành giọng nói tiếng Việt (Text-to-Speech)
def generate_tts_feedback(score_html, summary_text):
    if not summary_text or not summary_text.strip():
        return (
            gr.update(value=None, visible=False),
            gr.update(visible=True, value="❌ **Lỗi:** Không có nội dung nhận xét để chuyển thành giọng nói.")
        )
    try:
        import re
        import os
        import time
        from gtts import gTTS
        
        # Thử trích xuất điểm số từ HTML (ví dụ: "8.5")
        score_str = ""
        if score_html:
            # Tìm số điểm trong tag HTML
            score_match = re.search(r'([0-9\.]+)\s*<span', score_html)
            if score_match:
                score_str = score_match.group(1)
        
        speech_parts = []
        if score_str:
            speech_parts.append(f"Kết quả đánh giá: {score_str} trên 10 điểm.")
        
        speech_parts.append("Nhận xét chi tiết từ giảng viên AI:")
        speech_parts.append(summary_text)
        
        full_speech_text = " ".join(speech_parts)
        
        # Loại bỏ các ký tự Markdown thông thường để giọng đọc trôi chảy
        clean_text = re.sub(r'[\*\#\_`\-]', '', full_speech_text)
        # Loại bỏ bớt emoji để tránh TTS đọc lỗi hoặc đọc ngắt quãng
        clean_text = re.sub(r'[^\w\s\d\.,\?\!:\-\(\)\[\]àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ]', ' ', clean_text)
        # Thu gọn khoảng trắng thừa
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        print(f"🎙️ Bắt đầu sinh âm thanh TTS từ văn bản: {clean_text[:60]}...")
        
        # Tạo thư mục audio nếu chưa tồn tại
        os.makedirs("audio", exist_ok=True)
        
        # Sử dụng timestamp để tránh cache trình duyệt cũ
        filename = f"feedback_{int(time.time())}.mp3"
        output_path = os.path.join("audio", filename)
        
        # Chuyển đổi giọng đọc tiếng Việt
        tts = gTTS(text=clean_text, lang='vi')
        tts.save(output_path)
        
        print(f"✅ Đã tạo thành công file âm thanh nhận xét tại: {output_path}")
        
        return (
            gr.update(value=output_path, visible=True),
            gr.update(visible=False, value="")
        )
    except Exception as e:
        error_msg = f"❌ **Lỗi khi tạo giọng nói AI:** {str(e)}"
        print(error_msg)
        return (
            gr.update(value=None, visible=False),
            gr.update(visible=True, value=error_msg)
        )

# Xử lý Bước 2: Chấm điểm dựa trên transcript (có tích hợp RAG)
def process_grading_step(question, rubric, transcript, api_key, gemini_model, enable_rag=True, rag_top_k=3):
    try:
        if not transcript or not transcript.strip():
            raise ValueError("Không tìm thấy văn bản bài làm. Hãy hoàn thành Bước 1 hoặc tự nhập văn bản vào ô ký âm trước.")
            
        rag_context = ""
        rag_display_md = ""
        
        if enable_rag:
            print(f"🔍 Đang kích hoạt RAG: Truy vấn tài liệu giáo trình (Top-{rag_top_k})...")
            query_str = f"{question} {transcript}"
            chunks = query_relevant_chunks(query_str, top_k=int(rag_top_k))
            if chunks:
                rag_context = format_rag_context(chunks)
                items = []
                for i, c in enumerate(chunks, 1):
                    preview_text = c['text'].strip()
                    items.append(
                        f"**[{i}] Nguồn: `{c['source']}`** (Độ tương đồng ngữ nghĩa: **{c['similarity']}**)\n\n"
                        f"> {preview_text}"
                    )
                rag_display_md = "\n\n---\n\n".join(items)
            else:
                rag_display_md = "ℹ️ *Không tìm thấy đoạn kiến thức phù hợp trong tài liệu hoặc thư mục document/ chưa có file.*"
        else:
            rag_display_md = "⏸️ *Chế độ đối chiếu tài liệu RAG đang tắt.*"

        evaluation = grade_with_gemini(question, rubric, transcript, api_key, gemini_model, rag_context=rag_context)
        
        score = evaluation.get("score", "N/A")
        summary = evaluation.get("summary", "")
        
        strengths = evaluation.get("strengths", [])
        strengths_md = "".join([f"<div style='margin-bottom: 10px; line-height: 1.5;'>🔹 {s}</div>" for s in strengths]) if isinstance(strengths, list) else str(strengths)
        
        weaknesses = evaluation.get("weaknesses", [])
        weaknesses_md = "".join([f"<div style='margin-bottom: 10px; line-height: 1.5;'>🔸 {w}</div>" for w in weaknesses]) if isinstance(weaknesses, list) else str(weaknesses)
        
        improvement = evaluation.get("improvement", [])
        improvement_md = "".join([f"<div style='margin-bottom: 10px; line-height: 1.5;'>💡 {i}</div>" for i in improvement]) if isinstance(improvement, list) else str(improvement)
        
        score_html = f"""
        <div style="
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
            padding: 24px 20px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 4px 20px rgba(99, 102, 241, 0.25);
            margin-bottom: 20px;
        ">
            <span style="font-size: 1.1em; font-weight: 600; display: block; opacity: 0.9; letter-spacing: 1px; color: #ffffff !important;">KẾT QUẢ ĐÁNH GIÁ</span>
            <span style="font-size: 4em; font-weight: 800; display: block; margin: 10px 0 5px 0; font-family: system-ui, -apple-system, sans-serif; line-height: 1; color: #ffffff !important;">{score} <span style="font-size: 0.45em; font-weight: 400; opacity: 0.8; color: #e2e8f0 !important;">/ 10</span></span>
        </div>
        """
        
        return (
            score_html,
            summary,
            strengths_md,
            weaknesses_md,
            improvement_md,
            rag_display_md,
            gr.update(value=None, visible=False),
            gr.update(visible=False, value="")
        )
    except Exception as e:
        error_msg = f"❌ **Lỗi ở Bước 2 (Chấm điểm):** {str(e)}"
        print(error_msg)
        return (
            "", # score_html
            "", # summary
            "", # strengths_md
            "", # weaknesses_md
            "", # improvement_md
            "", # rag_display_md
            gr.update(value=None, visible=False),
            gr.update(visible=True, value=error_msg)
        )

# Hàm xử lý quét và lập chỉ mục lại tài liệu
def handle_reindex_ui():
    try:
        total = index_documents(force_reindex=True)
        return f"✅ Đã quét và lập chỉ mục thành công **{total}** đoạn văn bản từ thư mục `document/`."
    except Exception as e:
        return f"❌ Lỗi khi lập chỉ mục: {str(e)}"

# Hàm tra cứu trực tiếp tài liệu trong Tab RAG
def handle_rag_search_ui(query, top_k):
    if not query or not query.strip():
        return "⚠️ Vui lòng nhập từ khóa hoặc câu hỏi cần tra cứu."
    try:
        chunks = query_relevant_chunks(query, top_k=int(top_k))
        if not chunks:
            return "ℹ️ Không tìm thấy đoạn văn bản nào khớp trong cơ sở tri thức."
            
        md_results = [f"### 🔍 Kết quả tìm kiếm cho: *\"{query}\"* ({len(chunks)} đoạn trích xuất)\n"]
        for i, c in enumerate(chunks, 1):
            md_results.append(
                f"#### [{i}] 📄 `{c['source']}` (Độ tương đồng: `{c['similarity']}`)\n"
                f"{c['text']}\n"
            )
        return "\n\n---\n\n".join(md_results)
    except Exception as e:
        return f"❌ Lỗi khi tra cứu: {str(e)}"

def get_rag_status_markdown():
    status = get_rag_status()
    if status.get("status") == "error":
        return f"⚠️ **Trạng thái:** Lỗi ({status.get('error')})"
    files_list = "\n".join([f"- 📄 `{f}`" for f in status.get("files", [])])
    return f"""
- **Trạng thái:** 🟢 Sẵn sàng ({status.get('total_chunks')} đoạn trích xuất)
- **Mô hình Embedding:** `{status.get('model')}`
- **Số tài liệu trong document/:** {status.get('total_files')} file
{files_list if files_list else "*(Chưa có file nào)*"}
"""

# Hàm xử lý chạy thử nghiệm đa mô hình và xuất file Excel
def run_benchmark_ui(
    audio_mic,
    audio_file,
    custom_question,
    custom_rubric,
    selected_stt_models,
    selected_llm_models,
    enable_correction,
    api_key,
    groq_api_key
):
    media_path = audio_file if audio_file else audio_mic
    if not media_path:
        return (
            None,
            gr.update(value=None, visible=False),
            gr.update(visible=True, value="❌ **Lỗi:** Vui lòng ghi âm trực tiếp hoặc tải file âm thanh/video bài làm lên.")
        )
    if not custom_question or not custom_question.strip():
        return (
            None,
            gr.update(value=None, visible=False),
            gr.update(visible=True, value="❌ **Lỗi:** Vui lòng nhập nội dung câu hỏi thi.")
        )
    if not custom_rubric or not custom_rubric.strip():
        return (
            None,
            gr.update(value=None, visible=False),
            gr.update(visible=True, value="❌ **Lỗi:** Vui lòng nhập tiêu chí rubric chấm điểm.")
        )
    if not selected_stt_models:
        return (
            None,
            gr.update(value=None, visible=False),
            gr.update(visible=True, value="❌ **Lỗi:** Vui lòng chọn ít nhất 1 mô hình Ký âm (STT) để thử nghiệm.")
        )
    if not selected_llm_models:
        return (
            None,
            gr.update(value=None, visible=False),
            gr.update(visible=True, value="❌ **Lỗi:** Vui lòng chọn ít nhất 1 mô hình Chấm điểm (LLM) để đánh giá.")
        )

    try:
        output_file, df = run_benchmark(
            audio_path=media_path,
            question=custom_question.strip(),
            rubric=custom_rubric.strip(),
            stt_models=selected_stt_models,
            llm_models=selected_llm_models,
            enable_correction=enable_correction,
            gemini_api_key=api_key,
            groq_api_key=groq_api_key
        )
        return (
            df,
            gr.update(value=output_file, visible=True),
            gr.update(visible=True, value=f"🎉 **Thử nghiệm hoàn tất!** File Excel đã được tạo thành công: `{output_file}`")
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        error_msg = f"❌ **Lỗi khi chạy thử nghiệm đa mô hình:** {str(e)}"
        print(error_msg)
        return (
            None,
            gr.update(value=None, visible=False),
            gr.update(visible=True, value=error_msg)
        )

# Giao diện Gradio (Blocks)
custom_css = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

* {
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
}

.container {
    max-width: 1280px;
    margin: 0 auto;
    padding: 0 8px;
}

/* ===== HEADER ===== */
.header-box {
    text-align: center;
    margin-bottom: 28px;
    background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #4f46e5 100%);
    color: #ffffff !important;
    padding: 36px 32px 28px;
    border-radius: 20px;
    box-shadow: 0 8px 32px rgba(79, 70, 229, 0.35), 0 2px 8px rgba(0,0,0,0.15);
    position: relative;
    overflow: hidden;
}

.header-box::before {
    content: '';
    position: absolute;
    top: -60px; right: -60px;
    width: 220px; height: 220px;
    background: rgba(255,255,255,0.05);
    border-radius: 50%;
}

.header-box::after {
    content: '';
    position: absolute;
    bottom: -80px; left: -40px;
    width: 280px; height: 280px;
    background: rgba(255,255,255,0.04);
    border-radius: 50%;
}

.header-logo-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 20px;
    margin-bottom: 10px;
}

.header-logo-text {
    text-align: left;
}

.header-box h1 {
    font-size: 2em;
    font-weight: 800;
    margin: 0 0 4px 0;
    letter-spacing: -0.5px;
    line-height: 1.15;
    color: #ffffff !important;
}

.header-box .brand-name {
    font-size: 1.45em;
    font-weight: 800;
    color: #a5b4fc !important;
    letter-spacing: 2px;
    display: block;
    margin-bottom: 2px;
}

.header-box p {
    font-size: 0.95em;
    opacity: 0.9 !important;
    margin: 6px 0 0 0;
    font-weight: 400;
    line-height: 1.5;
    color: #e2e8f0 !important;
}

/* ===== SCORE CARD ===== */
.score-card {
    background: linear-gradient(135deg, #1e1b4b 0%, #4f46e5 100%);
    color: white;
    padding: 24px 20px;
    border-radius: 14px;
    text-align: center;
    box-shadow: 0 4px 20px rgba(79, 70, 229, 0.25);
    margin-bottom: 16px;
    position: relative;
    overflow: hidden;
}

/* ===== SECTIONS ===== */
.step-title {
    font-weight: 800;
    font-size: 1.1em;
    color: #4f46e5;
    padding: 8px 12px;
    background: #e0e7ff;
    border-radius: 8px;
    margin-bottom: 12px;
    letter-spacing: 0.5px;
    border-left: 5px solid #4f46e5;
}

.section-main-title {
    font-weight: 800;
    font-size: 1.25em;
    color: #1e1b4b;
    margin-bottom: 16px;
    border-bottom: 2px solid #e2e8f0;
    padding-bottom: 6px;
}

/* ===== FOOTER ===== */
.footer-text {
    text-align: center;
    font-size: 0.88em;
    color: #94a3b8;
    margin-top: 32px;
    padding: 16px 0 8px;
    border-top: 1px solid #e2e8f0;
}

.footer-text strong {
    color: #475569;
}

/* ===== BUTTONS ===== */
button.primary {
    background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%) !important;
    border: none !important;
    box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35) !important;
    font-weight: 700 !important;
    letter-spacing: 0.5px !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease !important;
}

button.primary:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(99, 102, 241, 0.45) !important;
}

/* ===== ERROR ===== */
#error-msg {
    background: #fff1f2;
    border: 1px solid #fecdd3;
    border-radius: 10px;
    padding: 12px 16px;
    color: #be123c;
    font-size: 0.93em;
    margin-bottom: 12px;
}

/* ===== EVALUATION CARDS ===== */
.eval-card {
    padding: 16px 20px !important;
    border-radius: 12px !important;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05) !important;
    margin-bottom: 12px !important;
    transition: transform 0.2s ease, box-shadow 0.2s ease !important;
}
.eval-card:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.08) !important;
}
.eval-strengths {
    background-color: #f0fdf4 !important;
    border: 1px solid #bbf7d0 !important;
}
.eval-weaknesses {
    background-color: #fffbfa !important;
    border: 1px solid #fed7aa !important;
}
.eval-improvements {
    background-color: #f5f3ff !important;
    border: 1px solid #ddd6fe !important;
}
.eval-card h3 {
    margin-top: 0 !important;
    font-weight: 700 !important;
}
"""

with gr.Blocks() as demo:
    with gr.Column(elem_classes="container"):
        # Header với Logo QNU AI VIVA
        with gr.Column(elem_classes="header-box"):
            gr.HTML("""
                <div class="header-logo-wrap">
                    <svg width="90" height="90" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
                        <!-- Globe background circle -->
                        <circle cx="95" cy="105" r="80" fill="none" stroke="#93c5fd" stroke-width="5"/>
                        <!-- Horizontal lines -->
                        <ellipse cx="95" cy="105" rx="80" ry="30" fill="none" stroke="#93c5fd" stroke-width="3.5"/>
                        <ellipse cx="95" cy="105" rx="55" ry="72" fill="none" stroke="#93c5fd" stroke-width="3.5"/>
                        <line x1="15" y1="105" x2="175" y2="105" stroke="#93c5fd" stroke-width="3.5"/>
                        <line x1="20" y1="73" x2="170" y2="73" stroke="#93c5fd" stroke-width="2.5"/>
                        <line x1="20" y1="137" x2="170" y2="137" stroke="#93c5fd" stroke-width="2.5"/>
                        <!-- QN letters -->
                        <text x="95" y="120" text-anchor="middle" font-family="Arial Black, sans-serif" font-weight="900" font-size="62" fill="#ffffff">QN</text>
                        <!-- Red speech bubble -->
                        <ellipse cx="158" cy="40" rx="22" ry="18" fill="#ef4444"/>
                        <polygon points="145,52 155,62 162,52" fill="#ef4444"/>
                    </svg>
                    <div class="header-logo-text">
                        <span class="brand-name">QNU AI VIVA</span>
                        <h1>Hệ Thống Chấm Điểm Thi Vấn Đáp AI</h1>
                        <p>Hệ thống thi vấn đáp thông minh • Tách biệt Nhận diện giọng nói &amp; Chấm điểm AI (Sửa lỗi chính tả bằng AI)</p>
                    </div>
                </div>
            """)
        
        # API Keys dùng chung
        api_key_input = gr.Textbox(
            label="Gemini API Key",
            type="password",
            value=os.environ.get("GEMINI_API_KEY", ""),
            visible=False,
        )
        groq_api_key_input = gr.Textbox(
            label="Groq API Key",
            type="password",
            value=os.environ.get("GROQ_API_KEY", ""),
            visible=False,
        )

        presets = load_questions_from_file("BỘ ĐỀ THI.txt")
        preset_titles = list(presets.keys())

        with gr.Tabs():
            # ==================== TAB 1: CHẤM ĐIỂM TRỰC TIẾP ====================
            with gr.Tab("🎯 Chấm Điểm Thi Vấn Đáp Trực Tiếp"):
                error_panel = gr.Markdown(visible=False, elem_id="error-msg")
                
                with gr.Row():
                    # Cột trái: Cấu hình và Quy trình các bước
                    with gr.Column(scale=11):
                        gr.Markdown("<div class='section-main-title'>⚙️ CẤU HÌNH & THIẾT LẬP</div>")
                        
                        with gr.Group():
                            gemini_model_input = gr.Dropdown(
                                choices=["gemini-2.5-flash", "gemini-2.5-pro", "gemini-3.5-flash", "gemini-flash-latest", "gemini-pro-latest", "gemma3:4b (Local - Ollama)"],
                                value="gemini-2.5-flash",
                                label="1. Chọn mô hình Gemini/Gemma dùng để Chấm điểm / STT Cloud",
                            )
                            
                            quota_info = gr.Markdown(
                                value=MODEL_QUOTAS["gemini-2.5-flash"],
                            )

                            gemini_correct_model_input = gr.Dropdown(
                                choices=["gemini-2.5-flash", "gemini-2.5-pro", "gemini-3.5-flash", "gemini-flash-latest", "gemini-pro-latest", "gemma3:4b (Local - Ollama)"],
                                value="gemini-2.5-flash",
                                label="1b. Chọn mô hình Gemini/Gemma dùng để Sửa chính tả AI",
                            )

                            correct_quota_info = gr.Markdown(
                                value=MODEL_QUOTAS["gemini-2.5-flash"],
                            )
                        
                        gr.Markdown("<div class='step-title'>🎙️ BƯỚC 1: CHUYỂN GIỌNG NÓI THÀNH VĂN BẢN</div>")
                        with gr.Group():
                            whisper_model_input = gr.Dropdown(
                                choices=["Gemini API (Cloud - Siêu Nhanh)", "Groq API (Cloud - whisper-large-v3)", "PhoWhisper-small (Local - Tối ưu Tiếng Việt)", "tiny", "base", "small", "medium"],
                                value="base",
                                label="Phương thức chuyển đổi giọng nói (Chọn Gemini hoặc Groq Cloud để tăng tốc)",
                            )
                            
                            with gr.Tab("🎙️ Ghi âm trực tiếp"):
                                audio_input = gr.Audio(
                                    label="Nhấn nút để ghi âm câu trả lời",
                                    sources=["microphone"],
                                    type="filepath",
                                )
                            with gr.Tab("📁 Tải file bài làm"):
                                file_input = gr.File(
                                    label="Tải lên file âm thanh hoặc video (.mp3, .wav, .m4a, .mp4...)",
                                    file_types=["audio", "video"],
                                    type="filepath",
                                )
                            
                            stt_btn = gr.Button("🎙️ Bước 1: Ký Âm Giọng Nói", variant="primary", size="lg")
                        
                        gr.Markdown("<div class='step-title'>⚡ BƯỚC 2: CHẤM ĐIỂM THI VẤN ĐÁP</div>")
                        with gr.Group():
                            question_preset_dropdown = gr.Dropdown(
                                choices=["-- Chọn câu hỏi từ bộ đề thi mẫu --"] + preset_titles,
                                value="-- Chọn câu hỏi từ bộ đề thi mẫu --",
                                label="Chọn nhanh câu hỏi từ bộ đề thi mẫu (BỘ ĐỀ THI.txt)",
                            )
                            
                            question_input = gr.Textbox(
                                label="Câu hỏi thi vấn đáp",
                                placeholder="Nhập nội dung câu hỏi thi vấn đáp...",
                                lines=2,
                                value="Trình bày khái niệm và vai trò của lập trình hướng đối tượng (OOP). Nêu 4 tính chất cơ bản của OOP.",
                            )
                            
                            rubric_input = gr.Textbox(
                                label="Tiêu chí chấm điểm (Rubric)",
                                placeholder="Nhập tiêu chí chấm điểm chi tiết tương ứng...",
                                lines=4,
                                value="- Trình bày rõ định nghĩa OOP (1.5 điểm)\n- Nêu đúng tên và định nghĩa ngắn gọn 4 tính chất: Đóng gói, Kế thừa, Đa hình, Trừu tượng (Mỗi tính chất 1.5 điểm, tổng 6.0 điểm)\n- Lấy ví dụ minh họa thực tế dễ hiểu (1.5 điểm)\n- Kỹ năng diễn đạt, trả lời lưu loát (1.0 điểm)",
                            )
                            
                            with gr.Accordion("📚 Đối Chiếu Giáo Trình/Tài Liệu Môn Học (Local RAG)", open=True):
                                with gr.Row():
                                    enable_rag_cb = gr.Checkbox(
                                        label="Bật đối chiếu tài liệu môn học (RAG)",
                                        value=True,
                                        info="Tự động trích xuất các đoạn tài liệu liên quan từ thư mục document/ để chấm điểm"
                                    )
                                    rag_top_k_slider = gr.Slider(
                                        minimum=1, maximum=5, value=3, step=1,
                                        label="Số đoạn tham chiếu (Top-K)"
                                    )
                                with gr.Row():
                                    reindex_btn = gr.Button("🔄 Quét lại thư mục document/", size="sm")
                                    reindex_status = gr.Markdown(value="*Trạng thái: Đã sẵn sàng đối chiếu tài liệu.*")
                            
                            grade_btn = gr.Button("⚡ Bước 2: Chấm Điểm & Đánh Giá AI", variant="primary", size="lg")
                    
                    # Cột phải: Ký âm và Kết quả chấm điểm
                    with gr.Column(scale=9):
                        gr.Markdown("<div class='section-main-title'>📝 KÝ ÂM & ĐÁNH GIÁ CHI TIẾT</div>")
                        
                        transcript_output = gr.Textbox(
                            label="Văn bản nhận dạng được (Có thể chỉnh sửa trực tiếp)",
                            placeholder="Kết quả chuyển giọng nói ở Bước 1 sẽ hiển thị ở đây. Hãy đọc, chỉnh sửa các lỗi chính tả nếu có hoặc nhấn nút sửa chính tả bằng AI bên dưới...",
                            lines=8,
                            interactive=True,
                        )
                        
                        correct_btn = gr.Button("✨ Tự Động Sửa Lỗi Chính Tả Bằng AI", variant="secondary")
                        
                        score_output = gr.HTML()
                        
                        summary_output = gr.Textbox(
                            label="📋 Nhận xét chung của giảng viên AI",
                            lines=5,
                            interactive=False,
                        )
                        
                        with gr.Accordion("📖 Đoạn Trích Giáo Trình Đã Đối Chiếu (RAG Context)", open=False):
                            rag_context_output = gr.Markdown(value="*Chưa có dữ liệu đối chiếu. Hãy bấm 'Bước 2: Chấm Điểm' để trích xuất.*")
                        
                        with gr.Row():
                            tts_btn = gr.Button("🔊 Nghe Nhận Xét Bằng Giọng Nói AI", variant="secondary")
                        
                        tts_audio_output = gr.Audio(
                            label="🔊 Giọng đọc nhận xét AI",
                            interactive=False,
                            autoplay=True,
                            visible=False
                        )
                        
                        with gr.Row():
                            with gr.Column(scale=1, elem_classes="eval-card eval-strengths"):
                                gr.Markdown("### ✅ Điểm mạnh")
                                strengths_output = gr.Markdown()
                            with gr.Column(scale=1, elem_classes="eval-card eval-weaknesses"):
                                gr.Markdown("### ⚠️ Điểm yếu / Thiếu sót")
                                weaknesses_output = gr.Markdown()
                            with gr.Column(scale=1, elem_classes="eval-card eval-improvements"):
                                gr.Markdown("### 💡 Gợi ý cải thiện")
                                improvement_output = gr.Markdown()

            # ==================== TAB 2: THỬ NGHIỆM ĐA MÔ HÌNH & XUẤT EXCEL ====================
            with gr.Tab("📊 Thử Nghiệm Đa Mô Hình & Xuất Báo Cáo Excel"):
                bm_status_panel = gr.Markdown(visible=False, elem_id="error-msg")
                
                with gr.Row():
                    with gr.Column(scale=8):
                        gr.Markdown("<div class='section-main-title'>📁 DỮ LIỆU ĐẦU VÀO & CẤU HÌNH TEST</div>")
                        
                        bm_preset_dropdown = gr.Dropdown(
                            choices=["-- Chọn câu hỏi từ bộ đề thi mẫu --"] + preset_titles,
                            value="-- Chọn câu hỏi từ bộ đề thi mẫu --",
                            label="Chọn câu hỏi từ bộ đề thi mẫu (BỘ ĐỀ THI.txt)",
                        )
                        
                        bm_question_input = gr.Textbox(
                            label="Câu hỏi thi vấn đáp",
                            lines=2,
                            value="Trình bày khái niệm và vai trò của lập trình hướng đối tượng (OOP). Nêu 4 tính chất cơ bản của OOP.",
                        )
                        
                        bm_rubric_input = gr.Textbox(
                            label="Tiêu chí chấm điểm (Rubric)",
                            lines=4,
                            value="- Trình bày rõ định nghĩa OOP (1.5 điểm)\n- Nêu đúng tên và định nghĩa ngắn gọn 4 tính chất: Đóng gói, Kế thừa, Đa hình, Trừu tượng (Mỗi tính chất 1.5 điểm, tổng 6.0 điểm)\n- Lấy ví dụ minh họa thực tế dễ hiểu (1.5 điểm)\n- Kỹ năng diễn đạt, trả lời lưu loát (1.0 điểm)",
                        )
                        
                        with gr.Tab("📁 Tải file bài làm test"):
                            bm_file_input = gr.File(
                                label="Tải lên file âm thanh hoặc video bài làm (.mp3, .wav, .m4a, .mp4...)",
                                file_types=["audio", "video"],
                                type="filepath",
                            )
                        with gr.Tab("🎙️ Ghi âm bài làm test"):
                            bm_audio_input = gr.Audio(
                                label="Ghi âm câu trả lời test",
                                sources=["microphone"],
                                type="filepath",
                            )
                        
                        gr.Markdown("<div class='step-title'>🤖 LỰA CHỌN CÁC MÔ HÌNH THỬ NGHIỆM</div>")
                        
                        bm_stt_checkbox = gr.CheckboxGroup(
                            choices=[
                                "tiny",
                                "base",
                                "small",
                                "PhoWhisper-small (Local - Tối ưu Tiếng Việt)",
                                "Groq API (Cloud - whisper-large-v3)",
                                "Gemini API (Cloud - Siêu Nhanh)"
                            ],
                            value=["base", "Groq API (Cloud - whisper-large-v3)", "Gemini API (Cloud - Siêu Nhanh)"],
                            label="1. Các mô hình Ký âm (STT) cần so sánh:",
                        )
                        
                        bm_llm_checkbox = gr.CheckboxGroup(
                            choices=[
                                "gemini-2.5-flash",
                                "gemini-3.5-flash",
                                "gemini-flash-latest",
                                "gemini-2.5-pro",
                                "gemma3:4b (Local - Ollama)"
                            ],
                            value=["gemini-2.5-flash", "gemini-3.5-flash"],
                            label="2. Các mô hình LLM Chấm điểm cần so sánh:",
                        )
                        
                        bm_correction_checkbox = gr.Checkbox(
                            label="✨ Bật bước tự động sửa lỗi chính tả bằng AI trước khi chấm điểm",
                            value=True,
                        )
                        
                        bm_run_btn = gr.Button("🚀 Chạy Thử Nghiệm Toàn Diện & Xuất Excel", variant="primary", size="lg")
                    
                    with gr.Column(scale=12):
                        gr.Markdown("<div class='section-main-title'>📊 BÁO CÁO SO SÁNH & TẢI VỀ EXCEL</div>")
                        
                        bm_file_output = gr.File(
                            label="📥 Tải về tệp báo cáo Excel (.xlsx)",
                            interactive=False,
                            visible=False
                        )
                        
                        bm_df_output = gr.Dataframe(
                            label="📋 Bảng Kết Quả Thử Nghiệm Đa Mô Hình",
                            interactive=False,
                            wrap=True
                        )

            # ==================== TAB 3: TRA CỨU & QUẢN LÝ TRI THỨC RAG ====================
            with gr.Tab("📚 Tra Cứu & Quản Lý Tri Thức RAG"):
                with gr.Row():
                    with gr.Column(scale=5):
                        gr.Markdown("<div class='section-main-title'>📂 QUẢN LÝ KHO TÀI LIỆU</div>")
                        rag_status_display = gr.Markdown(value=get_rag_status_markdown())
                        rag_reindex_full_btn = gr.Button("🔄 Quét và Lập Chỉ Mục Lại Toàn Bộ (Force Re-index)", variant="primary")
                        rag_reindex_info = gr.Markdown(value="")
                    with gr.Column(scale=7):
                        gr.Markdown("<div class='section-main-title'>🔍 TRA CỨU NGỮ NGHĨA TRONG GIÁO TRÌNH</div>")
                        rag_test_query_input = gr.Textbox(
                            label="Nhập câu hỏi hoặc khái niệm cần tra cứu",
                            placeholder="Ví dụ: Mô hình phát triển phần mềm Agile, Scrum, Kiểm thử hộp đen...",
                            lines=2,
                            value="Mô hình phát triển phần mềm linh hoạt Agile và Scrum có các vai trò gì?"
                        )
                        rag_test_top_k = gr.Slider(minimum=1, maximum=5, value=3, step=1, label="Số đoạn trích xuất (Top-K)")
                        rag_search_btn = gr.Button("🔎 Tìm Kiếm Đoạn Văn Bản Liên Quan Nhất", variant="secondary")
                        rag_search_results = gr.Markdown(value="*Nhập từ khóa và bấm 'Tìm Kiếm' để xem trích xuất từ tài liệu docx...*")

        # Footer
        gr.HTML("""
            <div class="footer-text">
                <p>Đề tài: "Xây dựng phần mềm hỗ trợ ôn luyện thi vấn đáp sử dụng AI" &copy; 2026. Hỗ trợ chạy local offline + Cloud API mới.</p>
            </div>
        """)
        
        # --- CẤU HÌNH SỰ KIỆN CLICK TAB 1 ---
        stt_btn.click(
            fn=process_stt_step,
            inputs=[
                audio_input,
                file_input,
                whisper_model_input,
                api_key_input,
                gemini_model_input,
                groq_api_key_input
            ],
            outputs=[
                transcript_output,
                error_panel
            ]
        )
        
        correct_btn.click(
            fn=process_correction_ui,
            inputs=[
                transcript_output,
                question_input,
                rubric_input,
                api_key_input,
                gemini_correct_model_input
            ],
            outputs=[
                transcript_output,
                error_panel
            ]
        )
        
        grade_btn.click(
            fn=process_grading_step,
            inputs=[
                question_input,
                rubric_input,
                transcript_output,
                api_key_input,
                gemini_model_input,
                enable_rag_cb,
                rag_top_k_slider
            ],
            outputs=[
                score_output,
                summary_output,
                strengths_output,
                weaknesses_output,
                improvement_output,
                rag_context_output,
                tts_audio_output,
                error_panel
            ]
        )
        
        reindex_btn.click(
            fn=handle_reindex_ui,
            inputs=[],
            outputs=[reindex_status]
        )
        
        rag_reindex_full_btn.click(
            fn=lambda: (handle_reindex_ui(), get_rag_status_markdown()),
            inputs=[],
            outputs=[rag_reindex_info, rag_status_display]
        )
        
        rag_search_btn.click(
            fn=handle_rag_search_ui,
            inputs=[rag_test_query_input, rag_test_top_k],
            outputs=[rag_search_results]
        )
        
        tts_btn.click(
            fn=generate_tts_feedback,
            inputs=[
                score_output,
                summary_output
            ],
            outputs=[
                tts_audio_output,
                error_panel
            ]
        )
        
        def update_quota_info(model_name):
            return MODEL_QUOTAS.get(model_name, "ℹ️ Hạn mức tùy thuộc vào tài khoản của bạn.")
        
        gemini_model_input.change(
            fn=update_quota_info,
            inputs=[gemini_model_input],
            outputs=[quota_info]
        )

        gemini_correct_model_input.change(
            fn=update_quota_info,
            inputs=[gemini_correct_model_input],
            outputs=[correct_quota_info]
        )

        def on_preset_change(selected_title):
            if selected_title in presets:
                return (
                    presets[selected_title]["question"],
                    presets[selected_title]["rubric"]
                )
            return (
                "Trình bày khái niệm và vai trò của lập trình hướng đối tượng (OOP). Nêu 4 tính chất cơ bản của OOP.",
                "- Trình bày rõ định nghĩa OOP (1.5 điểm)\n- Nêu đúng tên và định nghĩa ngắn gọn 4 tính chất: Đóng gói, Kế thừa, Đa hình, Trừu tượng (Mỗi tính chất 1.5 điểm, tổng 6.0 điểm)\n- Lấy ví dụ minh họa thực tế dễ hiểu (1.5 điểm)\n- Kỹ năng diễn đạt, trả lời lưu loát (1.0 điểm)"
            )

        question_preset_dropdown.change(
            fn=on_preset_change,
            inputs=[question_preset_dropdown],
            outputs=[question_input, rubric_input]
        )

        # --- CẤU HÌNH SỰ KIỆN CLICK TAB 2 (BENCHMARK) ---
        bm_preset_dropdown.change(
            fn=on_preset_change,
            inputs=[bm_preset_dropdown],
            outputs=[bm_question_input, bm_rubric_input]
        )

        bm_run_btn.click(
            fn=run_benchmark_ui,
            inputs=[
                bm_audio_input,
                bm_file_input,
                bm_question_input,
                bm_rubric_input,
                bm_stt_checkbox,
                bm_llm_checkbox,
                bm_correction_checkbox,
                api_key_input,
                groq_api_key_input
            ],
            outputs=[
                bm_df_output,
                bm_file_output,
                bm_status_panel
            ]
        )

if __name__ == "__main__":
    # Chạy giao diện cục bộ
    demo.launch(
        server_name="127.0.0.1", 
        server_port=7860, 
        share=False,
        theme=gr.themes.Soft(),
        css=custom_css
    )

