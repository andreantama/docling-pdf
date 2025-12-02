# PDF Extraction API with Worker System

Sistem ekstraksi PDF menggunakan Docling dengan arsitektur worker untuk processing yang scalable dan reliable.

## 🎯 Fitur Utama

- **Worker System**: Multiple workers untuk processing paralel
- **Queue-based Processing**: PDF jobs diproses melalui Redis queue
- **Scalable**: Dapat menambah/mengurangi jumlah worker sesuai kebutuhan
- **Background Processing**: API langsung return response, processing di background
- **Progress Tracking**: Real-time monitoring progress ekstraksi
- **Rich Monitoring**: Statistics worker dan queue information

## 🏗 Arsitektur

```
Client → API Upload → Redis Queue → Workers → PDF Extraction → Results Storage
```

## 📁 Struktur Project

```
/home/tama/Project/python/docling-pdf/
├── main.py              # Base API dan Worker Manager dalam satu file
├── worker.py            # Worker classes untuk memproses queue
├── config.py            # Konfigurasi aplikasi (Redis, worker, upload settings)
├── redis_manager.py     # Enhanced dengan queue management
├── pdf_extractor.py     # Enhanced untuk worker mode
├── requirements.txt     # Dependencies Python
├── .env.example         # Template environment variables
├── README.md           # Dokumentasi ini
└── venv/               # Virtual environment (dibuat saat setup)
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

### 3. Setup Environment
```bash
# Copy dan edit konfigurasi
cp .env.example .env
nano .env

# Setup environment variables untuk worker system
```

### 4. Start Redis Server
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

### 5. Start Application (API + Workers)
```bash
# Pastikan virtual environment sudah aktif
python3 main.py
```

Application akan menjalankan:
- FastAPI server di port 8000 (atau sesuai config)
- Worker system dengan jumlah worker sesuai config  
- Redis queue monitoring
- Background processing workers

Server akan berjalan di: http://localhost:8000

**Note:** Untuk keluar dari virtual environment, gunakan command `deactivate`.

## 🔧 Konfigurasi Worker System

Sistem worker dapat dikonfigurasi melalui environment variables di file `.env`:

```bash
# Worker Configuration
WORKER_COUNT=3                    # Jumlah worker (default: 3)
WORKER_POLL_INTERVAL=2.0         # Interval polling queue dalam detik
ENABLE_WORKERS=True              # Enable/disable worker system

# Queue Configuration  
QUEUE_NAME=pdf_extraction_queue  # Nama Redis queue
MAX_QUEUE_SIZE=100              # Maksimal ukuran queue
WORKER_TIMEOUT=300              # Timeout worker dalam detik

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=False

# Upload Configuration
MAX_FILE_SIZE=52428800  # 50MB
```

## 📚 API Endpoints

### Upload & Processing
**POST** `/upload`
- Upload file PDF dan tambahkan ke queue
- Returns: task_id untuk tracking progress

```bash
curl -X POST "http://localhost:8000/upload" \
     -F "file=@sample.pdf"
```

### Monitoring & Status
**GET** `/status/{task_id}` - Cek progress extraction
**GET** `/result/{task_id}` - Ambil hasil extraction
**GET** `/workers` - Statistik workers
**GET** `/queue` - Informasi queue
**GET** `/health` - Health check dengan info worker
**GET** `/tasks` - List semua tasks

### Management
**DELETE** `/task/{task_id}` - Hapus task
**POST** `/queue/clear` - Clear queue (debugging)

## 🎮 Testing

```bash
# Upload PDF
curl -X POST "http://localhost:8000/upload" \
     -F "file=@sample.pdf"

# Cek status
curl "http://localhost:8000/status/{task_id}"

# Ambil hasil
curl "http://localhost:8000/result/{task_id}"

# Cek worker stats
curl "http://localhost:8000/workers"

