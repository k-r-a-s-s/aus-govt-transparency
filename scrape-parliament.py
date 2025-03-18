import os
import requests
from bs4 import BeautifulSoup
import time
from tqdm import tqdm

# Base URL and target page
BASE_URL = "https://www.aph.gov.au"
PAGE_URL = "https://www.aph.gov.au/Parliamentary_Business/Committees/House_of_Representatives_Committees?url=pmi/declarations.htm"
OUTPUT_DIR = "pdfs"

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

def main():
    try:
        # Fetch the page content
        print("Fetching page content...")
        response = requests.get(PAGE_URL)
        response.raise_for_status()

        # Parse the page
        soup = BeautifulSoup(response.text, "html.parser")

        # Find all PDF links
        pdf_links = []
        for link in soup.find_all("a", href=True):
            if ".pdf" in link["href"].lower() and "?url=pmi/declarations/" in link["href"]:
                # Extract the PDF filename from the URL
                pdf_filename = link["href"].split("/")[-1]
                # Construct the correct URL
                pdf_url = f"{BASE_URL}/Parliamentary_Business/Committees/House_of_Representatives_Committees{link['href']}"
                pdf_links.append((pdf_url, pdf_filename))

        print(f"Found {len(pdf_links)} PDF files to download.")
        
        # Count existing files
        existing_files = 0
        for _, pdf_name in pdf_links:
            if os.path.exists(os.path.join(OUTPUT_DIR, pdf_name)):
                existing_files += 1
        
        if existing_files > 0:
            print(f"{existing_files} files already exist and will be skipped.")

        # Download PDFs with progress bar
        success_count = 0
        failed_count = 0
        skipped_count = 0
        
        for pdf_url, pdf_name in tqdm(pdf_links, desc="Downloading PDFs"):
            pdf_path = os.path.join(OUTPUT_DIR, pdf_name)
            
            # Skip if file already exists
            if os.path.exists(pdf_path):
                skipped_count += 1
                continue
            
            try:
                # Add a small delay to avoid overwhelming the server
                time.sleep(0.5)
                
                pdf_response = requests.get(pdf_url, timeout=30)
                
                # Check if the request was successful
                if pdf_response.status_code == 200:
                    with open(pdf_path, "wb") as f:
                        f.write(pdf_response.content)
                    success_count += 1
                else:
                    print(f"\nFailed to download {pdf_name}: HTTP {pdf_response.status_code}")
                    failed_count += 1
            except Exception as e:
                print(f"\nError downloading {pdf_name}: {str(e)}")
                failed_count += 1

        # Print summary
        print("\nDownload Summary:")
        print(f"  - Successfully downloaded: {success_count}")
        print(f"  - Failed downloads: {failed_count}")
        print(f"  - Skipped (already exist): {skipped_count}")
        print(f"  - Total files processed: {len(pdf_links)}")
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
