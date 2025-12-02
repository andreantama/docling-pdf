from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import asyncio
import threading
from typing import Dict, Any
import os
import signal

# Import custom modules
from config import Config
from redis_manager import RedisManager
from pdf_extractor import PDFExtractor
from worker import WorkerManager

# Global instances
redis_manager = None
worker_manager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan event handler"""
    global redis_manager, worker_manager
    
    try:
        print("🚀 Starting PDF Extraction API with Worker System...")
        
        # Inisialisasi Redis manager
        redis_manager = RedisManager()
        print("✅ Redis Manager initialized")
        
        # Setup signal handlers untuk graceful shutdown (hanya di main thread)
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Inisialisasi dan start worker system
        if Config.ENABLE_WORKERS:
            worker_manager = WorkerManager()
            # Start workers dalam background task asyncio (bukan thread)
            asyncio.create_task(worker_manager.start_workers())
            print(f"✅ Worker system started with {Config.WORKER_COUNT} workers")
        else:
            print("⚠️ Worker system disabled")
        
        print("🎉 Application startup completed!")
        
        yield
        
    except Exception as e:
        print(f"❌ Startup failed: {e}")
        raise e
    
    # Shutdown
    print("🛑 Shutting down PDF Extraction API...")
    
    if worker_manager:
        await worker_manager.stop_workers()
        print("✅ Workers stopped")
    
    print("🏁 Shutdown completed")

def signal_handler(signum, frame):
    """Signal handler untuk graceful shutdown"""
    print(f"\n🛑 Received signal {signum}")
    if worker_manager:
        worker_manager.is_running = False

# Inisialisasi FastAPI app dengan lifespan
app = FastAPI(
    title="PDF Extraction API with Docling",
    description="API untuk ekstraksi data dari file PDF menggunakan Docling dengan progress tracking di Redis",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware untuk mengizinkan request dari frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Dalam production, ganti dengan domain yang spesifik
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.post("/upload", response_model=Dict[str, Any])
async def upload_pdf(file: UploadFile = File(...)):
    """
    Endpoint untuk upload file PDF dan menambahkan ke queue
    
    Args:
        file: File PDF yang diupload
    
    Returns:
        JSON response dengan task_id untuk tracking progress
    """
    try:
        # Validasi file extension
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=400, 
                detail="Only PDF files are allowed. Please upload a .pdf file"
            )
        
        # Validasi file size
        file_content = await file.read()
        if len(file_content) > Config.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413, 
                detail=f"File size too large. Maximum size is {Config.MAX_FILE_SIZE/1024/1024:.1f}MB"
            )
        
        # Validasi file content (basic check)
        if not file_content.startswith(b'%PDF'):
            raise HTTPException(
                status_code=400, 
                detail="Invalid PDF file. File does not appear to be a valid PDF"
            )
        
        # Cek status queue
        queue_info = redis_manager.get_queue_info()
        if queue_info["is_full"]:
            raise HTTPException(
                status_code=503,
                detail=f"Queue is full ({queue_info['queue_size']}/{queue_info['max_queue_size']}). Please try again later."
            )
        
        # Buat task baru di Redis
        task_id = redis_manager.create_task(file.filename)
        print(f"📄 New PDF upload task created: {task_id} for file: {file.filename}")
        
        # Tambahkan job ke queue untuk diproses oleh workers
        success = redis_manager.enqueue_pdf_job(task_id, file_content, file.filename)
        
        if not success:
            # Jika gagal enqueue, hapus task
            redis_manager.delete_task(task_id)
            raise HTTPException(
                status_code=503,
                detail="Failed to add job to processing queue. Please try again later."
            )
        
        # Return task_id untuk tracking
        return {
            "success": True,
            "message": "PDF upload successful. Added to processing queue.",
            "task_id": task_id,
            "filename": file.filename,
            "file_size": len(file_content),
            "status": "queued",
            "queue_position": queue_info["queue_size"] + 1
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle unexpected errors
        print(f"❌ Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.get("/status/{task_id}", response_model=Dict[str, Any])
async def get_task_status(task_id: str):
    """
    Endpoint untuk mengecek status dan progress ekstraksi PDF
    
    Args:
        task_id: ID task yang ingin dicek statusnya
    
    Returns:
        JSON response dengan status, progress, dan hasil ekstraksi
    """
    try:
        # Ambil status task dari Redis
        task_data = redis_manager.get_task_status(task_id)
        
        if not task_data:
            raise HTTPException(
                status_code=404, 
                detail=f"Task with ID {task_id} not found. Task may have expired."
            )
        
        # Return semua informasi task
        return {
            "success": True,
            "task_id": task_id,
            "status": task_data.get("status"),
            "progress": task_data.get("progress"),
            "message": task_data.get("message"),
            "filename": task_data.get("filename"),
            "result": task_data.get("result"),
            "error": task_data.get("error"),
            "created_at": task_data.get("created_at"),
            "completed_at": task_data.get("completed_at")
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        print(f"❌ Status check error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {str(e)}")

@app.get("/result/{task_id}", response_model=Dict[str, Any])
async def get_extraction_result(task_id: str):
    """
    Endpoint untuk mendapatkan hasil ekstraksi PDF
    Hanya mengembalikan data jika task sudah completed
    
    Args:
        task_id: ID task yang ingin diambil hasilnya
    
    Returns:
        JSON response dengan hasil ekstraksi PDF
    """
    try:
        # Ambil status task dari Redis
        task_data = redis_manager.get_task_status(task_id)
        
        if not task_data:
            raise HTTPException(
                status_code=404, 
                detail=f"Task with ID {task_id} not found"
            )
        
        # Cek apakah task sudah selesai
        if task_data.get("status") != "completed":
            current_status = task_data.get("status", "unknown")
            current_progress = task_data.get("progress", 0)
            
            return {
                "success": False,
                "message": f"Task is not completed yet. Current status: {current_status} ({current_progress}%)",
                "task_id": task_id,
                "status": current_status,
                "progress": current_progress
            }
        
        # Return hasil ekstraksi jika task completed
        result = task_data.get("result")
        if not result:
            raise HTTPException(
                status_code=500, 
                detail="Task marked as completed but no result data found"
            )
        
        return {
            "success": True,
            "task_id": task_id,
            "extraction_result": result,
            "completed_at": task_data.get("completed_at")
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        print(f"❌ Result retrieval error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get extraction result: {str(e)}")

@app.get("/tasks", response_model=Dict[str, Any])
async def list_all_tasks():
    """
    Endpoint untuk melihat semua task yang ada
    Berguna untuk monitoring dan debugging
    
    Returns:
        JSON response dengan list semua task
    """
    try:
        # Ambil semua task dari Redis
        tasks = redis_manager.get_all_tasks()
        
        return {
            "success": True,
            "total_tasks": len(tasks),
            "tasks": tasks
        }
        
    except Exception as e:
        print(f"❌ List tasks error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get task list: {str(e)}")

@app.delete("/task/{task_id}", response_model=Dict[str, Any])
async def delete_task(task_id: str):
    """
    Endpoint untuk menghapus task dari Redis
    
    Args:
        task_id: ID task yang ingin dihapus
    
    Returns:
        JSON response konfirmasi penghapusan
    """
    try:
        # Cek apakah task ada
        task_data = redis_manager.get_task_status(task_id)
        if not task_data:
            raise HTTPException(
                status_code=404, 
                detail=f"Task with ID {task_id} not found"
            )
        
        # Hapus task dari Redis
        redis_manager.delete_task(task_id)
        
        return {
            "success": True,
            "message": f"Task {task_id} deleted successfully",
            "task_id": task_id
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        print(f"❌ Delete task error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete task: {str(e)}")

@app.get("/health", response_model=Dict[str, Any])
async def health_check():
    """
    Endpoint untuk health check
    Berguna untuk monitoring apakah service berjalan dengan baik
    
    Returns:
        JSON response dengan status health
    """
    try:
        # Test Redis connection
        redis_status = "connected"
        try:
            redis_manager.redis_client.ping()
        except:
            redis_status = "disconnected"
        
        # Get worker status
        worker_status = "disabled"
        active_workers = 0
        if worker_manager and Config.ENABLE_WORKERS:
            worker_stats = worker_manager.get_all_stats()
            active_workers = worker_stats["worker_manager"]["active_workers"]
            worker_status = "running" if active_workers > 0 else "stopped"
        
        # Get queue info
        queue_info = redis_manager.get_queue_info()
        
        return {
            "success": True,
            "status": "healthy",
            "redis_status": redis_status,
            "worker_status": worker_status,
            "active_workers": active_workers,
            "queue_size": queue_info["queue_size"],
            "message": "PDF Extraction API is running properly"
        }
        
    except Exception as e:
        return {
            "success": False,
            "status": "unhealthy",
            "error": str(e)
        }

@app.get("/workers", response_model=Dict[str, Any])
async def get_worker_stats():
    """
    Endpoint untuk mendapatkan statistik workers
    
    Returns:
        JSON response dengan statistik semua workers
    """
    try:
        if not worker_manager or not Config.ENABLE_WORKERS:
            return {
                "success": False,
                "message": "Worker system is disabled",
                "workers_enabled": False
            }
        
        stats = worker_manager.get_all_stats()
        
        return {
            "success": True,
            "workers_enabled": True,
            "stats": stats
        }
        
    except Exception as e:
        print(f"❌ Worker stats error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get worker stats: {str(e)}")

@app.get("/queue", response_model=Dict[str, Any])
async def get_queue_info():
    """
    Endpoint untuk mendapatkan informasi queue
    
    Returns:
        JSON response dengan informasi queue
    """
    try:
        queue_info = redis_manager.get_queue_info()
        
        return {
            "success": True,
            "queue_info": queue_info
        }
        
    except Exception as e:
        print(f"❌ Queue info error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get queue info: {str(e)}")

@app.post("/queue/clear", response_model=Dict[str, Any])
async def clear_queue():
    """
    Endpoint untuk membersihkan queue (untuk debugging/maintenance)
    
    Returns:
        JSON response konfirmasi pembersihan queue
    """
    try:
        cleared_count = redis_manager.clear_queue()
        
        return {
            "success": True,
            "message": f"Queue cleared successfully. {cleared_count} jobs removed.",
            "cleared_count": cleared_count
        }
        
    except Exception as e:
        print(f"❌ Clear queue error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear queue: {str(e)}")

@app.get("/", response_model=Dict[str, Any])
async def root():
    """
    Root endpoint dengan informasi API
    
    Returns:
        JSON response dengan informasi dasar API
    """
    return {
        "message": "PDF Extraction API with Docling and Worker System",
        "version": "2.0.0",
        "worker_system": {
            "enabled": Config.ENABLE_WORKERS,
            "worker_count": Config.WORKER_COUNT if Config.ENABLE_WORKERS else 0,
            "poll_interval": Config.WORKER_POLL_INTERVAL
        },
        "endpoints": {
            "upload": "POST /upload - Upload PDF file for extraction",
            "status": "GET /status/{task_id} - Check extraction progress",
            "result": "GET /result/{task_id} - Get extraction result",
            "tasks": "GET /tasks - List all tasks",
            "workers": "GET /workers - Get worker statistics",
            "queue": "GET /queue - Get queue information",
            "clear_queue": "POST /queue/clear - Clear processing queue",
            "health": "GET /health - Health check",
            "delete": "DELETE /task/{task_id} - Delete task"
        },
        "documentation": "/docs - Swagger UI documentation"
    }

if __name__ == "__main__":
    """
    Entry point untuk menjalankan aplikasi
    Jalankan dengan: python main.py
    """
    print("🚀 Starting PDF Extraction API with Worker System...")
    print(f"📡 Server will run on: http://{Config.API_HOST}:{Config.API_PORT}")
    print(f"📚 API Documentation: http://{Config.API_HOST}:{Config.API_PORT}/docs")
    print(f"🔧 Redis: {Config.REDIS_HOST}:{Config.REDIS_PORT}")
    print(f"👷 Workers: {Config.WORKER_COUNT if Config.ENABLE_WORKERS else 'Disabled'}")
    if Config.ENABLE_WORKERS:
        print(f"⏱️ Worker Poll Interval: {Config.WORKER_POLL_INTERVAL}s")
        print(f"📋 Queue: {Config.QUEUE_NAME} (Max: {Config.MAX_QUEUE_SIZE})")
    
    # Jalankan server dengan uvicorn
    uvicorn.run(
        "main:app",  # Module:app
        host=Config.API_HOST,
        port=Config.API_PORT,
        reload=Config.DEBUG,  # Auto-reload saat development
        log_level="info"
    )