#!/usr/bin/env python3
"""
Backend Verification Test - Verify PyPDFium2 Configuration
Tests whether PyPDFium2 backend is properly configured and active
"""

import os
import sys
from typing import Dict, Any

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pdf_extractor import PDFExtractor
from redis_manager import RedisManager
import warnings

# Suppress warnings untuk test yang bersih
warnings.filterwarnings("ignore")

def test_backend_verification():
    """Test backend configuration and verify PyPDFium2 is active"""
    print("🔍 Backend Verification Test")
    print("=" * 60)
    
    # Initialize extractor
    print("1️⃣ Initializing PDF extractor...")
    redis_manager = RedisManager()
    extractor = PDFExtractor(redis_manager)
    
    # Get backend information
    print("\n2️⃣ Checking backend configuration...")
    backend_info = extractor.get_current_backend_info()
    
    print(f"📊 Backend Info:")
    for key, value in backend_info.items():
        print(f"   • {key}: {value}")
    
    # Verify PyPDFium2 is configured
    print("\n3️⃣ Verifying PyPDFium2 configuration...")
    
    backend_configured = backend_info.get('backend_configured', 'unknown')
    
    if backend_configured == 'pypdfium2':
        print("✅ SUCCESS: PyPDFium2 backend is properly configured!")
        return True
    elif backend_configured == 'unknown':
        print("⚠️  WARNING: Backend configuration could not be determined")
        print("   This might be normal depending on Docling version")
        return False
    elif backend_configured == 'error_getting_info':
        print("❌ ERROR: Could not retrieve backend information")
        return False
    else:
        print(f"❌ ERROR: Expected 'pypdfium2' but got '{backend_configured}'")
        return False

def test_backend_imports():
    """Test that PyPDFium2 can be imported and is available"""
    print("\n4️⃣ Testing PyPDFium2 import availability...")
    
    try:
        import pypdfium2
        print(f"✅ PyPDFium2 successfully imported - version: {getattr(pypdfium2, '__version__', 'unknown')}")
        return True
    except ImportError as e:
        print(f"❌ PyPDFium2 import failed: {e}")
        return False

def test_docling_backend_options():
    """Test Docling's backend configuration options"""
    print("\n5️⃣ Testing Docling backend configuration...")
    
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
        
        # Test configuration creation
        pipeline_options = PdfPipelineOptions(
            pdf_backend="pypdfium2",
            do_ocr=False,
            do_table_structure=True,
            generate_page_images=False
        )
        
        format_options = {
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
        
        converter = DocumentConverter(format_options=format_options)
        
        print("✅ Docling backend configuration test passed!")
        print(f"   • Pipeline options created successfully")
        print(f"   • Backend set to: pypdfium2")
        print(f"   • DocumentConverter initialized with format options")
        
        return True
        
    except Exception as e:
        print(f"❌ Docling backend configuration test failed: {e}")
        return False

def main():
    """Run all backend verification tests"""
    print("🚀 Starting Backend Verification Tests")
    print("=" * 80)
    
    results = []
    
    # Test 1: Backend configuration verification
    results.append(test_backend_verification())
    
    # Test 2: PyPDFium2 import test
    results.append(test_backend_imports())
    
    # Test 3: Docling backend options test
    results.append(test_docling_backend_options())
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 VERIFICATION SUMMARY")
    print("=" * 80)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED - PyPDFium2 backend is properly configured!")
        return True
    else:
        print("⚠️  Some tests failed - check configuration above")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n💥 Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)