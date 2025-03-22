# LLM Guidance: Using Gemini 2.0 Flash

This document provides guidance for using Google's Gemini 2.0 Flash model within the Australian Government Transparency Project. Following these guidelines ensures consistent LLM usage across the codebase and maximizes extraction accuracy.

## Model Choice

**Always use Gemini 2.0 Flash** for all LLM-related tasks in this project:

```python
MODEL_NAME = "models/gemini-2.0-flash-001"
```

When using the latest Google AI Python SDK:

```python
MODEL_NAME = "gemini-2.0-flash"
```

This model is preferred for the following reasons:
- Excellent performance on structured data extraction from PDFs
- Superior handling of multi-page document understanding
- High accuracy on named entity recognition
- Good balance of speed and cost for processing many documents
- Generous free tier limits

## API Configuration

### Setting Up the API Client

Using the older Google GenerativeAI Python library:

```python
import os
import google.generativeai as genai

# Configure the API with your API key
API_KEY = os.environ.get("GOOGLE_API_KEY")
genai.configure(api_key=API_KEY)

# Initialize the model
model = genai.GenerativeModel(MODEL_NAME)
```

Using the newer Google AI Python SDK:

```python
from google import genai

# Configure the API with your API key
client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

# Use the model directly
response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=["Extract structured data from this PDF document"]
)
```

### Rate Limiting

Always implement rate limiting to stay within the free tier limits:

```python
from utils.rate_limiter import RateLimiter

# Initialize rate limiter with Gemini 2.0 Flash free tier limits
rate_limiter = RateLimiter(
    requests_per_minute=15,  # Default free tier RPM
    requests_per_day=1500    # Default free tier RPD
)

# Wait if needed before making a request
rate_limiter.wait_if_needed()

# Call the API
response = model.generate_content(...)
```

## Example Usage Patterns

### Basic Text Generation

For simple text prompts:

```python
from google import genai

client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=["Extract all financial disclosures from this document."]
)
print(response.text)
```

### Processing PDFs

For PDF processing with the latest Google AI SDK:

```python
from google import genai
import base64

client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

# Read the PDF file
with open("path/to/disclosure.pdf", "rb") as f:
    pdf_bytes = f.read()

# Encode the PDF as base64
pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

# Create file part
file_part = {
    "mime_type": "application/pdf",
    "data": pdf_base64
}

# Process with appropriate prompt
response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=[
        "Extract structured data from this parliamentary disclosure document in JSON format.",
        file_part
    ]
)
print(response.text)
```

### Streaming Responses

For faster interactions with large responses:

```python
from google import genai

client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

response = client.models.generate_content_stream(
    model="gemini-2.0-flash",
    contents=["Extract and explain all financial disclosures in this document"]
)

# Process the streaming response
for chunk in response:
    print(chunk.text, end="")
```

### Multi-turn Conversations

For complex extraction tasks that may require follow-up questions:

```python
from google import genai

client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
chat = client.chats.create(model="gemini-2.0-flash")

# Initial extraction
response = chat.send_message("Here's a parliamentary disclosure document. Extract all asset disclosures.")
print(response.text)

# Follow-up question
response = chat.send_message("Now categorize these assets by type (real estate, shares, etc.)")
print(response.text)

# Get the full conversation history if needed
for message in chat.get_history():
    print(f'role - {message.role}', end=": ")
    print(message.parts[0].text)
```

### Setting Configuration Parameters

Configure model parameters for optimal extraction:

```python
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=["Extract structured JSON data from this parliamentary disclosure"],
    config=types.GenerateContentConfig(
        max_output_tokens=1024,  # Allow longer responses for complete extraction
        temperature=0.1,         # Lower temperature for more deterministic output
        top_p=0.95,              # Default value
        top_k=40                 # Default value
    )
)
print(response.text)
```

### Using System Instructions

Guide the model's behavior with system instructions:

```python
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

response = client.models.generate_content(
    model="gemini-2.0-flash",
    config=types.GenerateContentConfig(
        system_instruction="""You are an expert at extracting structured data from 
        parliamentary financial disclosure documents. Always output in valid JSON format.
        Be thorough and extract all relevant details about assets, liabilities, income,
        gifts, and other disclosures. Format dates as YYYY-MM-DD."""),
    contents=["Process this MP's disclosure document"]
)

print(response.text)
```

## PDF Processing Guidelines

### Direct PDF Processing

For PDF processing, use the `GeminiPDFProcessor` class which is already configured to use Gemini 2.0 Flash:

