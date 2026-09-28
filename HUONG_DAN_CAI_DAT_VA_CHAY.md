# 🚀 Hướng Dẫn Clone & Chạy Dự Án QNU AI VIVA

Tài liệu này hướng dẫn chi tiết từng bước để clone mã nguồn từ GitHub về máy tính mới, cài đặt môi trường và khởi chạy ứng dụng **QNU AI VIVA** (Hệ thống trợ lý ký âm & chấm điểm thi vấn đáp thông minh).

---

## 📋 1. Yêu Cầu Tiền Đề (Prerequisites)

Trước khi bắt đầu, hãy đảm bảo máy tính đã cài đặt:
1. **Git**: Tải tại [git-scm.com](https://git-scm.com/) (nếu chưa có).
2. **Python**: Phiên bản khuyến nghị từ **Python 3.10 đến 3.12**.
3. **FFmpeg** *(Tùy chọn nhưng khuyến nghị)*: Cần thiết để xử lý audio nếu bạn dùng các mô hình Whisper local.
   - Windows: Có thể cài qua `winget install Gyan.FFmpeg` hoặc `choco install ffmpeg`.
   - Ubuntu/Debian: `sudo apt install ffmpeg`.
   - macOS: `brew install ffmpeg`.
4. **Ollama** *(Tùy chọn)*: Nếu muốn chạy mô hình chấm điểm offline `gemma3:4b` không cần mạng internet ([ollama.com](https://ollama.com/)).

---

## 📥 2. Clone Dự Án Về Máy Cục Bộ

Mở Terminal (PowerShell trên Windows hoặc bash trên Linux/macOS) và thực hiện lệnh:

```bash
# Clone repository về máy
git clone https://github.com/luannguyenn889/speed-to-text-demo.git

# Di chuyển vào thư mục dự án
cd speed-to-text-demo
```

---

## 🐍 3. Tạo Môi Trường Ảo (Virtual Environment)

Khuyến nghị luôn tạo môi trường ảo riêng biệt để tránh xung đột thư viện:

### Trên Windows (PowerShell):
```powershell
# Tạo môi trường ảo có tên .venv
python -m venv .venv

# Kích hoạt môi trường ảo
.\.venv\Scripts\Activate.ps1
```
> *Lưu ý nếu PowerShell báo lỗi `Execution_Policies`: chạy lệnh `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` rồi chạy lại lệnh activate.*

### Trên Windows (Command Prompt - cmd):
```cmd
python -m venv .venv
.\.venv\Scripts\activate.bat
```

### Trên macOS / Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## 📦 4. Cài Đặt Các Thư Viện Phụ Thuộc

Khi môi trường ảo đang được kích hoạt (có tiền tố `(.venv)` ở đầu dòng lệnh), chạy lệnh:

```bash
# Nâng cấp pip lên bản mới nhất
python -m pip install --upgrade pip

# Cài đặt toàn bộ dependencies từ requirements.txt
pip install -r requirements.txt
```

---

## 🔑 5. Cấu Hình Khóa API (API Keys)

Dự án hỗ trợ chuyển giọng nói sang văn bản và chấm điểm AI thông qua Google Gemini và Groq. Hãy tạo file cấu hình môi trường:

1. **Tạo file `.env` từ file mẫu `.env.example`**:
   - **Windows PowerShell**:
     ```powershell
     Copy-Item .env.example .env
     ```
   - **Linux / macOS**:
     ```bash
     cp .env.example .env
     ```

2. **Mở file `.env` và điền API Key của bạn**:
   ```env
   # Lấy miễn phí tại: https://aistudio.google.com/
   GEMINI_API_KEY=AIzaSy...your_gemini_api_key

   # Lấy miễn phí tại: https://console.groq.com/
   GROQ_API_KEY=gsk_...your_groq_api_key
   ```
> *Lưu ý: File `.env` đã được đưa vào `.gitignore` để bảo vệ an toàn, không bao giờ bị đẩy lên GitHub.*

---

## ▶️ 6. Khởi Chạy Ứng Dụng (Giao Diện Web Gradio)

Chạy lệnh sau tại thư mục gốc của dự án:

```bash
python app.py
```

Khi ứng dụng khởi động thành công, terminal sẽ hiển thị thông báo tương tự:
```text
Running on local URL:  http://127.0.0.1:7860
```

👉 Mở trình duyệt web và truy cập: **[http://127.0.0.1:7860](http://127.0.0.1:7860)**

---

## 🧪 7. Kiểm Tra Hoạt Động & Chạy Thử Nghiệm (Optional)

### Kiểm tra kết nối Gemini API:
```bash
python test_key.py
```
Nếu cấu hình đúng, danh sách các mô hình Gemini hỗ trợ sẽ được in ra.

### Chạy Benchmark so sánh nhiều mô hình (Xuất báo cáo Excel):
```bash
python test_models_excel.py --audio audio/caubademo.mp4 --question_idx 1
```
Kết quả so sánh chi tiết giữa các bộ ký âm (Whisper, PhoWhisper, Groq, Gemini) và các mô hình chấm điểm sẽ được lưu trong thư mục `exports/`.

---

## ❓ 8. Các Sự Cố Thường Gặp & Cách Khắc Phục (Troubleshooting)

| Lỗi / Hiện tượng | Nguyên nhân | Cách khắc phục |
| :--- | :--- | :--- |
| `ModuleNotFoundError: No module named '...'` | Chưa kích hoạt môi trường ảo `.venv` hoặc chưa cài `requirements.txt` | Chạy lại bước kích hoạt `.venv` và `pip install -r requirements.txt`. |
| Lỗi khi dùng Whisper local: `FileNotFoundError: [WinError 2] The system cannot find the file specified` | Thiếu công cụ FFmpeg trong hệ điều hành | Cài đặt `ffmpeg` và thêm vào biến môi trường PATH của hệ thống. |
| Báo lỗi `Port 7860 is in use` | Một tiến trình trước đó vẫn đang chiếm cổng `7860` | Đóng terminal cũ hoặc chạy lại lệnh tắt tiến trình Python đang chạy ngầm. |
| Báo lỗi `API_KEY not valid` hoặc hết hạn | Key Gemini / Groq chưa đúng | Kiểm tra lại chuỗi key trong file `.env` hoặc tạo mới trên AI Studio / Groq Console. |
