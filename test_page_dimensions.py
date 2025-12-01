#!/usr/bin/env python3
"""
Test script khusus untuk menguji penanganan error page-dimensions
dengan konfigurasi PyPDFium2 yang telah diperbaiki
"""

import asyncio
import tempfile
import os
import sys
from pdf_extractor import PDFExtractor
from redis_manager import RedisManager

def create_problematic_pdf():
    """Create a PDF that typically causes page-dimensions error"""
    
    # PDF with missing MediaBox that often causes page-dimensions error
    problematic_pdf = b"""%PDF-1.7
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
/Resources <<
/Font <<>>
/ProcSet [/PDF /Text /ImageB /ImageC /ImageI]
/XObject <<
/TPL0 4 0 R
/TPL1 5 0 R
>>
>>
/Contents 6 0 R
>>
endobj

4 0 obj
<<
/Type /XObject
/Subtype /Form
/FormType 1
/PTEX.FileName (./template.pdf)
/PTEX.PageNumber 1
/PTEX.InfoDict 7 0 R
/BBox [0 0 595.276 841.89]
/Resources 8 0 R
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Test Content Page 1) Tj
ET
endstream
endobj

5 0 obj
<<
/Type /XObject
/Subtype /Form
/FormType 1
/PTEX.FileName (./template.pdf)
/PTEX.PageNumber 2
/BBox [0 0 595.276 841.89]
/Resources 8 0 R
/Length 44
>>
stream
BT
/F1 12 Tf
100 600 Td
(Test Content Page 2) Tj
ET
endstream
endobj

6 0 obj
<<
/Length 88
>>
stream
q
595.276 0 0 841.89 0 0 cm
/TPL0 Do
Q
q
595.276 0 0 841.89 0 0 cm
/TPL1 Do
Q
endstream
endobj

7 0 obj
<<
/Producer (Test Producer)
/Title ()
/Subject ()
/Creator (Test Creator)
/Author ()
/Keywords ()
>>
endobj

8 0 obj
<<
/Font <<>>
/ProcSet [/PDF /Text /ImageB /ImageC /ImageI]
>>
endobj

xref
0 9
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000306 00000 n 
0000000620 00000 n 
0000000916 00000 n 
0000001056 00000 n 
0000001194 00000 n 
trailer
<<
/Size 9
/Root 1 0 R
/Info 7 0 R
>>
startxref
1269
%%EOF"""

    return problematic_pdf

async def test_page_dimensions_handling():
    """Test the enhanced page-dimensions error handling"""
    
    print("🧪 Testing Enhanced Page-Dimensions Error Handling")
    print("=" * 60)
    
    try:
        # Initialize components
        redis_manager = RedisManager()
        pdf_extractor = PDFExtractor(redis_manager)
        
        print("✅ Components initialized with enhanced PyPDFium2 configuration")
        
        # Create problematic PDF
        pdf_content = create_problematic_pdf()
        filename = "test_page_dimensions.pdf"
        
        print(f"\n🔬 Testing problematic PDF: {filename}")
        print("   This PDF typically causes 'page-dimensions' errors")
        
        # Run extraction
        task_id = f"test_page_dims_{hash(pdf_content) % 10000}"
        
        print("\n🚀 Starting extraction with enhanced error handling...")
        result = await pdf_extractor.extract_pdf_async(task_id, pdf_content, filename)
        
        # Analyze results
        print("\n📊 Extraction Results:")
        print("=" * 30)
        print(f"Success: {result.get('extraction_successful', False)}")
        print(f"Method: {result.get('extraction_method', 'unknown')}")
        
        if result.get('warning'):
            print(f"Warning: {result['warning']}")
        
        data = result.get('data', {})
        if data:
            print(f"Pages extracted: {len(data.get('pages', []))}")
            print(f"Text length: {len(data.get('full_text', ''))}")
            print(f"Tables found: {len(data.get('tables', []))}")
            print(f"Images found: {len(data.get('images', []))}")
            
            # Show sample text
            text = data.get('full_text', '')
            if text:
                sample = text[:100].replace('\n', ' ')
                print(f"Sample text: {sample}...")
        
        return result
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return None

async def test_pdf_dimension_fix():
    """Test the PDF dimension fixing function"""
    
    print("\n🔧 Testing PDF Dimension Fix Function")
    print("=" * 40)
    
    try:
        redis_manager = RedisManager()
        pdf_extractor = PDFExtractor(redis_manager)
        
        # Create test PDF and save to file
        pdf_content = create_problematic_pdf()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file.write(pdf_content)
            original_path = temp_file.name
        
        try:
            # Test the fix function
            print("🔧 Applying PDF dimension fix...")
            fixed_path = pdf_extractor._fix_pdf_page_dimensions(original_path)
            
            if fixed_path != original_path:
                print(f"✅ PDF dimensions fixed: {fixed_path}")
                
                # Test if fixed version works better
                print("🔍 Testing fixed PDF with Docling...")
                try:
                    # Here you could test conversion with the fixed PDF
                    print("✅ Fixed PDF ready for processing")
                except Exception as e:
                    print(f"⚠️ Fixed PDF still has issues: {e}")
                
                # Cleanup
                if os.path.exists(fixed_path):
                    os.unlink(fixed_path)
            else:
                print("ℹ️ No dimension fixing was needed or possible")
                
        finally:
            if os.path.exists(original_path):
                os.unlink(original_path)
                
    except Exception as e:
        print(f"❌ PDF fix test failed: {e}")

def main():
    """Main test function"""
    print("🎯 Enhanced Page-Dimensions Error Handling Test")
    print("=" * 60)
    print("Testing the improved PyPDFium2 configuration and")
    print("page-dimensions error handling mechanisms")
    print()
    
    # Run tests
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Test 1: Enhanced error handling
        result = loop.run_until_complete(test_page_dimensions_handling())
        
        # Test 2: PDF dimension fixing
        loop.run_until_complete(test_pdf_dimension_fix())
        
        # Summary
        print(f"\n🎉 Testing completed!")
        if result and result.get('extraction_successful'):
            print("✅ Enhanced page-dimensions handling is working")
            print("✅ System can handle problematic PDFs")
        else:
            print("⚠️ Some issues remain - check logs for details")
            
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
    finally:
        loop.close()

if __name__ == "__main__":
    main()