```python
from gemini_pdf_processor import GeminiPDFProcessor

processor = GeminiPDFProcessor(
    api_key=API_KEY,
    model="models/gemini-2.0-flash-001"  # Always specify Gemini 2.0 Flash
)

result = processor.process_pdf("path/to/pdf.pdf")
```

### Prompt Engineering

When creating prompts for PDF processing, follow these guidelines:

1. **Be explicit about the task**: Clearly state that the task is to extract structured data from parliamentary disclosure documents
2. **Specify the output format**: Always include a JSON schema in the prompt
3. **Include examples**: Where possible, include examples of expected output
4. **Set clear expectations**: Use language like "Extract all disclosures" rather than "Try to extract..."

### Sample Prompt Template

```python
PROMPT_TEMPLATE = """
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
"""
```

## Recategorization Guidelines

When using Gemini 2.0 Flash for recategorization tasks:

```python
def recategorize_with_llm(entries, model="models/gemini-2.0-flash-001"):
    """Recategorize entries using Gemini 2.0 Flash."""
    # Initialize the model
    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
    model = genai.GenerativeModel(model)
    
    # Create prompt for batch recategorization
    prompt = create_recategorization_prompt(entries)
    
    # Process with rate limiting
    rate_limiter.wait_if_needed()
    response = model.generate_content(prompt)
    
    # Parse and return results
    return parse_recategorization_response(response.text)
```

## Error Handling

Always implement proper error handling for LLM interactions:

```python
def safe_generate_content(model, prompt, retry_count=0, max_retries=3):
    """Generate content with error handling and retries."""
    try:
        rate_limiter.wait_if_needed()
        response = model.generate_content(prompt)
        return response
    except Exception as e:
        if "RESOURCE_EXHAUSTED" in str(e) and retry_count < max_retries:
            # Implement exponential backoff for rate limit errors
            wait_time = min(2 ** retry_count, 60)
            logging.warning(f"Rate limit error. Waiting {wait_time}s before retry...")
            time.sleep(wait_time)
            return safe_generate_content(model, prompt, retry_count + 1, max_retries)
        else:
            logging.error(f"Error generating content: {str(e)}")
            raise
```

## Model Output Processing

### JSON Parsing

Always implement robust JSON parsing with error handling:

```python
def parse_json_response(response_text):
    """Parse JSON from LLM response with error handling."""
    try:
        # Look for JSON pattern between triple backticks or directly in the text
        import re
        import json
        
        # First, try to find JSON inside triple backticks
        json_match = re.search(r"```json\s*([\s\S]*?)\s*```", response_text)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find JSON directly in the text
            json_match = re.search(r"(\{[\s\S]*\})", response_text)
            if json_match:
                json_str = json_match.group(1)
            else:
                raise ValueError("No JSON found in the response")
                
        # Parse the JSON
        parsed_data = json.loads(json_str)
        return parsed_data
    except Exception as e:
        logging.error(f"Error parsing JSON response: {str(e)}")
        logging.debug(f"Raw response: {response_text}")
        return None
```

## Performance Optimization

### Batch Processing

For processing multiple items, consider batch processing to reduce API calls:

```python
def batch_process_items(items, batch_size=5):
    """Process items in batches to reduce API calls."""
    results = []
    
    for i in range(0, len(items), batch_size):
        batch = items[i:i+batch_size]
        
        # Create a batch prompt
        batch_prompt = "Process the following items:\n\n"
        for idx, item in enumerate(batch):
            batch_prompt += f"Item {idx+1}: {item}\n"
        
        # Process the batch
        rate_limiter.wait_if_needed()
        response = model.generate_content(batch_prompt)
        
        # Parse the results
        batch_results = parse_batch_results(response.text, batch)
        results.extend(batch_results)
    
    return results
```

## File API Guidelines

For PDFs larger than 4MB, use the Gemini File API:

```python
def process_large_pdf(pdf_path):
    """Process a large PDF using the Gemini File API."""
    import base64
    
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    
    # Encode the PDF file as base64
    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
    
    # Create the prompt
    prompt = PROMPT_TEMPLATE
    
    # Create the file part
    file_part = {
        "mime_type": "application/pdf",
        "data": pdf_base64
    }
    
    # Process with rate limiting
    rate_limiter.wait_if_needed()
    response = model.generate_content([prompt, file_part])
    
    return parse_json_response(response.text)
```

## Next Steps

- [PDF Processing Pipeline](./pdf_processing.md)
- [Data Standardization Workflow](./data_standardization.md) 