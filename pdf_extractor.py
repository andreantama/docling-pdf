import asyncio
import tempfile
import os
from typing import Dict, Any
from docling.document_converter import DocumentConverter
from redis_manager import RedisManager

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
                
                # Konversi PDF menggunakan Docling
                # Docling akan mengekstrak text, tables, images, dan metadata
                result = self.converter.convert(temp_file_path)
                
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