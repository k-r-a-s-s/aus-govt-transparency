import { PDFDocumentProxy } from 'react-pdf';

declare module 'react-pdf' {
  namespace pdfjs {
    // Add missing internal methods that might be useful in fallback scenarios
    function initFakeWorker(): Promise<void>;
    
    // Expose the version for debugging
    const version: string;
    
    // Define the GlobalWorkerOptions
    namespace GlobalWorkerOptions {
      let workerSrc: string;
    }
  }
  
  // Extend document load params for better typing
  interface DocumentLoadingParams {
    numPages: number;
    fingerprint?: string;
    pdf?: PDFDocumentProxy;
  }
}

// Ensure this is treated as a module
export {}; 