import React, { useState, useEffect } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/esm/Page/AnnotationLayer.css';
import 'react-pdf/dist/esm/Page/TextLayer.css';
import { findValidWorkerUrl } from './pdfWorkerCheck';

// Set initial worker source to a safe default
// This will be updated dynamically once we find a valid CDN
pdfjs.GlobalWorkerOptions.workerSrc = pdfjs.version 
  ? `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`
  : 'https://unpkg.com/pdfjs-dist/build/pdf.worker.min.js';

interface PDFViewerProps {
  url: string;
  isOpen: boolean;
  onClose: () => void;
  filename?: string;
  onError?: () => void;
}

const PDFViewer: React.FC<PDFViewerProps> = ({ url, isOpen, onClose, filename, onError }) => {
  const [numPages, setNumPages] = useState<number | null>(null);
  const [pageNumber, setPageNumber] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);
  const [workerLoaded, setWorkerLoaded] = useState<boolean>(false);

  // Check and update worker URL on component mount
  useEffect(() => {
    const initializeWorker = async () => {
      try {
        // Try to find a valid worker URL from our list of CDNs
        const validWorkerUrl = await findValidWorkerUrl();
        
        if (validWorkerUrl) {
          pdfjs.GlobalWorkerOptions.workerSrc = validWorkerUrl;
          console.log('Successfully set worker URL to:', validWorkerUrl);
          setWorkerLoaded(true);
        } else {
          // If no CDN works, try using a local fallback
          console.warn('All CDN worker URLs failed, trying to initialize fake worker');
          
          // Force using built-in worker as last resort
          try {
            // @ts-ignore - this is an internal method but it's our last resort
            await pdfjs.initFakeWorker();
            console.log('Successfully initialized fake worker');
            setWorkerLoaded(true);
          } catch (fakeWorkerError) {
            console.error('Failed to initialize fake worker:', fakeWorkerError);
            setError(new Error('Could not load PDF.js worker from any source'));
            if (onError) onError();
          }
        }
      } catch (workerError) {
        console.error('Error in worker initialization:', workerError);
        setError(new Error('Failed to initialize PDF viewer worker'));
        if (onError) onError();
      }
    };
    
    initializeWorker();
  }, [onError]);

  const onDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
    setPageNumber(1);
    setLoading(false);
  };

  const onDocumentLoadError = (error: Error) => {
    console.error('Error loading PDF:', error);
    setError(error);
    setLoading(false);
    if (onError) onError();
  };

  if (!isOpen) return null;

  const goToPreviousPage = () => {
    setPageNumber(prevPageNumber => Math.max(prevPageNumber - 1, 1));
  };

  const goToNextPage = () => {
    if (numPages) {
      setPageNumber(prevPageNumber => Math.min(prevPageNumber + 1, numPages));
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black bg-opacity-50 flex items-center justify-center p-4">
      <div className="relative bg-white rounded-lg shadow-xl max-w-5xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <h3 className="text-xl font-semibold text-gray-900 truncate">
            {filename || 'PDF Document'}
          </h3>
          <button
            type="button"
            className="text-gray-400 bg-transparent hover:bg-gray-200 hover:text-gray-900 rounded-lg text-sm p-1.5 ml-auto inline-flex items-center"
            onClick={onClose}
            aria-label="Close"
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd"></path>
            </svg>
          </button>
        </div>

        {/* PDF Content */}
        <div className="flex-grow overflow-auto p-4 flex flex-col items-center">
          {loading && (
            <div className="flex items-center justify-center h-full w-full">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-700"></div>
            </div>
          )}

          {error && (
            <div className="text-red-500 text-center p-4">
              <p>Error loading PDF: {error.message}</p>
              <p className="mt-2">
                <a 
                  href={url} 
                  download 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md inline-flex items-center mt-2"
                >
                  Download PDF Instead
                </a>
              </p>
            </div>
          )}

          {workerLoaded && !error && (
            <Document
              file={url}
              onLoadSuccess={onDocumentLoadSuccess}
              onLoadError={onDocumentLoadError}
              loading={<div className="text-center mt-8">Loading PDF...</div>}
              error={<div className="text-red-500 text-center mt-8">Failed to load PDF</div>}
              options={{
                cMapUrl: 'https://unpkg.com/pdfjs-dist@3.11.174/cmaps/',
                cMapPacked: true,
                standardFontDataUrl: 'https://unpkg.com/pdfjs-dist@3.11.174/standard_fonts/'
              }}
            >
              {numPages && (
                <Page
                  pageNumber={pageNumber}
                  renderTextLayer={true}
                  renderAnnotationLayer={true}
                  width={Math.min(window.innerWidth * 0.8, 800)}
                  loading={<div className="text-center">Loading page...</div>}
                  error={<div className="text-red-500 text-center">Failed to load page</div>}
                />
              )}
            </Document>
          )}
        </div>

        {/* Controls */}
        <div className="border-t p-4 flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <button
              onClick={goToPreviousPage}
              disabled={pageNumber <= 1 || !numPages}
              className={`px-3 py-1 rounded ${pageNumber <= 1 || !numPages ? 'bg-gray-200 text-gray-500 cursor-not-allowed' : 'bg-blue-600 text-white hover:bg-blue-700'}`}
            >
              Previous
            </button>
            <button
              onClick={goToNextPage}
              disabled={!numPages || pageNumber >= numPages}
              className={`px-3 py-1 rounded ${!numPages || pageNumber >= numPages ? 'bg-gray-200 text-gray-500 cursor-not-allowed' : 'bg-blue-600 text-white hover:bg-blue-700'}`}
            >
              Next
            </button>
          </div>
          <div className="text-sm text-gray-700">
            Page {pageNumber} of {numPages || '--'}
          </div>
          <a
            href={url}
            download
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-1 bg-green-600 text-white rounded hover:bg-green-700 flex items-center"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Download
          </a>
        </div>
      </div>
    </div>
  );
};

export default PDFViewer; 