# Cek queue info
curl "http://localhost:8000/queue"
```

## 📊 Monitoring

### Worker Statistics
- Total processed jobs
- Failed jobs count  
- Success rate per worker
- Current active tasks
- Uptime information

### Queue Information
- Current queue size
- Queue capacity
- Processing rate

### Health Check
- Redis connection status
- Worker system status
- Active workers count

## 🎯 Keunggulan Sistem Worker

1. **Scalability**: Dapat menambah worker sesuai kebutuhan
2. **Reliability**: Jobs tersimpan di Redis, tidak hilang jika restart
3. **Performance**: Processing paralel dengan multiple workers
4. **Monitoring**: Rich monitoring dan statistics
5. **Fault Tolerance**: Worker restart otomatis jika error
6. **Simple Deployment**: Satu file untuk API dan worker system

## 📖 Progress Tracking

Progress ekstraksi disimpan di Redis dengan tahapan:
- 5%: Job added to queue
- 10%: Job picked up by worker
- 25%: Starting PDF extraction
- 40%: PDF preprocessing completed
- 70%: Docling conversion completed
- 85%: Content parsing completed  
- 100%: Extraction completed

## 🔍 Hasil Ekstraksi

API mengekstrak data berikut dari PDF:
- **Full Text**: Seluruh text dalam PDF
- **Pages**: Text per halaman
- **Tables**: Tabel yang ditemukan (jika ada)
- **Images**: Informasi gambar
- **Metadata**: Jumlah halaman, word count, character count

## 📖 Dokumentasi API

Buka browser dan akses: http://localhost:8000/docs untuk Swagger UI documentation.

## 🐛 Troubleshooting

### Worker tidak berjalan
- Cek `ENABLE_WORKERS=True` di config
- Cek koneksi Redis dengan `curl http://localhost:8000/health`
- Cek log worker untuk error

### Queue penuh
- Tingkatkan `MAX_QUEUE_SIZE` di .env
- Tambah `WORKER_COUNT` untuk processing lebih cepat
- Monitor processing rate dengan `/queue` endpoint

### Redis Connection Error
- Pastikan Redis server berjalan: `redis-cli ping`
- Cek konfigurasi Redis di `.env`
- Cek network connectivity

### PDF Upload Error
- Pastikan file adalah PDF valid
- Cek ukuran file tidak melebihi MAX_FILE_SIZE
- Pastikan file tidak corrupt

### Docling Processing Issues
Jika Docling menampilkan error "could not find page-dimensions", aplikasi akan tetap mencoba menyelesaikan ekstraksi menggunakan fallback PyMuPDF.

```bash
# Jika ada masalah dengan dependencies
pip install --upgrade docling
pip install --upgrade PyMuPDF
pip install --upgrade pypdfium2
```

### Installation Issues
```bash
# Jika ada konflik dependencies saat install
pip install --use-deprecated=legacy-resolver -r requirements.txt
```

## 🔧 Development

Untuk development mode dengan virtual environment:
```bash
# Aktifkan virtual environment terlebih dahulu
source venv/bin/activate  # Linux/macOS
# atau: venv\Scripts\activate  # Windows

# Set DEBUG mode dan jalankan
export DEBUG=True
python3 main.py
```

Mode debug mengaktifkan auto-reload saat file berubah.

## 🚀 Production Deployment

### Traditional Deployment
```bash
# Setup production environment
cp .env.example .env
# Edit .env untuk production settings

# Set production values
export DEBUG=False
export WORKER_COUNT=5           # Sesuaikan dengan CPU cores
export MAX_QUEUE_SIZE=200       # Sesuaikan dengan traffic
export WORKER_POLL_INTERVAL=1.0 # Faster polling untuk production

# Start with process manager (contoh: systemd, supervisor, PM2)
python3 main.py
```

### Docker Deployment 🐳
```bash
# Quick start dengan Docker Compose
docker-compose up --build -d

# API akan tersedia di: http://localhost:3111
# Health check: curl http://localhost:3111/health

# View logs
docker-compose logs -f pdf-extraction-api

# Stop services
docker-compose down
```

Untuk dokumentasi lengkap Docker deployment, lihat [DOCKER.md](DOCKER.md).

Untuk production deployment, pertimbangkan menggunakan:
- **Process Manager**: systemd, supervisor, atau PM2
- **Reverse Proxy**: Nginx atau Apache  
- **Load Balancer**: Jika menggunakan multiple instances
- **Container**: Docker untuk deployment yang konsisten