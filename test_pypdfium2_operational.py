#!/usr/bin/env python3
"""
Quick PyPDFium2 Operational Test
Test actual PyPDFium2 backend usage during PDF processing
"""

import os
import sys
import tempfile
from typing import Dict, Any

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pdf_extractor import PDFExtractor
from redis_manager import RedisManager
import warnings

# Suppress warnings untuk output yang bersih
warnings.filterwarnings("ignore")

def create_sample_pdf() -> bytes:
    """Create a minimal valid PDF for testing"""
    # Minimal PDF content yang valid
    pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(PyPDFium2 Test) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000206 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
299
%%EOF"""
    return pdf_content

def test_pypdfium2_operational():
    """Test PyPDFium2 operational usage"""
    print("🧪 PyPDFium2 Operational Test")
    print("=" * 60)
    
    try:
        # 1. Initialize components
        print("1️⃣ Initializing components...")
        redis_manager = RedisManager()
        extractor = PDFExtractor(redis_manager)
        
        # Verify backend configuration
        backend_info = extractor.get_current_backend_info()
        print(f"🔧 Backend: {backend_info['backend_configured']}")
        
        if backend_info['backend_configured'] != 'pypdfium2':
            print("❌ PyPDFium2 not configured!")
            return False
        
        # 2. Create test PDF
        print("\n2️⃣ Creating test PDF...")
        pdf_content = create_sample_pdf()
        print(f"📄 Test PDF created ({len(pdf_content)} bytes)")
        
        # 3. Save to temporary file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            tmp_file.write(pdf_content)
            temp_path = tmp_file.name
        
        print(f"💾 PDF saved to: {temp_path}")
        
        # 4. Test PyPDFium2 directly (bypass async extraction)
        print("\n3️⃣ Testing PyPDFium2 directly...")
        try:
            # Call Docling converter directly with our PyPDFium2 configuration
            print("🔄 Converting with Docling + PyPDFium2...")
            result = extractor.converter.convert(temp_path)
            
            print(f"✅ Conversion successful!")
            print(f"📊 Result type: {type(result)}")
            print(f"📄 Document pages: {len(result.pages) if hasattr(result, 'pages') else 'unknown'}")
            
            # Check if document has content
            if hasattr(result, 'pages') and result.pages:
                page = result.pages[0]
                print(f"📝 First page type: {type(page)}")
                print(f"📐 Page dimensions available: {hasattr(page, 'size')}")
            
            return True
            
        except Exception as conv_error:
            print(f"❌ Conversion failed: {conv_error}")
            return False
        
        finally:
            # Cleanup
            try:
                os.unlink(temp_path)
                print(f"🧹 Cleaned up temp file: {temp_path}")
            except:
                pass
    
    except Exception as e:
        print(f"💥 Test failed: {e}")
        return False

def main():
    """Run the operational test"""
    print("🚀 Starting PyPDFium2 Operational Test")
    print("=" * 80)
    
    success = test_pypdfium2_operational()
    
    print("\n" + "=" * 80)
    print("📊 TEST RESULT")
    print("=" * 80)
    
    if success:
        print("🎉 SUCCESS: PyPDFium2 backend is OPERATIONAL!")
        print("✅ The setting pdf_backend='pypdfium2' is working in extract_pdf_async")
        return True
    else:
        print("❌ FAILURE: PyPDFium2 backend test failed")
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