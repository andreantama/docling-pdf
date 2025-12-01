#!/usr/bin/env python3
"""
Startup script untuk PDF Extraction API
Includes health checks dan error handling
"""

import sys
import os
import subprocess
import time
from datetime import datetime

def check_redis():
    """Check if Redis is running"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        return True
    except Exception as e:
        print(f"❌ Redis check failed: {e}")
        return False

def check_dependencies():
    """Check if all dependencies are installed"""
    missing_deps = []
    
    required_packages = [
        'fastapi',
        'uvicorn',
        'redis',
        'docling',
        'fitz',  # PyMuPDF
    ]
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_deps.append(package)
    
    if missing_deps:
        print(f"❌ Missing dependencies: {missing_deps}")
        print("Run: pip install -r requirements.txt")
        return False
    
    return True

def start_redis_if_needed():
    """Try to start Redis if it's not running"""
    if not check_redis():
        print("🔄 Trying to start Redis...")
        try:
            # Try different Redis start commands
            redis_commands = [
                'redis-server --daemonize yes',
                'sudo systemctl start redis',
                'sudo service redis-server start'
            ]
            
            for cmd in redis_commands:
                try:
                    subprocess.run(cmd, shell=True, check=True, capture_output=True)
                    time.sleep(2)  # Wait for Redis to start
                    if check_redis():
                        print("✅ Redis started successfully")
                        return True
                except subprocess.CalledProcessError:
                    continue
            
            print("❌ Could not start Redis automatically")
            print("Please start Redis manually:")
            print("  sudo systemctl start redis")
            print("  # or")
            print("  redis-server")
            return False
            
        except Exception as e:
            print(f"❌ Error starting Redis: {e}")
            return False
    
    return True

def main():
    """Main startup function"""
    print("🚀 Starting PDF Extraction API")
    print("=" * 50)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check dependencies
    print("🔍 Checking dependencies...")
    if not check_dependencies():
        sys.exit(1)
    print("✅ All dependencies are available")
    
    # Check and start Redis
    print("🔍 Checking Redis...")
    if not start_redis_if_needed():
        print("⚠️  Warning: Redis is not available. Some features may not work.")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            sys.exit(1)
    else:
        print("✅ Redis is running")
    
    # Test import of main modules
    print("🔍 Testing module imports...")
    try:
        from pdf_extractor import PDFExtractor
        from redis_manager import RedisManager
        from main import app
        print("✅ All modules imported successfully")
    except Exception as e:
        print(f"❌ Module import failed: {e}")
        sys.exit(1)
    
    # Start the API
    print("\n🚀 Starting FastAPI server...")
    print("📖 API Documentation: http://localhost:8000/docs")
    print("🏥 Health Check: http://localhost:8000/health")
    print("📊 API Info: http://localhost:8000/")
    print("\n⏹️  Press Ctrl+C to stop the server")
    print("=" * 50)
    
    try:
        import uvicorn
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()