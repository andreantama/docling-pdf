import asyncio
import tempfile
import os
import warnings
import uuid
from typing import Dict, Any
from docling.document_converter import DocumentConverter
from redis_manager import RedisManager
from config import Config
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import PdfFormatOption
from pathlib import Path
import fitz  # PyMuPDF

# Suppress specific warnings for page dimensions if configured
if Config.IGNORE_PAGE_DIMENSION_WARNINGS:
    warnings.filterwarnings("ignore", message=".*page-dimensions.*")
    warnings.filterwarnings("ignore", message=".*Stage preprocess failed.*")

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
        
        # Inisialisasi Docling converter dengan configuration
        # Configure pipeline options dengan PyPDFium2 backend dan page dimension fixes
        pipeline_options = PdfPipelineOptions(
            pdf_backend='pypdfium2'  # Use PyPDFium2 for better page-dimensions handling
        )
        pipeline_options.artifacts_path = None  # Disable artifacts to avoid path issues
        pipeline_options.do_ocr = False  # Disable OCR initially to avoid preprocessing issues
        pipeline_options.do_table_structure = True  # Enable for FPDF documents
        pipeline_options.table_structure_options.do_cell_matching = True
        
        # Optimized settings for PDFs with valid dimensions (like FPDF 1.86 output)
        pipeline_options.generate_page_images = False  # Skip image generation for better performance
        pipeline_options.generate_picture_images = False  # Skip picture processing
        pipeline_options.images_scale = 1.0  # Use original image scale
        
        # Create converter dengan PyPDFium2 backend
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
        print("✅ Docling converter initialized with enhanced PyPDFium2 configuration")
        
        # Log backend configuration details
        print(f"🔧 Backend configuration: pypdfium2 backend configured")
        
        # Validasi bahwa converter berhasil dibuat
        if not hasattr(self, 'converter') or self.converter is None:
            raise Exception("Failed to initialize PDF converter")

    @staticmethod
    def fix_pdf(input_bytes):
        """Fix PDF page dimensions using PyMuPDF"""
        doc = fitz.open(stream=input_bytes, filetype="pdf")
        for page in doc:
            rect = page.rect
            page.set_cropbox(rect)
            page.set_mediabox(rect)
        
        return doc.tobytes()

    async def extract_pdf_worker(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Method untuk worker yang memproses job dari queue
        Args:
            job_data: Data job dari queue yang berisi task_id, filename, dan pdf_content
        Returns:
            Dictionary hasil ekstraksi
        """
        task_id = job_data["task_id"]
        filename = job_data["filename"]
        pdf_content = job_data["pdf_content"]
        
        try:
            print(f"🔧 Worker processing task: {task_id} for file: {filename}")
            
            # Panggil method ekstraksi yang sudah ada
            result = await self.extract_pdf_async(task_id, pdf_content, filename)
            
            # Cleanup PDF content dari Redis
            self.redis_manager.cleanup_pdf_content(task_id)
            
            print(f"✅ Worker completed task: {task_id}")
            return result
            
        except Exception as e:
            print(f"❌ Worker failed to process task {task_id}: {e}")
            
            # Handle error dan cleanup
            error_result = {
                "filename": filename,
                "extraction_successful": False,
                "error": str(e),
                "data": None
            }
            
            # Mark task sebagai failed
            self.redis_manager.complete_task(task_id, error_result, success=False)
            
            # Cleanup PDF content dari Redis
            self.redis_manager.cleanup_pdf_content(task_id)
            
            return error_result

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
            
            # Fix PDF dimensions before processing
            fixed_pdf_content = self.fix_pdf(pdf_content)
            
            # Save fixed PDF to temporary file
            temp_file_path = Path(tempfile.gettempdir()) / f"{uuid.uuid4()}.pdf"
            temp_file_path.write_bytes(fixed_pdf_content)
            temp_file_path = str(temp_file_path)  # Convert to string for compatibility
            
            try:
                # Update progress: file preparation selesai
                self.redis_manager.update_task_progress(
                    task_id, 
                    25, 
                    "PDF file prepared, validating..."
                )
                
                # Validate PDF file
                validation_result = self._validate_pdf_file(temp_file_path)
                print(f"📋 PDF validation result for {filename}: {validation_result}")
                
                if not validation_result["is_valid"]:
                    error_msg = f"Invalid PDF file: {validation_result.get('error', 'Unknown error')}"
                    raise Exception(error_msg)
                
                # Check for potential issues and optimize extraction strategy
                warning_messages = []
                optimization_notes = []
                
                if validation_result.get("is_encrypted", False):
                    warning_messages.append("PDF is encrypted")
                if not validation_result.get("has_page_dimensions", True):
                    warning_messages.append("PDF may have page dimension issues")
                if validation_result.get("page_count", 0) == 0:
                    warning_messages.append("PDF appears to have no pages")
                
                # Optimize for well-structured PDFs (like FPDF output)
                producer = validation_result.get("metadata", {}).get("producer", "").lower()
                
                if validation_result.get("has_page_dimensions", False) and validation_result.get("pages_with_valid_dimensions", 0) == validation_result.get("page_count", 0):
                    optimization_notes.append("PDF has excellent structure - using optimized extraction")
                    print(f"✅ PDF structure excellent for {filename}: All {validation_result['page_count']} pages have valid dimensions")
                    
                    # Special optimization for FPDF documents
                    if "fpdf" in producer:
                        optimization_notes.append("FPDF document detected - enabling enhanced table extraction")
                        print(f"🎯 FPDF document detected for {filename}: Producer = {validation_result['metadata']['producer']}")
                
                if warning_messages:    
                    print(f"⚠️ PDF warnings for {filename}: {', '.join(warning_messages)}")
                if optimization_notes:
                    print(f"🚀 PDF optimization for {filename}: {', '.join(optimization_notes)}")
                
                # Update progress: starting extraction with optimized strategy
                if validation_result.get("has_page_dimensions", False) and validation_result.get("pages_with_valid_dimensions", 0) == validation_result.get("page_count", 0):
                    self.redis_manager.update_task_progress(
                        task_id, 
                        35, 
                        f"PDF validated (excellent structure), starting optimized extraction for {validation_result['page_count']} pages..."
                    )
                else:
                    self.redis_manager.update_task_progress(
                        task_id, 
                        35, 
                        "PDF validated, starting extraction..."
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
                    # Verify backend configuration before conversion
                    print(f"🔍 Starting Docling conversion for: {filename}")
                    
                    # Get backend info from the configured format options
                    backend_name = 'pypdfium2'  # We know this from __init__
                    try:
                        if hasattr(self.converter, 'format_options') and InputFormat.PDF in self.converter.format_options:
                            pdf_option = self.converter.format_options[InputFormat.PDF]
                            if hasattr(pdf_option, 'pipeline_options') and hasattr(pdf_option.pipeline_options, 'pdf_backend'):
                                backend_name = pdf_option.pipeline_options.pdf_backend
                    except:
                        pass
                    
                    print(f"🔧 Using backend: {backend_name}")
                    
                    # Docling akan mengekstrak text, tables, images, dan metadata
                    result = self.converter.convert(temp_file_path)

                    print(f"✅ Docling conversion successful for: {filename}")
                except Exception as docling_error:
                    error_msg = str(docling_error).lower()
                    
                    # Check if conversion actually succeeded despite page-dimension warnings
                    if "conversionstatus.success" in error_msg or "finished converting" in str(docling_error):
                        print(f"⚠️ Docling completed with warnings (page-dimensions): {filename}")
                        # Continue with result processing despite warnings
                        try:
                            # Try to access result anyway
                            result = self.converter.convert(temp_file_path)

                        except:
                            # If still fails, proceed to backend fallback
                            pass
                    
                    # Handle page-dimensions specific errors
                    if "page-dimensions" in error_msg or "preprocess failed" in error_msg:
                        print(f"⚠️ Docling page-dimensions error detected: {docling_error}")
                        self.redis_manager.update_task_progress(
                            task_id, 
                            45, 
                            "Optimizing for problematic PDF structure..."
                        )
                        
                        # Try with PDF dimension fixing and simpler Docling configuration
                        try:
                            print("🔄 Trying PDF dimension fix and alternative backends...")
                            
                            # First try to fix PDF dimensions
                            fixed_pdf_path = self._fix_pdf_page_dimensions(temp_file_path)
                            
                            # Try conversion with fixed PDF
                            if fixed_pdf_path != temp_file_path:
                                try:
                                    result = self.converter.convert(fixed_pdf_path)
                                    print(f"✅ PDF conversion successful with dimension fix for: {filename}")
                                    # Cleanup fixed PDF
                                    if os.path.exists(fixed_pdf_path):
                                        os.unlink(fixed_pdf_path)
                                except Exception:
                                    # If still fails, try different backends
                                    result, backend_used = self._try_different_backends(fixed_pdf_path)
                                    print(f"✅ PDF conversion successful using {backend_used} backend with fix for: {filename}")
                                    # Cleanup fixed PDF
                                    if os.path.exists(fixed_pdf_path):
                                        os.unlink(fixed_pdf_path)
                            else:
                                # If fixing didn't work, try different backends on original
                                result, backend_used = self._try_different_backends(temp_file_path)
                                print(f"✅ PDF conversion successful using {backend_used} backend for: {filename}")
                                
                        except Exception as backend_error:
                            print(f"❌ All PDF backends failed: {backend_error}")
                            # Fall back to PyMuPDF
                            print("🔄 Falling back to PyMuPDF extraction...")
                            self.redis_manager.update_task_progress(
                                task_id, 
                                50, 
                                "Docling failed, using PyMuPDF fallback..."
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
                                "warning": f"Used PyMuPDF fallback due to all backends failing: {str(docling_error)}"
                            }
                            
                            # Mark task sebagai completed dengan warning
                            self.redis_manager.complete_task(task_id, final_result, success=True)
                            return final_result
                    else:
                        # Other Docling errors
                        print(f"❌ Docling conversion failed with other error: {docling_error}")
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
            full_text = doc.export_to_markdown()
            
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
    
    def _validate_pdf_file(self, file_path: str) -> Dict[str, Any]:
        """
        Validate PDF file and get basic information
        Args:
            file_path: Path to PDF file
        Returns:
            Dictionary with validation results
        """
        try:
            if PYMUPDF_AVAILABLE:
                # Use PyMuPDF for validation
                pdf_doc = fitz.open(file_path)
                
                validation_result = {
                    "is_valid": True,
                    "page_count": pdf_doc.page_count,
                    "is_encrypted": pdf_doc.is_encrypted,
                    "needs_password": pdf_doc.needs_pass,
                    "metadata": pdf_doc.metadata,
                    "has_page_dimensions": True  # Will be checked per page
                }
                
                # Check if pages have valid dimensions
                pages_with_dimensions = 0
                for page_num in range(pdf_doc.page_count):
                    try:
                        page = pdf_doc[page_num]
                        rect = page.rect
                        if rect.width > 0 and rect.height > 0:
                            pages_with_dimensions += 1
                    except Exception:
                        pass
                
                validation_result["pages_with_valid_dimensions"] = pages_with_dimensions
                validation_result["has_page_dimensions"] = pages_with_dimensions > 0
                
                pdf_doc.close()
                return validation_result
            else:
                # Basic validation without PyMuPDF
                with open(file_path, 'rb') as f:
                    header = f.read(10)
                    return {
                        "is_valid": header.startswith(b'%PDF'),
                        "page_count": -1,
                        "is_encrypted": False,
                        "needs_password": False,
                        "metadata": {},
                        "has_page_dimensions": True,  # Assume true
                        "pages_with_valid_dimensions": -1
                    }
                    
        except Exception as e:
            return {
                "is_valid": False,
                "error": str(e),
                "page_count": 0,
                "is_encrypted": False,
                "needs_password": False,
                "metadata": {},
                "has_page_dimensions": False,
                "pages_with_valid_dimensions": 0
            }
    
    def _fix_pdf_page_dimensions(self, pdf_path: str) -> str:
        """
        Try to fix PDF page dimension issues using PyMuPDF preprocessing
        Args:
            pdf_path: Path to problematic PDF
        Returns:
            Path to fixed PDF or original path if fixing failed
        """
        if not PYMUPDF_AVAILABLE:
            return pdf_path
            
        try:
            import tempfile
            
            print("🔧 Attempting to fix PDF page dimensions...")
            
            # Open PDF with PyMuPDF
            pdf_doc = fitz.open(pdf_path)
            
            # Create a new PDF with explicit page dimensions
            fixed_pdf = fitz.open()
            
            for page_num in range(pdf_doc.page_count):
                page = pdf_doc[page_num]
                
                # Get or set default page dimensions
                rect = page.rect
                if rect.width <= 0 or rect.height <= 0:
                    # Set default A4 dimensions if invalid
                    rect = fitz.Rect(0, 0, 595, 842)  # A4 in points
                
                # Create new page with explicit dimensions
                new_page = fixed_pdf.new_page(width=rect.width, height=rect.height)
                
                # Copy content from original page
                new_page.show_pdf_page(rect, pdf_doc, page_num)
            
            # Save fixed PDF
            with tempfile.NamedTemporaryFile(delete=False, suffix='_fixed.pdf') as temp_file:
                fixed_pdf_path = temp_file.name
            
            fixed_pdf.save(fixed_pdf_path)
            fixed_pdf.close()
            pdf_doc.close()
            
            print(f"✅ PDF page dimensions fixed: {fixed_pdf_path}")
            return fixed_pdf_path
            
        except Exception as e:
            print(f"⚠️ Could not fix PDF dimensions: {e}")
            return pdf_path
    
    def _try_different_backends(self, file_path: str) -> tuple[Any, str]:
        """
        Try different PDF backends to find one that works
        Args:
            file_path: Path to PDF file
        Returns:
            Tuple of (conversion_result, backend_used)
        """
        backends_to_try = [
            ('pypdfium2', 'PyPDFium2 - Most reliable for page dimensions'),
            ('dlparse_v1', 'DLParse V1 - Default backend'),
            ('dlparse_v2', 'DLParse V2 - Alternative parser')
        ]
        
        for backend, description in backends_to_try:
            try:
                print(f"🔄 Trying {description}...")
                
                from docling.datamodel.base_models import InputFormat
                from docling.datamodel.pipeline_options import PdfPipelineOptions
                from docling.document_converter import PdfFormatOption
                
                # Create pipeline options with specific backend
                pipeline_options = PdfPipelineOptions(pdf_backend=backend)
                pipeline_options.artifacts_path = None
                pipeline_options.do_ocr = False
                pipeline_options.do_table_structure = True
                
                # Create converter with this backend
                backend_converter = DocumentConverter(
                    format_options={
                        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                    }
                )
                
                # Try conversion
                result = backend_converter.convert(file_path)
                print(f"✅ Successfully converted with {backend}")
                return result, backend
                
            except Exception as e:
                print(f"❌ {backend} failed: {str(e)[:100]}...")
                continue
        
        # If all backends fail, raise the last error
        raise Exception("All PDF backends failed to process this file")