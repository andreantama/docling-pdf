# PDF Extraction API with Worker System

Sistem ekstraksi PDF menggunakan Docling dengan arsitektur worker untuk processing yang scalable.

## Perubahan Utama

### 1. Sistem Worker
- **Worker System**: Multiple workers yang dapat diatur jumlahnya melalui konfigurasi
- **Queue-based Processing**: PDF jobs diproses melalui Redis queue system
- **Scalable**: Dapat menambah/mengurangi jumlah worker sesuai kebutuhan
- **Background Processing**: API langsung return response, processing dilakukan di background

### 2. Arsitektur Baru

```
Client → API Upload → Redis Queue → Workers → PDF Extraction → Results Storage
```

#### Files Structure:
- `main.py` - Base API dan Worker Manager dalam satu file
- `worker.py` - Worker classes untuk memproses queue
- `redis_manager.py` - Enhanced dengan queue management
- `pdf_extractor.py` - Enhanced untuk worker mode
- `config.py` - Tambahan konfigurasi worker
- `.env.example` - Template konfigurasi

### 3. Endpoint Baru

#### API Endpoints:
- `POST /upload` - Upload PDF (langsung return, masuk ke queue)
- `GET /status/{task_id}` - Cek progress extraction
- `GET /result/{task_id}` - Ambil hasil extraction
- `GET /workers` - Statistik workers
- `GET /queue` - Informasi queue
- `POST /queue/clear` - Clear queue (debugging)
- `GET /health` - Health check dengan info worker
- `GET /tasks` - List semua tasks
- `DELETE /task/{task_id}` - Hapus task

### 4. Konfigurasi Worker (.env)

```bash
# Worker Configuration
WORKER_COUNT=3                    # Jumlah worker
WORKER_POLL_INTERVAL=2.0         # Interval polling queue (detik)
ENABLE_WORKERS=True              # Enable/disable worker system

# Queue Configuration  
QUEUE_NAME=pdf_extraction_queue  # Nama Redis queue
MAX_QUEUE_SIZE=100              # Maksimal ukuran queue
WORKER_TIMEOUT=300              # Timeout worker (detik)
```

## Cara Menjalankan

### 1. Setup Environment
```bash
# Copy dan edit konfigurasi
cp .env.example .env
nano .env

# Install dependencies
pip install -r requirements.txt
```

### 2. Start Redis Server
```bash
redis-server
```

### 3. Start Application (API + Workers)
```bash
python3 main.py
```

Application akan menjalankan:
- FastAPI server di port 8000 (atau sesuai config)
- Worker system dengan jumlah worker sesuai config
- Redis queue monitoring

### 4. Testing

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

## Monitoring

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

## Keunggulan Sistem Baru

1. **Scalability**: Dapat menambah worker sesuai kebutuhan
2. **Reliability**: Jobs tersimpan di Redis, tidak hilang jika restart
3. **Performance**: Processing paralel dengan multiple workers
4. **Monitoring**: Rich monitoring dan statistics
5. **Fault Tolerance**: Worker restart otomatis jika error
6. **Simple Deployment**: Satu file untuk API dan worker system

## Troubleshooting

### Worker tidak berjalan
- Cek `ENABLE_WORKERS=True` di config
- Cek koneksi Redis
- Cek log worker untuk error

### Queue penuh
- Tingkatkan `MAX_QUEUE_SIZE`
- Tambah `WORKER_COUNT`
- Monitor processing rate

### Redis connection error
- Pastikan Redis server running
- Cek konfigurasi Redis di `.env`
- Cek network connectivity