import os
import json
import threading
import time
import requests
from google import genai
from google.genai import types
from groq import Groq

# Cấu hình Schema định dạng JSON bằng dict để tương thích tối đa với google-genai
evaluation_schema = {
    "type": "OBJECT",
    "properties": {
        "score": {"type": "NUMBER", "description": "Điểm số đánh giá trên thang 10"},
        "summary": {"type": "STRING", "description": "Nhận xét chung chi tiết"},
        "strengths": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "Danh sách 3 điểm mạnh"
        },
        "weaknesses": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "Danh sách 3 điểm yếu hoặc thiếu sót"
        },
        "improvement": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "Danh sách gợi ý cải thiện"
        }
    },
    "required": ["score", "summary", "strengths", "weaknesses", "improvement"]
}

# Hạn mức của từng model để hiển thị thông tin
MODEL_QUOTAS = {
    "gemini-2.5-flash": "ℹ️ **Hạn mức Free Tier:** 15 yêu cầu/phút (RPM), 1.500 yêu cầu/ngày (RPD). Phản hồi rất nhanh và tối ưu nhất hiện tại.",
    "gemini-2.5-pro": "⚠️ **Hạn mức Free Tier:** Cực thấp - **2 yêu cầu/phút (RPM)**, 50 yêu cầu/ngày (RPD). Dễ bị lỗi quá tải (429) nếu gọi liên tục.",
    "gemini-3.5-flash": "ℹ️ **Hạn mức:** Phụ thuộc vào tài khoản phát triển của bạn.",
    "gemini-flash-latest": "ℹ️ **Hạn mức:** Mô hình Gemini Flash ổn định (gemini-1.5-flash).",
    "gemini-pro-latest": "⚠️ **Hạn mức:** Mô hình Gemini Pro ổn định (gemini-1.5-pro) - Tốc độ cao.",
    "gemma3:4b (Local - Ollama)": "💻 **Chạy Offline Local:** Sử dụng Ollama chạy mô hình Gemma 3 4B ngay trên máy tính của bạn. Không tốn phí, không giới hạn request, bảo mật tuyệt đối."
}

# Tự động phát hiện GPU/CUDA cho Whisper Local (Lazy-loaded)
_device = None

def get_device():
    global _device
    if _device is None:
        import torch
        _device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🚀 Hệ thống đang sử dụng thiết bị: {_device.upper()}")
    return _device

def get_audio_duration(file_path):
    """Lấy thời lượng âm thanh/video (tính bằng giây)"""
    if not file_path or not os.path.exists(file_path):
        return 0.0
    try:
        import subprocess
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return round(float(result.stdout.strip()), 2)
    except Exception as e:
        # Fallback bằng wave nếu là file wav
        try:
            import wave
            import contextlib
            with contextlib.closing(wave.open(file_path, 'r')) as f:
                frames = f.getnframes()
                rate = f.getframerate()
                return round(frames / float(rate), 2)
        except Exception:
            return 0.0

# Cơ chế cache mô hình Whisper để tránh load lại nhiều lần
model_cache = {}
phowhisper_pipeline_cache = {}
model_lock = threading.Lock()

def unload_whisper_models(exclude=None):
    """Giải phóng các mô hình Whisper khỏi bộ nhớ RAM/VRAM để trả lại tài nguyên"""
    with model_lock:
        # Giải phóng OpenAI Whisper
        models_to_remove = [k for k in model_cache.keys() if k != exclude]
        if models_to_remove:
            print(f"🧹 Đang giải phóng bộ nhớ của các mô hình Whisper: {models_to_remove}...")
            for k in models_to_remove:
                model_cache[k] = None
                del model_cache[k]
        
        # Giải phóng PhoWhisper
        phowhisper_to_remove = [k for k in phowhisper_pipeline_cache.keys() if k != exclude]
        if phowhisper_to_remove:
            print(f"🧹 Đang giải phóng bộ nhớ của các mô hình PhoWhisper: {phowhisper_to_remove}...")
            for k in phowhisper_to_remove:
                phowhisper_pipeline_cache[k] = None
                del phowhisper_pipeline_cache[k]

        import sys
        if ("torch" in sys.modules) and (models_to_remove or phowhisper_to_remove):
            import gc
            gc.collect()
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print("✅ Đã giải phóng bộ nhớ thành công.")

