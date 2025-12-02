import asyncio
import threading
import time
import sys
from typing import Dict, Any
from config import Config
from redis_manager import RedisManager
from pdf_extractor import PDFExtractor

class PDFWorker:
    """
    Worker class untuk memproses antrian PDF extraction dari Redis
    """
    
    def __init__(self, worker_id: int):
        """
        Inisialisasi worker dengan ID unik
        Args:
            worker_id: ID unik untuk worker (0, 1, 2, dst)
        """
        self.worker_id = worker_id
        self.is_running = False
        self.redis_manager = RedisManager()
        self.pdf_extractor = PDFExtractor(self.redis_manager)
        self.current_task = None
        self.processed_count = 0
        self.failed_count = 0
        self.start_time = time.time()
        
        print(f"🔧 Worker #{self.worker_id} initialized")
    
    async def start(self):
        """
        Memulai worker untuk memproses antrian
        """
        self.is_running = True
        print(f"🚀 Worker #{self.worker_id} started")
        
        while self.is_running:
            try:
                # Ambil job dari queue
                job = self.redis_manager.dequeue_pdf_job()
                
                if job:
                    await self._process_job(job)
                else:
                    # Tidak ada job, tunggu sebentar
                    await asyncio.sleep(Config.WORKER_POLL_INTERVAL)
                    
            except KeyboardInterrupt:
                print(f"🛑 Worker #{self.worker_id} received interrupt signal")
                break
            except Exception as e:
                print(f"❌ Worker #{self.worker_id} error: {e}")
                await asyncio.sleep(Config.WORKER_POLL_INTERVAL)
        
        print(f"🏁 Worker #{self.worker_id} stopped")
    
    async def _process_job(self, job: Dict[str, Any]):
        """
        Memproses satu job PDF extraction
        Args:
            job: Data job dari queue
        """
        task_id = job["task_id"]
        filename = job["filename"]
        
        try:
            self.current_task = task_id
            print(f"📄 Worker #{self.worker_id} processing: {filename} (Task: {task_id})")
            
            start_time = time.time()
            
            # Proses PDF extraction menggunakan PDFExtractor
            result = await self.pdf_extractor.extract_pdf_worker(job)
            
            processing_time = time.time() - start_time
            
            if result.get("extraction_successful", False):
                self.processed_count += 1
                print(f"✅ Worker #{self.worker_id} completed: {filename} in {processing_time:.2f}s")
            else:
                self.failed_count += 1
                print(f"❌ Worker #{self.worker_id} failed: {filename} - {result.get('error', 'Unknown error')}")
            
            self.current_task = None
            
        except Exception as e:
            self.failed_count += 1
            print(f"❌ Worker #{self.worker_id} exception processing {filename}: {e}")
            
            # Mark task as failed jika belum di-handle
            try:
                self.redis_manager.complete_task(
                    task_id,
                    {"error": str(e), "extraction_successful": False},
                    success=False
                )
                self.redis_manager.cleanup_pdf_content(task_id)
            except:
                pass
            
            self.current_task = None
    
    def stop(self):
        """
        Menghentikan worker
        """
        print(f"🛑 Stopping worker #{self.worker_id}...")
        self.is_running = False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Mendapatkan statistik worker
        """
        uptime = time.time() - self.start_time
        return {
            "worker_id": self.worker_id,
            "is_running": self.is_running,
            "current_task": self.current_task,
            "processed_count": self.processed_count,
            "failed_count": self.failed_count,
            "success_rate": self.processed_count / max(1, self.processed_count + self.failed_count) * 100,
            "uptime_seconds": uptime,
            "uptime_formatted": f"{int(uptime//3600)}h {int((uptime%3600)//60)}m {int(uptime%60)}s"
        }


class WorkerManager:
    """
    Manager untuk mengelola multiple workers
    """
    
    def __init__(self):
        """
        Inisialisasi worker manager
        """
        self.workers = []
        self.worker_threads = []
        self.is_running = False
        self.redis_manager = RedisManager()
        
        print(f"🎛️ Worker Manager initialized for {Config.WORKER_COUNT} workers")
    
    async def start_workers(self):
        """
        Memulai semua workers
        """
        if not Config.ENABLE_WORKERS:
            print("⚠️ Workers disabled in configuration")
            return
        
        self.is_running = True
        print(f"🚀 Starting {Config.WORKER_COUNT} workers...")
        
        # Buat dan start workers
        for worker_id in range(Config.WORKER_COUNT):
            worker = PDFWorker(worker_id)
            self.workers.append(worker)
            
            # Jalankan setiap worker dalam thread terpisah
            thread = threading.Thread(
                target=self._run_worker,
                args=(worker,),
                daemon=True
            )
            thread.start()
            self.worker_threads.append(thread)
        
        print(f"✅ All {Config.WORKER_COUNT} workers started")
        
        # Keep main thread alive dan monitor workers
        try:
            while self.is_running:
                await asyncio.sleep(10)  # Check every 10 seconds
                await self._monitor_workers()
        except KeyboardInterrupt:
            print("🛑 Received interrupt signal")
        
        await self.stop_workers()
    
    def _run_worker(self, worker: PDFWorker):
        """
        Menjalankan worker dalam thread
        Args:
            worker: Instance PDFWorker
        """
        try:
            # Buat event loop baru untuk thread ini
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Jalankan worker
            loop.run_until_complete(worker.start())
        except Exception as e:
            print(f"❌ Thread error for worker #{worker.worker_id}: {e}")
        finally:
            try:
                loop.close()
            except:
                pass
    
    async def _monitor_workers(self):
        """
        Monitor status workers dan queue
        """
        if not self.is_running:
            return
        
        try:
            # Get queue info
            queue_info = self.redis_manager.get_queue_info()
            
            # Get worker stats
            active_workers = sum(1 for w in self.workers if w.is_running)
            total_processed = sum(w.processed_count for w in self.workers)
            total_failed = sum(w.failed_count for w in self.workers)
            
            print(f"📊 Queue: {queue_info['queue_size']} jobs | "
                  f"Workers: {active_workers}/{len(self.workers)} active | "
                  f"Processed: {total_processed} | Failed: {total_failed}")
            
        except Exception as e:
            print(f"❌ Monitor error: {e}")
    
    async def stop_workers(self):
        """
        Menghentikan semua workers
        """
        print("🛑 Stopping all workers...")
        self.is_running = False
        
        # Stop semua workers
        for worker in self.workers:
            worker.stop()
        
        # Tunggu semua thread selesai (dengan timeout)
        for thread in self.worker_threads:
            thread.join(timeout=5)
        
        print("🏁 All workers stopped")
    
    def get_all_stats(self) -> Dict[str, Any]:
        """
        Mendapatkan statistik semua workers
        """
        worker_stats = [worker.get_stats() for worker in self.workers]
        queue_info = self.redis_manager.get_queue_info()
        
        total_processed = sum(w.processed_count for w in self.workers)
        total_failed = sum(w.failed_count for w in self.workers)
        
        return {
            "worker_manager": {
                "is_running": self.is_running,
                "total_workers": len(self.workers),
                "active_workers": sum(1 for w in self.workers if w.is_running),
                "total_processed": total_processed,
                "total_failed": total_failed,
                "overall_success_rate": total_processed / max(1, total_processed + total_failed) * 100
            },
            "queue_info": queue_info,
            "workers": worker_stats
        }