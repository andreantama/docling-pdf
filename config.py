# Configuration settings untuk aplikasi
import os

class Config:
    """
    Kelas konfigurasi untuk menyimpan semua pengaturan aplikasi
    Menggunakan environment variables dengan fallback ke default values
    """
    
    # Redis Configuration
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')  # Host Redis server
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))    # Port Redis server  
    REDIS_DB = int(os.getenv('REDIS_DB', 0))           # Database Redis yang digunakan
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None) # Password Redis (jika ada)
    
    # Task Configuration
    TASK_EXPIRY = int(os.getenv('TASK_EXPIRY', 3600))  # Berapa lama task disimpan di Redis (detik)
    
    # Upload Configuration
    MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', 50 * 1024 * 1024))  # Max 50MB file size
    ALLOWED_EXTENSIONS = ['.pdf']  # Hanya file PDF yang diperbolehkan
    
    # PDF Processing Configuration
    USE_PYMUPDF_PRIMARY = os.getenv('USE_PYMUPDF_PRIMARY', 'False').lower() == 'true'  # Use PyMuPDF as primary extractor
    IGNORE_PAGE_DIMENSION_WARNINGS = os.getenv('IGNORE_PAGE_DIMENSION_WARNINGS', 'True').lower() == 'true'  # Suppress page-dimensions warnings
    
    # App Configuration
    API_HOST = os.getenv('API_HOST', '0.0.0.0')     # Host untuk API server
    API_PORT = int(os.getenv('API_PORT', 8000))     # Port untuk API server
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'  # Mode debug
    
    # Worker Configuration
    WORKER_COUNT = int(os.getenv('WORKER_COUNT', 3))  # Jumlah worker yang akan berjalan
    WORKER_POLL_INTERVAL = float(os.getenv('WORKER_POLL_INTERVAL', 2.0))  # Interval polling queue dalam detik
    ENABLE_WORKERS = os.getenv('ENABLE_WORKERS', 'True').lower() == 'true'  # Enable/disable worker system
    
    # Queue Configuration
    QUEUE_NAME = os.getenv('QUEUE_NAME', 'pdf_extraction_queue')  # Nama queue Redis
    MAX_QUEUE_SIZE = int(os.getenv('MAX_QUEUE_SIZE', 100))  # Maksimal ukuran queue
    WORKER_TIMEOUT = int(os.getenv('WORKER_TIMEOUT', 300))  # Timeout untuk worker dalam detik