def load_whisper_model(model_name):
    unload_whisper_models(exclude=model_name)
    with model_lock:
        if model_name not in model_cache:
            import whisper
            dev = get_device()
            print(f"📥 Đang tải mô hình Whisper '{model_name}' trên {dev}...")
            model_cache[model_name] = whisper.load_model(model_name, device=dev)
        return model_cache[model_name]

def transcribe_audio(audio_path, model_name):
    if not audio_path:
        raise ValueError("Không tìm thấy file âm thanh. Vui lòng tải lên hoặc thu âm trực tiếp.")
    try:
        model = load_whisper_model(model_name)
        print(f"🎙️ Bắt đầu nhận diện giọng nói từ file: {audio_path}...")
        result = model.transcribe(audio_path, language="vi")
        transcript = result.get("text", "").strip()
        if not transcript:
            raise ValueError("Không thể chuyển đổi âm thanh thành văn bản (Nội dung trống).")
        return transcript
    except Exception as e:
        raise RuntimeError(f"Lỗi khi chuyển đổi giọng nói (Whisper): {str(e)}")

def load_phowhisper_pipeline(model_name="vinai/PhoWhisper-small"):
    unload_whisper_models(exclude=model_name)
    with model_lock:
        if model_name not in phowhisper_pipeline_cache:
            dev = get_device()
            print(f"📥 Đang tải mô hình PhoWhisper '{model_name}' trên {dev}...")
            from transformers import pipeline
            import torch
            device_id = 0 if torch.cuda.is_available() else -1
            phowhisper_pipeline_cache[model_name] = pipeline(
                "automatic-speech-recognition",
                model=model_name,
                device=device_id
            )
        return phowhisper_pipeline_cache[model_name]

def transcribe_with_phowhisper(audio_path, model_name="vinai/PhoWhisper-small"):
    if not audio_path:
        raise ValueError("Không tìm thấy file âm thanh. Vui lòng tải lên hoặc ghi âm trực tiếp.")
    try:
        pipe = load_phowhisper_pipeline(model_name)
        print(f"🎙️ Bắt đầu nhận diện giọng nói bằng PhoWhisper ({model_name}) từ file: {audio_path}...")
        result = pipe(audio_path, chunk_length_s=30)
        transcript = result.get("text", "").strip()
        if not transcript:
            raise ValueError("Không thể chuyển đổi âm thanh thành văn bản qua PhoWhisper (Nội dung trống).")
        return transcript
    except Exception as e:
        raise RuntimeError(f"Lỗi khi nhận diện giọng nói (PhoWhisper): {str(e)}")

def transcribe_with_gemini_cloud(media_path, api_key, gemini_model="gemini-2.5-flash"):
    if not api_key or not api_key.strip():
        raise ValueError("Vui lòng nhập Google Gemini API Key trên giao diện để sử dụng Cloud transcription.")
    if not media_path:
        raise ValueError("Không tìm thấy file âm thanh. Vui lòng tải lên hoặc thu âm trực tiếp.")

    try:
        client = genai.Client(api_key=api_key.strip())
        import shutil
        ext = os.path.splitext(media_path)[1]
        safe_temp_path = os.path.join(os.getcwd(), f"safe_temp_upload{ext}")
        print(f"🔄 Đang tạo bản sao tạm thời không dấu tại: {safe_temp_path}")
        shutil.copy(media_path, safe_temp_path)
        
        try:
            print(f"📤 Đang upload file âm thanh lên Gemini API...")
            audio_file = client.files.upload(file=safe_temp_path)
        finally:
            if os.path.exists(safe_temp_path):
                os.remove(safe_temp_path)
        
        print("⏳ Đang chờ Gemini xử lý file âm thanh...")
        start_time = time.time()
        while audio_file.state.name == "PROCESSING":
            time.sleep(1)
            audio_file = client.files.get(name=audio_file.name)
            if time.time() - start_time > 60:
                raise TimeoutError("Quá thời gian chờ Gemini xử lý file âm thanh.")
            
        if audio_file.state.name == "FAILED":
            raise RuntimeError("Gemini API xử lý file âm thanh thất bại.")
            
        print("🤖 Đang gửi yêu cầu nhận diện giọng nói qua Gemini Cloud...")
        prompt = "Hãy nghe file âm thanh đính kèm và ký âm (transcribe) toàn bộ câu trả lời của sinh viên thành văn bản tiếng Việt chính xác nhất (speech-to-text). Chỉ trả về phần văn bản đã ký âm được, giữ nguyên các ngắt nghỉ tự nhiên, không thêm giải thích hay lời bàn luận nào khác."
        
        response = client.models.generate_content(
            model=gemini_model,
            contents=[audio_file, prompt]
        )
        
        transcript = response.text.strip()
        
        try:
            print("🧹 Đang dọn dẹp file trên Gemini Cloud...")
            client.files.delete(name=audio_file.name)
        except Exception as de:
            print(f"⚠️ Cảnh báo: Không thể xóa file trên cloud: {str(de)}")
            
        return transcript
    except Exception as e:
        raise RuntimeError(f"Lỗi khi nhận diện qua Gemini Cloud: {str(e)}")

