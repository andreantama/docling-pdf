# PDF Extraction API dengan Docling

Project ini adalah API untuk melakukan ekstraksi data dari file PDF menggunakan Docling dengan progress tracking di Redis.

## 📁 Struktur Project

```
/home/tama/Project/python/docling-pdf/
├── main.py              # FastAPI application utama dengan semua endpoints
├── config.py            # Konfigurasi aplikasi (Redis, upload settings, dll)
├── redis_manager.py     # Manager untuk operasi Redis (progress tracking)
├── pdf_extractor.py     # Module ekstraksi PDF menggunakan Docling
├── requirements.txt     # Dependencies Python
└── README.md           # Dokumentasi ini
```

## 🚀 Cara Menjalankan

### 1. Setup Virtual Environment (Recommended)
```bash
cd /home/tama/Project/python/docling-pdf

# Buat virtual environment
python -m venv venv

# Aktifkan virtual environment
# Untuk Linux/macOS:
source venv/bin/activate

# Untuk Windows:
# venv\Scripts\activate
```

### 2. Install Dependencies
```bash
# Pastikan virtual environment sudah aktif (akan terlihat (venv) di prompt)
pip install -r requirements.txt
```

### 3. Setup Redis
Pastikan Redis server berjalan di localhost:6379 (default), atau sesuaikan konfigurasi di `config.py`.

```bash
# Untuk Ubuntu/Debian:
sudo apt install redis-server
sudo systemctl start redis

# Untuk macOS dengan Homebrew:
brew install redis
brew services start redis

# Untuk Windows:
# Download dan install Redis dari official website
```

### 4. Jalankan API Server
```bash
# Pastikan virtual environment sudah aktif
python main.py
```

Server akan berjalan di: http://localhost:8000

**Note:** Untuk keluar dari virtual environment, gunakan command `deactivate`.

## 📚 API Endpoints

### 1. Upload PDF
**POST** `/upload`
- Upload file PDF untuk ekstraksi
- Returns: task_id untuk tracking progress

```bash
curl -X POST "http://localhost:8000/upload" \
     -F "file=@example.pdf"
```

### 2. Check Status
**GET** `/status/{task_id}`
- Cek progress ekstraksi PDF
- Returns: status, progress percentage, dan message

```bash
curl "http://localhost:8000/status/your-task-id"
```

### 3. Get Result
**GET** `/result/{task_id}`
- Ambil hasil ekstraksi PDF (jika sudah selesai)
- Returns: extracted text, tables, images, metadata

```bash
curl "http://localhost:8000/result/your-task-id"
```

### 4. List Tasks
**GET** `/tasks`
- Lihat semua task yang ada

### 5. Health Check
**GET** `/health`
- Cek status kesehatan API dan Redis

### 6. Delete Task
**DELETE** `/task/{task_id}`
- Hapus task dari Redis

## 🛠 Environment Variables

Anda bisa mengatur konfigurasi melalui environment variables:

```bash
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_DB=0
export MAX_FILE_SIZE=52428800  # 50MB
export API_HOST=0.0.0.0
export API_PORT=8000
export DEBUG=False
```

## 📊 Progress Tracking

Progress ekstraksi disimpan di Redis dengan tahapan:
- 10%: Memulai ekstraksi
- 25%: File preparation selesai  
- 40%: Konversi dengan Docling dimulai
- 70%: Konversi selesai, parsing data
- 85%: Parsing selesai
- 90%: Finalisasi
- 100%: Selesai

## 🔍 Hasil Ekstraksi

API mengekstrak data berikut dari PDF:
- **Full Text**: Seluruh text dalam PDF
- **Pages**: Text per halaman
- **Tables**: Tabel yang ditemukan
- **Images**: Informasi gambar
- **Metadata**: Jumlah halaman, word count, dll

## 📖 Dokumentasi API

Buka browser dan akses: http://localhost:8000/docs untuk Swagger UI documentation.

## 🐛 Troubleshooting

### Redis Connection Error
- Pastikan Redis server berjalan
- Cek konfigurasi host/port di `config.py`

### PDF Upload Error
- Pastikan file adalah PDF valid
- Cek ukuran file tidak melebihi 50MB
- Pastikan file tidak corrupt

### Docling Import Error
```bash
pip install --upgrade docling
```

## 🔧 Development

Untuk development mode dengan virtual environment:
```bash
# Aktifkan virtual environment terlebih dahulu
source venv/bin/activate  # Linux/macOS
# atau: venv\Scripts\activate  # Windows

# Set DEBUG mode dan jalankan
export DEBUG=True
python main.py
```

Mode debug mengaktifkan auto-reload saat file berubah.