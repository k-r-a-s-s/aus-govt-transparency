# PDF Processing Pipeline

The PDF processing pipeline is a key component of the Australian Government Transparency Project. It handles the extraction of structured data from parliamentary disclosure PDFs using Google's Gemini 2.0 AI.

## Overview

The pipeline consists of several steps:

1. **PDF Collection**: PDFs are downloaded from parliamentary websites
2. **PDF Processing**: Gemini AI extracts structured data from PDFs
3. **Post-Processing**: Extracted data is cleaned and standardized
4. **Database Storage**: Structured data is stored in the SQLite database

## Key Components

### PDF Collection

The PDF collection is handled by the `scrape_parliament.py` script. This script downloads PDFs from parliamentary websites and organizes them by parliament.

**Key Files:**
- `scrape_parliament.py`: Main scraping script
- `parliament_urls.py`: Configuration file with URLs for different parliaments

**Main Functions:**

```python
def scrape_parliament(parliament: str = "47th", output_dir: str = "pdfs", limit: Optional[int] = None) -> List[str]:
    """
    Scrape parliamentary disclosure PDFs for a specific parliament.
    
    Args:
        parliament: Parliament to scrape (e.g., '47th')
        output_dir: Directory to save PDFs
        limit: Maximum number of PDFs to download
        
    Returns:
        List of downloaded PDF paths
    """
```

```python
def scrape_all_parliaments(output_dir: str = "pdfs", limit: Optional[int] = None) -> Dict[str, List[str]]:
    """
    Scrape parliamentary disclosure PDFs for all parliaments.
    
    Args:
        output_dir: Directory to save PDFs
        limit: Maximum number of PDFs to download per parliament
        
    Returns:
        Dictionary mapping parliaments to lists of downloaded PDF paths
    """
```

### PDF Processing

The PDF processing is handled by the `GeminiPDFProcessor` class in `gemini_pdf_processor.py`. This class uses Google's Gemini 2.0 AI to extract structured data from PDFs.

**Key Files:**
- `gemini_pdf_processor.py`: Main PDF processing module
- `test_gemini_pdf.py`: Script to test PDF processing
- `process_parliament_disclosures.py`: Orchestration script for the complete pipeline

**Main Classes:**

```python
class RateLimiter:
    """
    Rate limiter for API requests.
    
    Attributes:
        requests_per_minute: Maximum requests per minute
        requests_per_day: Maximum requests per day
        request_history: List of request timestamps
    """
```

```python
class GeminiPDFProcessor:
    """
    Process PDFs using Google Gemini AI.
    
    Attributes:
        api_key: Google API key
        model: Gemini model name
        rate_limiter: Rate limiter for API requests
        apply_post_processing: Whether to apply post-processing
    """
```

**Main Methods:**

```python
def process_pdf(self, pdf_path: str, use_file_api: bool = False) -> Dict[str, Any]:
    """
    Process a single PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        use_file_api: Whether to use the Gemini File API
        
    Returns:
        Dictionary with extracted data
    """
```

```python
def process_directory(
    self, 
    pdf_dir: str, 
    output_dir: str = None, 
    limit: Optional[int] = None, 
    continue_on_error: bool = False
) -> List[Dict[str, Any]]:
    """
    Process all PDFs in a directory.
    
    Args:
        pdf_dir: Directory containing PDFs
        output_dir: Directory to save JSON output
        limit: Maximum number of PDFs to process
        continue_on_error: Whether to continue if an error occurs
        
    Returns:
        List of dictionaries with extracted data
    """
```

```python
def post_process_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean and standardize extracted data.
    
    Args:
        data: Dictionary with extracted data
        
    Returns:
        Dictionary with cleaned data
    """
```

### Orchestration

The orchestration of the complete pipeline is handled by the `process_parliament_disclosures.py` script. This script coordinates the PDF collection, processing, and database storage.

**Key Functions:**

```python
def scrape_parliament_pdfs(parliament: Optional[str] = None, all_parliaments: bool = False) -> None:
    """
    Scrape parliamentary disclosure PDFs.
    
    Args:
        parliament: Specific parliament to scrape (e.g., '47th')
        all_parliaments: Whether to scrape all parliaments
    """
```