def transcribe_with_groq(media_path, api_key):
    if not api_key or not api_key.strip():
        raise ValueError("Vui lòng nhập Groq API Key trên giao diện để sử dụng Groq Cloud STT.")
    if not media_path:
        raise ValueError("Không tìm thấy file âm thanh. Vui lòng tải lên hoặc ghi âm trực tiếp.")

    try:
        client = Groq(api_key=api_key.strip())
        safe_filename = "audio_input" + os.path.splitext(media_path)[1]
        print(f"🎙️ Bắt đầu nhận diện giọng nói qua Groq API (whisper-large-v3) từ: {safe_filename}...")
        
        with open(media_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(safe_filename, file.read()),
                model="whisper-large-v3",
                temperature=0,
                response_format="verbose_json",
            )
        transcript = transcription.text.strip()
        if not transcript:
            raise ValueError("Không thể chuyển đổi âm thanh thành văn bản qua Groq (Nội dung trống).")
        return transcript
    except Exception as e:
        raise RuntimeError(f"Lỗi khi nhận diện qua Groq API: {str(e)}")

def call_ollama_api(model, prompt, is_json=False, timeout=180):
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    if is_json:
        payload["format"] = "json"
    
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        result = response.json()
        return result.get("response", "").strip()
    except Exception as e:
        raise RuntimeError(
            f"Không thể kết nối đến Ollama local. Vui lòng đảm bảo ứng dụng Ollama đã được khởi động và mô hình '{model}' đã được tải bằng lệnh 'ollama run {model}'. Chi tiết lỗi: {str(e)}"
        )

