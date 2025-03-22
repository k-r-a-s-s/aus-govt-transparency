import { pdfjs } from 'react-pdf';

// Define multiple CDN sources for better reliability
const workerUrls = [
  `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`,
  `https://cdn.jsdelivr.net/npm/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`,
  `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.js`
];

// Function to check if a PDF.js worker URL is valid
export const checkPdfWorkerUrl = async (url: string = workerUrls[0]): Promise<boolean> => {
  try {
    console.log('Checking PDF.js worker URL:', url);
    
    const response = await fetch(url, { 
      method: 'HEAD',
      cache: 'no-cache',
      headers: {
        'Cache-Control': 'no-cache'
      }
    });
    
    const isValid = response.ok;
    console.log('PDF.js worker URL is valid:', isValid);
    return isValid;
  } catch (error) {
    console.error('Error checking PDF.js worker URL:', error);
    return false;
  }
};

// Find a valid worker URL from our list of CDNs
export const findValidWorkerUrl = async (): Promise<string | null> => {
  for (const url of workerUrls) {
    const isValid = await checkPdfWorkerUrl(url);
    if (isValid) {
      console.log('Found valid worker URL:', url);
      return url;
    }
  }
  return null;
};

// Export the current worker URL for debugging
export const currentWorkerUrl = pdfjs.GlobalWorkerOptions.workerSrc; 