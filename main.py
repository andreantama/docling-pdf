from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
from typing import Dict, Any
import os

# Import custom modules
from config import Config
from redis_manager import RedisManager
from pdf_extractor import PDFExtractor

# Inisialisasi FastAPI app
app = FastAPI(
    title="PDF Extraction API with Docling",
    description="API untuk ekstraksi data dari file PDF menggunakan Docling dengan progress tracking di Redis",
    version="1.0.0"
)

# CORS middleware untuk mengizinkan request dari frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Dalam production, ganti dengan domain yang spesifik
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
redis_manager = None
pdf_extractor = None

@app.on_event("startup")
async def startup_event():
    """
    Event yang dijalankan saat aplikasi startup
    Inisialisasi koneksi Redis dan PDF extractor
    """
    global redis_manager, pdf_extractor
    
    try:
        print("🚀 Starting PDF Extraction API...")
        
        # Inisialisasi Redis manager
        redis_manager = RedisManager()
        print("✅ Redis Manager initialized")
        
        # Inisialisasi PDF extractor
        pdf_extractor = PDFExtractor(redis_manager)
        print("✅ PDF Extractor initialized")
        
        print("🎉 Application startup completed!")
        
    except Exception as e:
        print(f"❌ Startup failed: {e}")
        raise e

@app.on_event("shutdown")
async def shutdown_event():
    """
    Event yang dijalankan saat aplikasi shutdown
    Cleanup resources jika diperlukan
    """
    print("🛑 Shutting down PDF Extraction API...")

async def background_pdf_extraction(task_id: str, pdf_content: bytes, filename: str):
    """
    Background task untuk melakukan ekstraksi PDF
    Dijalankan secara asynchronous agar tidak memblokir API response
    Args:
        task_id: ID unik untuk task
        pdf_content: Binary content dari file PDF
        filename: Nama file yang diupload
    """
    try:
        # Jalankan ekstraksi PDF dengan progress tracking
        await pdf_extractor.extract_pdf_async(task_id, pdf_content, filename)
        print(f"✅ PDF extraction completed for task: {task_id}")
        
    except Exception as e:
        print(f"❌ PDF extraction failed for task {task_id}: {e}")
        # Update task sebagai failed jika terjadi error
        redis_manager.complete_task(task_id, {"error": str(e)}, success=False)

@app.post("/upload", response_model=Dict[str, Any])
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Endpoint untuk upload file PDF dan memulai proses ekstraksi
    
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
        
        # Buat task baru di Redis
        task_id = redis_manager.create_task(file.filename)
        print(f"📄 New PDF upload task created: {task_id} for file: {file.filename}")
        
        # Jalankan ekstraksi PDF sebagai background task
        background_tasks.add_task(
            background_pdf_extraction,
            task_id,
            file_content,
            file.filename
        )
        
        # Return task_id untuk tracking
        return {
            "success": True,
            "message": "PDF upload successful. Extraction started in background.",
            "task_id": task_id,
            "filename": file.filename,
            "file_size": len(file_content),
            "status": "created"
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
        
        return {
            "success": True,
            "status": "healthy",
            "redis_status": redis_status,
            "message": "PDF Extraction API is running properly"
        }
        
    except Exception as e:
        return {
            "success": False,
            "status": "unhealthy",
            "error": str(e)
        }

@app.get("/", response_model=Dict[str, Any])
async def root():
    """
    Root endpoint dengan informasi API
    
    Returns:
        JSON response dengan informasi dasar API
    """
    return {
        "message": "PDF Extraction API with Docling",
        "version": "1.0.0",
        "endpoints": {
            "upload": "POST /upload - Upload PDF file for extraction",
            "status": "GET /status/{task_id} - Check extraction progress",
            "result": "GET /result/{task_id} - Get extraction result",
            "tasks": "GET /tasks - List all tasks",
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
    print("🚀 Starting PDF Extraction API server...")
    print(f"📡 Server will run on: http://{Config.API_HOST}:{Config.API_PORT}")
    print(f"📚 API Documentation: http://{Config.API_HOST}:{Config.API_PORT}/docs")
    print(f"🔧 Redis: {Config.REDIS_HOST}:{Config.REDIS_PORT}")
    
    # Jalankan server dengan uvicorn
    uvicorn.run(
        "main:app",  # Module:app
        host=Config.API_HOST,
        port=Config.API_PORT,
        reload=Config.DEBUG,  # Auto-reload saat development
        log_level="info"
    )