def correct_transcript_with_gemini(transcript, question, rubric, api_key, gemini_model="gemini-2.5-flash"):
    is_local = gemini_model == "gemma3:4b (Local - Ollama)"
    if not is_local and (not api_key or not api_key.strip()):
        print("⚠️ Cảnh báo: Chưa cấu hình Gemini API Key, bỏ qua bước tự sửa lỗi chính tả.")
        return transcript
        
    try:
        prompt = f"""
Bạn là một trợ lý hiệu đính và hiệu chỉnh chính tả chuyên nghiệp tiếng Việt trong lĩnh vực Công nghệ thông tin.
Nhiệm vụ của bạn là sửa lỗi chính tả, lỗi dấu câu, viết hoa đúng tên riêng, và đặc biệt là sửa các lỗi nghe nhầm (các từ phát âm tương tự nhưng viết sai hoặc sai nghĩa ngữ cảnh) từ văn bản nhận diện giọng nói (Speech-to-Text).

Ngữ cảnh của đề thi vấn đáp:
- Câu hỏi đề thi: "{question}"
- Tiêu chí chấm điểm (Rubric): "{rubric}"

Văn bản ký âm thô thu được từ STT cần sửa lỗi:
"{transcript}"

Yêu cầu sửa đổi chi tiết:
1. Dựa vào ngữ cảnh câu hỏi và rubric ở trên để suy đoán chính xác các thuật ngữ chuyên ngành công nghệ thông tin mà sinh viên đã trả lời (ví dụ: nếu đề bài nói về OOP, hãy sửa 'lắp' thành 'lớp', 'úp' hoặc 'ô ô bê' thành 'OOP', 'phân thức' hoặc 'phân phương thức' thành 'phương thức', 'dưới liệu' thành 'dữ liệu', 'chư tượng' thành 'trừu tượng', v.v.).
2. Sửa lỗi chính tả tiếng Việt thông thường một cách chuẩn xác.
3. Đảm bảo câu văn trôi chảy, giữ nguyên 100% ý chính và câu từ gốc của sinh viên (không viết lại câu trả lời theo cách tốt hơn, không tự ý thêm ý mới, không tóm tắt lại). Chỉ sửa đúng lỗi nghe sai/chính tả/dấu câu.
4. BẮT BUỘC CHỈ TRẢ VỀ đoạn văn bản đã được sửa lỗi chính tả hoàn thiện. Không bao gồm lời chào, lời dẫn dắt, hay bất kỳ văn bản giải thích nào khác.
"""
        if is_local:
            print("🤖 Đang chạy Gemma 3 Local sửa lỗi chính tả theo ngữ cảnh đề bài...")
            corrected_text = call_ollama_api("gemma3:4b", prompt, is_json=False)
        else:
            client = genai.Client(api_key=api_key.strip())
            print("🤖 Đang chạy Gemini AI sửa lỗi chính tả theo ngữ cảnh đề bài...")
            response = client.models.generate_content(
                model=gemini_model,
                contents=prompt
            )
            corrected_text = response.text.strip()
            
        print(f"DEBUG raw transcript: {transcript}")
        print(f"DEBUG corrected transcript: {corrected_text}")
        return corrected_text
    except Exception as e:
        print(f"⚠️ Cảnh báo: Lỗi khi chạy sửa lỗi chính tả: {str(e)}. Sử dụng transcript gốc.")
        return transcript

