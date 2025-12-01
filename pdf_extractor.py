import asyncio
import tempfile
import os
from typing import Dict, Any
from docling.document_converter import DocumentConverter
from redis_manager import RedisManager

# Import untuk fallback extraction
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    print("Warning: PyMuPDF not available for fallback extraction")

class PDFExtractor:
    """
    Kelas untuk melakukan ekstraksi data dari file PDF menggunakan Docling
    Dengan progress tracking yang disimpan di Redis
    """
    
    def __init__(self, redis_manager: RedisManager):
        """
        Inisialisasi PDF extractor dengan Redis manager
        Args:
            redis_manager: Instance RedisManager untuk tracking progress
        """
        self.redis_manager = redis_manager
        # Inisialisasi Docling converter
        self.converter = DocumentConverter()
        
    async def extract_pdf_async(self, task_id: str, pdf_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Async method untuk ekstraksi PDF dengan progress tracking
        Args:
            task_id: ID task untuk tracking progress
            pdf_content: Binary content dari file PDF
            filename: Nama file PDF
        Returns:
            Dictionary hasil ekstraksi
        """
        try:
            # Update status: mulai processing
            self.redis_manager.update_task_progress(
                task_id, 
                10, 
                "Starting PDF extraction...", 
                "processing"
            )
            
            # Simpan PDF ke temporary file karena Docling membutuhkan file path
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(pdf_content)
                temp_file_path = temp_file.name
            
            try:
                # Update progress: file preparation selesai
                self.redis_manager.update_task_progress(
                    task_id, 
                    25, 
                    "PDF file prepared, starting extraction..."
                )
                
                # Simulate progress update saat memulai konversi
                await asyncio.sleep(0.5)  # Small delay untuk demo progress
                
                # Update progress: mulai konversi dengan Docling
                self.redis_manager.update_task_progress(
                    task_id, 
                    40, 
                    "Converting PDF with Docling..."
                )
                
                # Konversi PDF menggunakan Docling dengan error handling
                try:
                    # Docling akan mengekstrak text, tables, images, dan metadata
                    result = self.converter.convert(temp_file_path)
                except Exception as docling_error:
                    # Jika Docling gagal, coba dengan fallback method
                    print(f"Docling conversion failed: {docling_error}")
                    self.redis_manager.update_task_progress(
                        task_id, 
                        45, 
                        "Docling failed, trying fallback extraction..."
                    )
                    
                    # Fallback ke PyMuPDF untuk ekstraksi dasar
                    extracted_data = await self._fallback_extraction(temp_file_path, task_id)
                    
                    # Prepare final result dengan fallback
                    final_result = {
                        "filename": filename,
                        "extraction_successful": True,
                        "extraction_method": "fallback_pymupdf",
                        "data": extracted_data,
                        "metadata": {
                            "total_pages": len(extracted_data.get("pages", [])),
                            "total_text_length": len(extracted_data.get("full_text", "")),
                            "has_tables": len(extracted_data.get("tables", [])) > 0,
                            "has_images": len(extracted_data.get("images", [])) > 0
                        },
                        "warning": f"Used fallback extraction due to: {str(docling_error)}"
                    }
                    
                    # Mark task sebagai completed dengan warning
                    self.redis_manager.complete_task(task_id, final_result, success=True)
                    return final_result
                
                # Update progress: konversi selesai, mulai parsing hasil
                self.redis_manager.update_task_progress(
                    task_id, 
                    70, 
                    "PDF conversion completed, extracting data..."
                )
                
                # Simulate processing time
                await asyncio.sleep(0.5)
                
                # Parse hasil ekstraksi
                extracted_data = await self._parse_docling_result(result, task_id)
                
                # Update progress: parsing selesai
                self.redis_manager.update_task_progress(
                    task_id, 
                    90, 
                    "Data extraction completed, finalizing..."
                )
                
                # Prepare final result
                final_result = {
                    "filename": filename,
                    "extraction_successful": True,
                    "extraction_method": "docling",
                    "data": extracted_data,
                    "metadata": {
                        "total_pages": len(extracted_data.get("pages", [])),
                        "total_text_length": len(extracted_data.get("full_text", "")),
                        "has_tables": len(extracted_data.get("tables", [])) > 0,
                        "has_images": len(extracted_data.get("images", [])) > 0
                    }
                }
                
                # Mark task sebagai completed
                self.redis_manager.complete_task(task_id, final_result, success=True)
                
                return final_result
                
            finally:
                # Cleanup: hapus temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    
        except Exception as e:
            # Handle error dan update task status
            error_result = {
                "filename": filename,
                "extraction_successful": False,
                "error": str(e),
                "data": None
            }
            
            # Mark task sebagai failed
            self.redis_manager.complete_task(task_id, error_result, success=False)
            
            return error_result
    
    async def _parse_docling_result(self, docling_result, task_id: str) -> Dict[str, Any]:
        """
        Parse hasil dari Docling menjadi format yang mudah digunakan
        Args:
            docling_result: Hasil konversi dari Docling
            task_id: ID task untuk progress tracking
        Returns:
            Dictionary dengan data yang telah diparsing
        """
        try:
            # Get document object dari hasil konversi
            doc = docling_result.document
            
            # Update progress: mulai parsing
            self.redis_manager.update_task_progress(
                task_id, 
                75, 
                "Parsing extracted content..."
            )
            
            # Ekstrak full text dari document
            full_text = doc.export_to_text()
            
            # Extract tables jika ada
            tables = []
            table_elements = [item for item in doc.texts if hasattr(item, 'label') and 'table' in str(item.label).lower()]
            for table_elem in table_elements:
                tables.append({
                    "content": str(table_elem),
                    "page": getattr(table_elem, 'page', 'unknown')
                })
            
            # Extract images info jika ada
            images = []
            picture_elements = [item for item in doc.texts if hasattr(item, 'label') and 'picture' in str(item.label).lower()]
            for img_elem in picture_elements:
                images.append({
                    "description": str(img_elem),
                    "page": getattr(img_elem, 'page', 'unknown')
                })
            
            # Parse per halaman
            pages = []
            # Docling biasanya menyimpan informasi page dalam metadata
            # Kita akan split text berdasarkan page breaks atau estimasi
            text_lines = full_text.split('\n')
            
            # Estimasi pembagian halaman berdasarkan panjang text
            # Ini adalah pendekatan sederhana, bisa disesuaikan
            lines_per_page = 50  # Estimasi lines per halaman
            current_page = 1
            current_page_lines = []
            
            for line in text_lines:
                current_page_lines.append(line)
                
                if len(current_page_lines) >= lines_per_page:
                    pages.append({
                        "page_number": current_page,
                        "content": '\n'.join(current_page_lines),
                        "line_count": len(current_page_lines)
                    })
                    current_page += 1
                    current_page_lines = []
            
            # Tambahkan halaman terakhir jika ada sisa
            if current_page_lines:
                pages.append({
                    "page_number": current_page,
                    "content": '\n'.join(current_page_lines),
                    "line_count": len(current_page_lines)
                })
            
            # Update progress: parsing hampir selesai
            self.redis_manager.update_task_progress(
                task_id, 
                85, 
                "Content parsing completed..."
            )
            
            return {
                "full_text": full_text,
                "pages": pages,
                "tables": tables,
                "images": images,
                "word_count": len(full_text.split()),
                "character_count": len(full_text)
            }
            
        except Exception as e:
            print(f"Error parsing Docling result: {e}")
            # Return minimal data jika parsing gagal
            return {
                "full_text": "Error parsing document content",
                "pages": [],
                "tables": [],
                "images": [],
                "word_count": 0,
                "character_count": 0,
                "parsing_error": str(e)
            }
    
    def extract_pdf_sync(self, task_id: str, pdf_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Synchronous wrapper untuk ekstraksi PDF
        Args:
            task_id: ID task untuk tracking progress
            pdf_content: Binary content dari file PDF  
            filename: Nama file PDF
        Returns:
            Dictionary hasil ekstraksi
        """
        # Jalankan async method dalam event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.extract_pdf_async(task_id, pdf_content, filename)
            )
        finally:
            loop.close()
    
    async def _fallback_extraction(self, pdf_path: str, task_id: str) -> Dict[str, Any]:
        """
        Fallback extraction method menggunakan PyMuPDF jika Docling gagal
        Args:
            pdf_path: Path ke file PDF
            task_id: ID task untuk progress tracking
        Returns:
            Dictionary dengan data yang telah diekstrak
        """
        if not PYMUPDF_AVAILABLE:
            # Jika PyMuPDF tidak tersedia, return basic extraction
            return {
                "full_text": "Fallback extraction failed - PyMuPDF not available",
                "pages": [],
                "tables": [],
                "images": [],
                "word_count": 0,
                "character_count": 0,
                "extraction_error": "Both Docling and PyMuPDF failed"
            }
        
        try:
            # Update progress: menggunakan fallback
            self.redis_manager.update_task_progress(
                task_id, 
                50, 
                "Using PyMuPDF fallback extraction..."
            )
            
            # Buka PDF dengan PyMuPDF
            pdf_document = fitz.open(pdf_path)
            
            # Ekstrak data dari setiap halaman
            pages = []
            full_text = ""
            images_info = []
            
            for page_num in range(pdf_document.page_count):
                page = pdf_document[page_num]
                
                # Ekstrak text dari halaman
                page_text = page.get_text()
                full_text += page_text + "\n"
                
                # Ekstrak informasi gambar dasar
                image_list = page.get_images()
                for img_idx, img in enumerate(image_list):
                    images_info.append({
                        "page": page_num + 1,
                        "image_index": img_idx,
                        "description": f"Image {img_idx + 1} on page {page_num + 1}"
                    })
                
                # Simpan data per halaman
                pages.append({
                    "page_number": page_num + 1,
                    "content": page_text,
                    "line_count": len(page_text.split('\n')),
                    "word_count": len(page_text.split()),
                    "character_count": len(page_text)
                })
                
                # Update progress per halaman
                progress = 50 + (20 * (page_num + 1) / pdf_document.page_count)
                self.redis_manager.update_task_progress(
                    task_id, 
                    int(progress), 
                    f"Processed page {page_num + 1}/{pdf_document.page_count} (fallback)"
                )
                
                await asyncio.sleep(0.1)  # Small delay
            
            # Tutup PDF document
            pdf_document.close()
            
            # Update progress: finalisasi fallback
            self.redis_manager.update_task_progress(
                task_id, 
                75, 
                "Fallback extraction completed..."
            )
            
            return {
                "full_text": full_text.strip(),
                "pages": pages,
                "tables": [],  # Table extraction tidak tersedia di fallback
                "images": images_info,
                "word_count": len(full_text.split()),
                "character_count": len(full_text),
                "extraction_method": "pymupdf_fallback",
                "note": "Tables extraction not available in fallback mode"
            }
            
        except Exception as e:
            print(f"Error in fallback extraction: {e}")
            return {
                "full_text": "Fallback extraction failed",
                "pages": [],
                "tables": [],
                "images": [],
                "word_count": 0,
                "character_count": 0,
                "extraction_error": f"Fallback extraction failed: {str(e)}"
            }