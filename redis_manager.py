import redis
import json
import uuid
import time
from typing import Dict, Any, Optional, List
from config import Config

class RedisManager:
    """
    Kelas untuk mengelola operasi Redis
    Handle penyimpanan progress dan hasil ekstraksi PDF
    """
    
    def __init__(self):
        """
        Inisialisasi koneksi Redis menggunakan konfigurasi dari Config class
        """
        try:
            # Membuat koneksi ke Redis server untuk text data
            self.redis_client = redis.Redis(
                host=Config.REDIS_HOST,
                port=Config.REDIS_PORT,
                db=Config.REDIS_DB,
                password=Config.REDIS_PASSWORD,
                decode_responses=True  # Otomatis decode bytes ke string untuk JSON data
            )
            
            # Membuat koneksi terpisah untuk binary data (PDF content)
            self.redis_binary = redis.Redis(
                host=Config.REDIS_HOST,
                port=Config.REDIS_PORT,
                db=Config.REDIS_DB,
                password=Config.REDIS_PASSWORD,
                decode_responses=False  # Keep binary data as bytes
            )
            
            # Test koneksi
            self.redis_client.ping()
            print("✅ Connected to Redis successfully")
        except Exception as e:
            print(f"❌ Failed to connect to Redis: {e}")
            raise e
    
    def generate_task_id(self) -> str:
        """
        Generate unique task ID untuk setiap ekstraksi
        Returns: UUID string untuk task ID
        """
        return str(uuid.uuid4())
    
    def create_task(self, filename: str) -> str:
        """
        Membuat task baru di Redis dengan status initial
        Args:
            filename: Nama file PDF yang akan diproses
        Returns:
            task_id: ID unik untuk task
        """
        task_id = self.generate_task_id()
        
        # Data initial untuk task
        task_data = {
            "task_id": task_id,
            "filename": filename,
            "status": "created",  # Status: created -> processing -> completed/failed
            "progress": 0,        # Progress percentage (0-100)
            "message": "Task created, waiting to start",
            "created_at": json.dumps(None),  # Akan diisi saat task dimulai
            "completed_at": None,
            "result": None,       # Hasil ekstraksi akan disimpan di sini
            "error": None         # Error message jika ada
        }
        
        # Simpan task data ke Redis dengan expiry time
        self.redis_client.setex(
            f"task:{task_id}",
            Config.TASK_EXPIRY,
            json.dumps(task_data)
        )
        
        return task_id
    
    def update_task_progress(self, task_id: str, progress: int, message: str, status: str = None):
        """
        Update progress dan status task
        Args:
            task_id: ID task yang akan diupdate
            progress: Progress percentage (0-100)
            message: Pesan status untuk user
            status: Status task (optional, jika ingin mengubah status)
        """
        try:
            # Ambil data task yang sudah ada
            task_data = self.get_task_status(task_id)
            if not task_data:
                raise ValueError(f"Task {task_id} not found")
            
            # Update progress dan message
            task_data["progress"] = progress
            task_data["message"] = message
            
            # Update status jika disediakan
            if status:
                task_data["status"] = status
            
            # Simpan kembali ke Redis
            self.redis_client.setex(
                f"task:{task_id}",
                Config.TASK_EXPIRY,
                json.dumps(task_data)
            )
            
        except Exception as e:
            print(f"Error updating task progress: {e}")
    
    def complete_task(self, task_id: str, result: Dict[str, Any], success: bool = True):
        """
        Menandai task sebagai selesai dan menyimpan hasil
        Args:
            task_id: ID task yang selesai
            result: Hasil ekstraksi PDF
            success: True jika berhasil, False jika gagal
        """
        try:
            # Ambil data task yang sudah ada
            task_data = self.get_task_status(task_id)
            if not task_data:
                raise ValueError(f"Task {task_id} not found")
            
            # Update status dan hasil
            task_data["status"] = "completed" if success else "failed"
            task_data["progress"] = 100
            task_data["completed_at"] = json.dumps(None)  # Timestamp completion
            
            if success:
                task_data["result"] = result
                task_data["message"] = "Extraction completed successfully"
            else:
                task_data["error"] = result.get("error", "Unknown error")
                task_data["message"] = f"Extraction failed: {task_data['error']}"
            
            # Simpan hasil final ke Redis
            self.redis_client.setex(
                f"task:{task_id}",
                Config.TASK_EXPIRY,
                json.dumps(task_data)
            )
            
        except Exception as e:
            print(f"Error completing task: {e}")
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Mengambil status dan data task dari Redis
        Args:
            task_id: ID task yang akan dicek
        Returns:
            Dict dengan data task atau None jika tidak ditemukan
        """
        try:
            # Ambil data dari Redis
            task_data = self.redis_client.get(f"task:{task_id}")
            
            if task_data:
                # Parse JSON data
                return json.loads(task_data)
            else:
                return None
                
        except Exception as e:
            print(f"Error getting task status: {e}")
            return None
    
    def delete_task(self, task_id: str):
        """
        Menghapus task dari Redis
        Args:
            task_id: ID task yang akan dihapus
        """
        try:
            self.redis_client.delete(f"task:{task_id}")
        except Exception as e:
            print(f"Error deleting task: {e}")
    
    def get_all_tasks(self) -> list:
        """
        Mendapatkan semua task yang ada di Redis
        Returns:
            List of task data
        """
        try:
            # Cari semua key yang dimulai dengan "task:"
            task_keys = self.redis_client.keys("task:*")
            tasks = []
            
            for key in task_keys:
                task_data = self.redis_client.get(key)
                if task_data:
                    tasks.append(json.loads(task_data))
            
            return tasks
            
        except Exception as e:
            print(f"Error getting all tasks: {e}")
            return []
    
    # ===== QUEUE MANAGEMENT METHODS =====
    
    def enqueue_pdf_job(self, task_id: str, pdf_content: bytes, filename: str) -> bool:
        """
        Menambahkan job PDF extraction ke queue
        Args:
            task_id: ID task yang sudah dibuat
            pdf_content: Binary content PDF
            filename: Nama file PDF
        Returns:
            True jika berhasil menambahkan ke queue
        """
        try:
            # Cek ukuran queue
            queue_size = self.redis_client.llen(Config.QUEUE_NAME)
            if queue_size >= Config.MAX_QUEUE_SIZE:
                print(f"Queue is full ({queue_size}/{Config.MAX_QUEUE_SIZE})")
                return False
            
            # Simpan PDF content ke Redis dengan key terpisah menggunakan binary connection
            pdf_key = f"pdf_content:{task_id}"
            self.redis_binary.setex(pdf_key, Config.TASK_EXPIRY, pdf_content)
            
            # Buat job data
            job_data = {
                "task_id": task_id,
                "filename": filename,
                "pdf_key": pdf_key,
                "queued_at": time.time()
            }
            
            # Push job ke queue (FIFO - First In First Out)
            self.redis_client.lpush(Config.QUEUE_NAME, json.dumps(job_data))
            
            # Update task status menjadi queued
            self.update_task_progress(
                task_id, 5, "Job added to processing queue", "queued"
            )
            
            print(f"✅ Job {task_id} added to queue. Queue size: {queue_size + 1}")
            return True
            
        except Exception as e:
            print(f"Error enqueuing job: {e}")
            return False
    
    def dequeue_pdf_job(self) -> Optional[Dict[str, Any]]:
        """
        Mengambil job PDF extraction dari queue
        Returns:
            Dict dengan data job atau None jika queue kosong
        """
        try:
            # Ambil job dari queue dengan timeout (blocking pop)
            job_data = self.redis_client.brpop(Config.QUEUE_NAME, timeout=1)
            
            if job_data:
                # Parse job data
                queue_name, job_json = job_data
                job = json.loads(job_json)
                
                # Ambil PDF content dari Redis menggunakan binary connection
                pdf_content = self.redis_binary.get(job["pdf_key"])
                if pdf_content is None:
                    print(f"❌ PDF content not found for task {job['task_id']}")
                    return None
                
                job["pdf_content"] = pdf_content
                
                # Update task status menjadi processing
                self.update_task_progress(
                    job["task_id"], 10, "Job picked up by worker", "processing"
                )
                
                return job
            
            return None
            
        except Exception as e:
            print(f"Error dequeuing job: {e}")
            return None
    
    def get_queue_info(self) -> Dict[str, Any]:
        """
        Mendapatkan informasi tentang status queue
        Returns:
            Dict dengan informasi queue
        """
        try:
            queue_size = self.redis_client.llen(Config.QUEUE_NAME)
            
            return {
                "queue_size": queue_size,
                "max_queue_size": Config.MAX_QUEUE_SIZE,
                "queue_name": Config.QUEUE_NAME,
                "is_full": queue_size >= Config.MAX_QUEUE_SIZE
            }
            
        except Exception as e:
            print(f"Error getting queue info: {e}")
            return {
                "queue_size": 0,
                "max_queue_size": Config.MAX_QUEUE_SIZE,
                "queue_name": Config.QUEUE_NAME,
                "is_full": False,
                "error": str(e)
            }
    
    def cleanup_pdf_content(self, task_id: str):
        """
        Membersihkan PDF content dari Redis setelah processing selesai
        Args:
            task_id: ID task yang akan dibersihkan
        """
        try:
            pdf_key = f"pdf_content:{task_id}"
            self.redis_binary.delete(pdf_key)
        except Exception as e:
            print(f"Error cleaning up PDF content for task {task_id}: {e}")
    
    def clear_queue(self):
        """
        Membersihkan semua job dari queue (untuk debugging/maintenance)
        """
        try:
            cleared_count = self.redis_client.delete(Config.QUEUE_NAME)
            print(f"Cleared {cleared_count} items from queue")
            return cleared_count
        except Exception as e:
            print(f"Error clearing queue: {e}")
            return 0