def grade_with_gemini(question, rubric, transcript, api_key, gemini_model="gemini-2.5-flash", rag_context=""):
    is_local = "Local - Ollama" in gemini_model
    ollama_model_name = gemini_model.split()[0] if is_local else "gemma3:4b"
    
    if not is_local and (not api_key or not api_key.strip()):
        raise ValueError("Vui lòng nhập Google Gemini API Key trên giao diện.")
    if not question or not question.strip():
        raise ValueError("Vui lòng điền nội dung Câu hỏi.")
    if not rubric or not rubric.strip():
        raise ValueError("Vui lòng điền nội dung Tiêu chí chấm điểm (Rubric).")
    if not transcript or not transcript.strip():
        raise ValueError("Nội dung bài làm của sinh viên trống, không thể chấm điểm.")

    try:
        rag_section = ""
        if rag_context and rag_context.strip():
            rag_section = f"""
DƯỚI ĐÂY LÀ KIẾN THỨC CHUẨN ĐƯỢC TRÍCH XUẤT TỪ TÀI LIỆU/GIÁO TRÌNH MÔN HỌC (RAG CONTEXT):
======================================================================
{rag_context}
======================================================================
Hãy đối chiếu kỹ lưỡng bài trả lời của sinh viên với tài liệu chuẩn ở trên để đánh giá độ chính xác về mặt học thuật và các thuật ngữ chuyên ngành.
"""

        prompt = f"""
Bạn là giảng viên đại học chuyên ngành Công nghệ thông tin. Đánh giá câu trả lời vấn đáp của sinh viên theo thang điểm 10 dựa trên rubric và tài liệu môn học.

Câu hỏi:
{question}

Tiêu chí chấm điểm (Rubric):
{rubric}
{rag_section}
Văn bản câu trả lời của sinh viên (được ghi âm và chuyển thành văn bản):
{transcript}

Yêu cầu:
- Cho điểm trên thang 10 (chấp nhận điểm lẻ như 7.5, 8.5).
- Nhận xét chi tiết về tính logic, độ chính xác kiến thức và cách diễn đạt (đặc biệt đối chiếu với nội dung kiến thức chuẩn nếu có).
- Chỉ ra 3 điểm mạnh cụ thể.
- Chỉ ra 3 điểm yếu hoặc điểm thiếu sót cụ thể so với giáo trình/tài liệu chuẩn.
- Đề xuất 2–3 gợi ý cải thiện để sinh viên đạt điểm tốt hơn.

BẮT BUỘC TRẢ VỀ DUY NHẤT 1 ĐỐI TƯỢNG JSON (không kèm bất kỳ lời dẫn nào) theo đúng định dạng sau:
{{
  "score": 8.0,
  "summary": "nhận xét chung chi tiết ở đây",
  "strengths": ["điểm mạnh 1", "điểm mạnh 2", "điểm mạnh 3"],
  "weaknesses": ["điểm yếu 1", "điểm yếu 2", "điểm yếu 3"],
  "improvement": ["gợi ý 1", "gợi ý 2", "gợi ý 3"]
}}
"""
        if is_local:
            print(f"🤖 Đang gửi yêu cầu chấm điểm lên Local Model ({ollama_model_name} qua Ollama)...")
            result_text = call_ollama_api(ollama_model_name, prompt, is_json=False)
        else:
            client = genai.Client(api_key=api_key.strip())
            print("🤖 Đang gửi yêu cầu chấm điểm lên Gemini API...")
            response = client.models.generate_content(
                model=gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=evaluation_schema,
                )
            )
            result_text = response.text.strip()
            
        print(f"DEBUG result_text: {result_text}")
        
        # Bóc tách chuỗi JSON an toàn từ phản hồi của mô hình
        import re
        json_match = re.search(r'(\{[\s\S]*\})', result_text)
        if json_match:
            result_text = json_match.group(1)
        else:
            result_text = result_text.replace("```json", "").replace("```", "").strip()
        
        # Chuẩn hóa các dấu ngoặc kép thông minh từ mô hình SLM cục bộ
        result_text = result_text.replace('“', '"').replace('”', '"').replace('’', "'").replace('‘', "'")
                
        data = json.loads(result_text)
        print(f"DEBUG parsed data: {data}")
        return data
    except json.JSONDecodeError as je:
        raise RuntimeError(f"Lỗi định dạng JSON phản hồi từ mô hình AI. Vui lòng thử lại. Chi tiết: {str(je)}")
    except Exception as e:
        err_msg = str(e)
        if not is_local and ("429" in err_msg or "quota" in err_msg.lower() or "limit" in err_msg.lower() or "exhausted" in err_msg.lower()):
            raise RuntimeError(
                "Bạn đã vượt quá giới hạn lượt gọi API (Quota/Rate Limit) hoặc hết hạn mức tín dụng tài khoản Gemini.\n"
                "• Gói Miễn phí (Free Tier) có giới hạn: gemini-2.5-flash là 15 yêu cầu/phút; gemini-2.5-pro là 2 yêu cầu/phút.\n"
                "• Vui lòng đợi 1 phút rồi thử lại, hoặc kiểm tra trạng thái thanh toán/hạn mức trong Google AI Studio."
            )
        raise RuntimeError(f"Lỗi kết nối mô hình AI: {err_msg}")

def load_questions_from_file(file_path="BỘ ĐỀ THI.txt"):
    if not os.path.exists(file_path):
        print(f"⚠️ Cảnh báo: Không tìm thấy file {file_path}")
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        parts = content.split("---")
        presets = {}
        for part in parts:
            if "CÂU HỎI" not in part:
                continue
            
            title_line = ""
            for line in part.split("\n"):
                if "## 📑 CÂU HỎI" in line:
                    title_line = line.replace("## 📑", "").strip()
                    break
            
            q_start = part.find("> \"")
            q_end = part.find("\"", q_start + 3)
            question = ""
            if q_start != -1 and q_end != -1:
                question = part[q_start + 3:q_end].strip()
            
            r_marker = "### 📋 Rubric chấm điểm chi tiết (Thang điểm 10)"
            r_start = part.find(r_marker)
            rubric = ""
            if r_start != -1:
                rubric = part[r_start + len(r_marker):].strip()
            
            if title_line and question and rubric:
                presets[title_line] = {
                    "question": question,
                    "rubric": rubric
                }
        return presets
    except Exception as e:
        print(f"⚠️ Lỗi khi đọc file câu hỏi mẫu: {str(e)}")
        return {}