```python
def process_pdfs(
    parliament: Optional[str] = None,
    all_parliaments: bool = False,
    output_dir: str = "outputs",
    store_in_db: bool = False,
    db_path: str = "disclosures.db",
    limit: Optional[int] = None,
    skip_post_processing: bool = False,
    requests_per_minute: int = 15,
    requests_per_day: int = 1500,
    continue_on_error: bool = False
) -> Dict[str, Any]:
    """
    Process parliamentary disclosure PDFs with Gemini.
    
    Args:
        parliament: Specific parliament to process (e.g., '47th')
        all_parliaments: Whether to process all parliaments
        output_dir: Directory to save the structured data as JSON
        store_in_db: Whether to store the structured data in the database
        db_path: Path to the SQLite database file
        limit: Maximum number of PDFs to process per parliament
        skip_post_processing: Whether to skip post-processing of extracted data
        requests_per_minute: Maximum number of API requests per minute
        requests_per_day: Maximum number of API requests per day
        continue_on_error: Whether to continue processing if an error occurs
        
    Returns:
        Dictionary with processing statistics
    """
```

## Data Extraction Process

The data extraction process works as follows:

1. **PDF Loading**: The PDF file is loaded into memory
2. **Content Extraction**: The PDF content is extracted using Gemini AI
3. **Prompting**: A specific prompt is used to guide the AI in extracting structured data
4. **JSON Parsing**: The AI's response is parsed into a JSON structure
5. **Post-Processing**: The extracted data is cleaned and standardized

### Prompt Template

The following prompt template is used to guide the AI in extracting structured data:

```
You are an expert at extracting structured data from parliamentary disclosure documents.
Please analyze the provided PDF and extract all disclosures of interests.

For each disclosure, please extract the following information:
- MP's name
- Party affiliation
- Electorate
- Category of disclosure (Asset, Liability, Income, Gift, Travel, etc.)
- Description of the item
- Entity associated with the disclosure
- Date of declaration
- Additional details

Format the output as a JSON object with the following structure:
{
  "mp_name": "Full name of the MP",
  "party": "Political party",
  "electorate": "Electoral district",
  "disclosures": [
    {
      "category": "Category of disclosure",
      "item": "Description of the item",
      "entity": "Associated entity or source",
      "declaration_date": "Date in YYYY-MM-DD format",
      "details": "Any additional details"
    },
    ... additional disclosures ...
  ]
}

Be as detailed and accurate as possible. If information is not available, use null or an empty string.
```

### Post-Processing

The post-processing step includes:

1. **Date Standardization**: Convert various date formats to YYYY-MM-DD
2. **Category Normalization**: Map extracted categories to standard categories
3. **Entity Extraction**: Extract and normalize entity names
4. **Nil Entry Detection**: Identify and flag "nil" or "n/a" entries
5. **Confidence Scoring**: Assign confidence scores to extracted data

## Usage Examples

### Process a Single PDF

```python
from gemini_pdf_processor import GeminiPDFProcessor

processor = GeminiPDFProcessor()
result = processor.process_pdf("pdfs/47th/smith_jane.pdf")
print(f"Extracted {len(result['disclosures'])} disclosures")
```

### Process All PDFs for a Parliament

```python
from process_parliament_disclosures import process_pdfs

stats = process_pdfs(
    parliament="47th",
    output_dir="outputs/47th",
    store_in_db=True,
    limit=10
)
print(f"Processed {stats['total_pdfs']} PDFs with {stats['total_disclosures']} disclosures")
```

### Complete Pipeline with Standardization

```bash
python process_parliament_disclosures.py --parliament 47th --store-in-db --standardize
```

## Rate Limiting and Error Handling

The system includes sophisticated rate limiting to ensure you don't exceed Gemini API limits:

### Rate Limiter Class

```python
class RateLimiter:
    def __init__(self, requests_per_minute: int = 15, requests_per_day: int = 1500):
        self.requests_per_minute = requests_per_minute
        self.requests_per_day = requests_per_day
        self.request_history = []
        
    def wait_if_needed(self) -> float:
        """
        Wait if we're approaching rate limits.
        
        Returns:
            Number of seconds waited
        """
```

### Error Handling

The system implements exponential backoff for rate limit errors:

```python
def _handle_rate_limit_error(self, retry_count: int) -> float:
    """
    Handle rate limit error with exponential backoff.
    
    Args:
        retry_count: Number of retries so far
        
    Returns:
        Wait time in seconds
    """
    wait_time = min(2 ** retry_count, 60)
    logger.warning(f"Rate limit exceeded. Waiting {wait_time} seconds before retry...")
    time.sleep(wait_time)
    return wait_time
```

## Performance Considerations

- **Batch Processing**: Process PDFs in batches to maximize throughput
- **PDF Size Optimization**: For large PDFs, consider splitting or optimizing them
- **Conservative Rate Limits**: Use slightly conservative rate limits to provide a safety margin
- **Progress Tracking**: Monitor progress with statistics on successful/failed/rate-limited requests

## Next Steps

- [Data Standardization Workflow](./data_standardization.md)
- [Utility Scripts Documentation](./scripts.md) 