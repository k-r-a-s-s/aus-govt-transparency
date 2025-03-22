import React from 'react';

interface SimplePDFViewerProps {
  url: string;
  isOpen: boolean;
  onClose: () => void;
  filename?: string;
}

/**
 * A simpler PDF viewer that uses an iframe to display PDFs directly.
 * This can be used as a fallback if the more advanced PDF.js viewer has issues.
 */
const SimplePDFViewer: React.FC<SimplePDFViewerProps> = ({ url, isOpen, onClose, filename }) => {
  if (!isOpen) return null;

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

        {/* PDF Content - Using iframe for simplicity */}
        <div className="flex-grow h-[70vh] relative">
          <iframe 
            src={url} 
            title={filename || "PDF Viewer"} 
            className="w-full h-full border-0"
            sandbox="allow-scripts allow-same-origin"
          />
        </div>

        {/* Controls */}
        <div className="border-t p-4 flex items-center justify-between">
          <div className="text-sm text-gray-700">
            <span className="italic">
              Using simple viewer - some PDF features may be limited
            </span>
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

export default SimplePDFViewer; 