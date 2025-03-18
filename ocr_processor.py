import os
import io
from typing import List, Dict, Any, Optional, Tuple
from google.cloud import vision
from google.cloud import storage
import tempfile
import fitz  # PyMuPDF
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class OCRProcessor:
    """
    A class to handle PDF processing with Google Cloud Vision OCR.
    """
    
    def __init__(self, credentials_path: Optional[str] = None):
        """
        Initialize the OCR processor.
        
        Args:
            credentials_path: Path to the Google Cloud credentials JSON file.
                              If None, will use the GOOGLE_APPLICATION_CREDENTIALS environment variable.
        """
        if credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
            
        self.vision_client = vision.ImageAnnotatorClient()
        
    def process_local_pdf(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        Process a local PDF file using Google Cloud Vision OCR.
        
        Args:
            pdf_path: Path to the local PDF file.
            
        Returns:
            A list of dictionaries containing the extracted text for each page.
        """
        logger.info(f"Processing local PDF: {pdf_path}")
        
        # Extract PDF metadata
        pdf_metadata = self._extract_pdf_metadata(pdf_path)
        
        # Convert PDF to images and process with OCR
        results = []
        
        try:
            pdf_document = fitz.open(pdf_path)
            
            for page_num, page in enumerate(pdf_document):
                logger.info(f"Processing page {page_num + 1} of {len(pdf_document)}")
                
                # Convert page to image
                pix = page.get_pixmap(alpha=False)
                img_bytes = pix.tobytes("png")
                
                # Process image with Vision API
                image = vision.Image(content=img_bytes)
                response = self.vision_client.document_text_detection(image=image)
                
                # Extract text
                text = response.full_text_annotation.text
                
                # Add to results
                results.append({
                    "page_number": page_num + 1,
                    "text": text,
                    "confidence": response.full_text_annotation.pages[0].blocks[0].confidence if response.full_text_annotation.pages else 0.0,
                })
                
            pdf_document.close()
            
        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {str(e)}")
            raise
        
        # Combine metadata with OCR results
        return {
            "metadata": pdf_metadata,
            "pages": results
        }
    
    def _extract_pdf_metadata(self, pdf_path: str) -> Dict[str, Any]:
        """
        Extract metadata from a PDF file.
        
        Args:
            pdf_path: Path to the PDF file.
            
        Returns:
            A dictionary containing the PDF metadata.
        """
        try:
            pdf_document = fitz.open(pdf_path)
            metadata = pdf_document.metadata
            
            # Extract filename without extension
            filename = os.path.basename(pdf_path)
            name_without_ext = os.path.splitext(filename)[0]
            
            # Parse MP name and parliament from filename (e.g., "abbotta_43p.pdf")
            # Format is typically [lastname][firstinitial]_[parliament]p.pdf
            parts = name_without_ext.split('_')
            mp_id = parts[0]
            parliament = parts[1].replace('p', '') if len(parts) > 1 else None
            
            result = {
                "filename": filename,
                "mp_id": mp_id,
                "parliament": parliament,
                "title": metadata.get("title", ""),
                "author": metadata.get("author", ""),
                "subject": metadata.get("subject", ""),
                "keywords": metadata.get("keywords", ""),
                "page_count": len(pdf_document),
            }
            
            pdf_document.close()
            return result
            
        except Exception as e:
            logger.error(f"Error extracting metadata from PDF {pdf_path}: {str(e)}")
            return {
                "filename": os.path.basename(pdf_path),
                "error": str(e)
            }
    
    def batch_process_pdfs(self, pdf_dir: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Process multiple PDF files in a directory.
        
        Args:
            pdf_dir: Directory containing PDF files.
            limit: Maximum number of PDFs to process. If None, process all PDFs.
            
        Returns:
            A list of dictionaries containing the OCR results for each PDF.
        """
        logger.info(f"Batch processing PDFs from directory: {pdf_dir}")
        
        # Get list of PDF files
        pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
        
        if limit:
            pdf_files = pdf_files[:limit]
            
        logger.info(f"Found {len(pdf_files)} PDF files to process")
        
        # Process each PDF
        results = []
        for pdf_file in pdf_files:
            pdf_path = os.path.join(pdf_dir, pdf_file)
            try:
                result = self.process_local_pdf(pdf_path)
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing PDF {pdf_path}: {str(e)}")
                results.append({
                    "filename": pdf_file,
                    "error": str(e)
                })
        
        return results 