import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import DisclosureTimeline from '../components/visualizations/DisclosureTimeline';
import FilterableDisclosureTable from '../components/visualizations/FilterableDisclosureTable';
import { fetchMPDetails } from '../services/api';
import PDFViewer from '../components/common/PDFViewer';
import SimplePDFViewer from '../components/common/SimplePDFViewer';
import DisclosuresByCategory from '../components/visualizations/DisclosuresByCategory';
import AssetsByCategory from '../components/visualizations/AssetsByCategory';

const MPProfile: React.FC = () => {
  // Get MP name from URL params
  const { name } = useParams<{ name: string }>();
  const decodedName = name ? decodeURIComponent(name) : '';
  
  // Fetch MP details
  const { data, isLoading, error } = useQuery({
    queryKey: ['mp-details', decodedName],
    queryFn: () => fetchMPDetails(decodedName),
    enabled: !!decodedName,
  });
  
  // Extract MP and disclosure data
  const mp = data;
  const disclosures = data?.disclosures || [];
  
  // Calculate statistics
  const categoryStats = React.useMemo(() => {
    if (!disclosures.length) return {};
    
    return disclosures.reduce((acc, disclosure) => {
      const category = disclosure.category;
      acc[category] = (acc[category] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);
  }, [disclosures]);
  
  const [selectedPdfUrl, setSelectedPdfUrl] = useState<string | null>(null);
  const [isPdfModalOpen, setIsPdfModalOpen] = useState(false);
  const [useSimpleViewer, setUseSimpleViewer] = useState(false);
  
  const handleOpenPdf = (pdfUrl: string) => {
    setSelectedPdfUrl(`${import.meta.env.VITE_API_URL}/pdf/${pdfUrl}`);
    setIsPdfModalOpen(true);
  };

  const handleClosePdf = () => {
    setIsPdfModalOpen(false);
    // Clear the URL after a short delay to allow the modal to close gracefully
    setTimeout(() => {
      setSelectedPdfUrl(null);
      setUseSimpleViewer(false);
    }, 300);
  };
  
  const handleViewerError = () => {
    console.log('Switching to simple PDF viewer due to error');
    setUseSimpleViewer(true);
  };
  
  // Handle loading state
  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }
  
  // Handle error state
  if (error || !mp) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-800 p-4 rounded-md">
        <h3 className="text-lg font-semibold">Error Loading MP Profile</h3>
        <p>{error instanceof Error ? error.message : 'MP not found'}</p>
      </div>
    );
  }
  
  return (
    <div className="container mx-auto px-4 py-8">
      {/* Page Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-800">Member of Parliament Profile</h1>
        <p className="text-gray-600 mt-2">
          View detailed information about financial disclosures made by this MP, including assets, gifts, travel, and other interests.
        </p>
      </div>
      
      {/* MP Header */}
      <div className="bg-white shadow rounded-lg p-6 mb-6">
        <div className="flex flex-col md:flex-row md:items-center">
          <div className="mb-4 md:mb-0 md:mr-6">
            <div className="bg-gray-200 h-24 w-24 rounded-full flex items-center justify-center text-gray-600">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zm-4 7a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
            </div>
          </div>
          
          <div>
            <h1 className="text-3xl font-bold">{mp.mp_name}</h1>
            <div className="flex flex-col sm:flex-row sm:space-x-4">
              <p className="text-gray-600">
                <span className="font-semibold">Party:</span> {mp.party || 'Not specified'}
              </p>
              <p className="text-gray-600">
                <span className="font-semibold">Electorate:</span> {mp.electorate || 'Not specified'}
              </p>
            </div>
          </div>
        </div>
      </div>
      
      {/* MP Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-white p-4 rounded-lg shadow">
          <h3 className="text-lg font-semibold mb-2">Total Disclosures</h3>
          <p className="text-3xl font-bold text-blue-600">{disclosures.length}</p>
        </div>
        
        <div className="bg-white p-4 rounded-lg shadow">
          <h3 className="text-lg font-semibold mb-2">Latest Disclosure</h3>
          <p className="text-3xl font-bold text-green-600">
            {disclosures.length > 0 
              ? new Date(disclosures[0].declaration_date).toLocaleDateString() 
              : 'N/A'}
          </p>
        </div>
        
        <div className="bg-white p-4 rounded-lg shadow">
          <h3 className="text-lg font-semibold mb-2">Most Common Category</h3>
          <p className="text-3xl font-bold text-amber-600">
            {Object.keys(categoryStats).length > 0 
              ? Object.entries(categoryStats).sort((a, b) => b[1] - a[1])[0][0]
              : 'N/A'}
          </p>
        </div>
      </div>
      
      {/* PDF Viewer Modal */}
      {selectedPdfUrl && !useSimpleViewer && (
        <PDFViewer 
          url={selectedPdfUrl} 
          isOpen={isPdfModalOpen} 
          onClose={handleClosePdf}
          filename={selectedPdfUrl.split('/').pop() || 'Document'}
          onError={() => setUseSimpleViewer(true)}
        />
      )}
      
      {/* Fallback Simple PDF Viewer */}
      {selectedPdfUrl && useSimpleViewer && (
        <SimplePDFViewer
          url={selectedPdfUrl} 
          isOpen={isPdfModalOpen} 
          onClose={handleClosePdf}
          filename={selectedPdfUrl.split('/').pop() || 'Document'}
        />
      )}
      
      {/* PDF Documents Section */}
      <div className="bg-white p-6 rounded-lg shadow mb-6">
        <h2 className="text-2xl font-bold mb-4">Source Documents</h2>
        <p className="text-gray-600 mb-4">
          View the original parliamentary disclosure documents for {mp.mp_name}.
        </p>
        
        {/* Extract unique PDF URLs */}
        {(() => {
          const uniquePdfUrls = new Set<string>();
          disclosures.forEach(disclosure => {
            if (disclosure.pdf_url) {
              uniquePdfUrls.add(disclosure.pdf_url);
            }
          });
          
          return uniquePdfUrls.size > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {Array.from(uniquePdfUrls).map((pdfUrl) => {
                // Extract parliament number from PDF URL if possible
                const parliamentMatch = pdfUrl.match(/(\d+)p/);
                const parliament = parliamentMatch ? `${parliamentMatch[1]}th Parliament` : '';
                
                return (
                  <div key={pdfUrl} className="border border-gray-200 rounded-lg p-4 flex flex-col">
                    <div className="flex-grow">
                      <h3 className="font-semibold text-gray-700">{pdfUrl}</h3>
                      {parliament && <p className="text-sm text-gray-500">{parliament}</p>}
                    </div>
                    <div className="mt-3 space-y-2">
                      <button 
                        onClick={() => { setUseSimpleViewer(false); handleOpenPdf(pdfUrl); }} 
                        className="w-full bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md inline-flex items-center justify-center"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                        </svg>
                        View PDF
                      </button>
                      <div className="flex space-x-2">
                        <button
                          onClick={() => { setUseSimpleViewer(true); handleOpenPdf(pdfUrl); }}
                          className="flex-1 text-sm bg-gray-100 hover:bg-gray-200 text-gray-800 px-2 py-1 rounded"
                        >
                          Simple View
                        </button>
                        <a
                          href={`${import.meta.env.VITE_API_URL}/pdf/${pdfUrl}`}
                          download
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="flex-1 text-sm bg-gray-100 hover:bg-gray-200 text-gray-800 px-2 py-1 rounded text-center"
                        >
                          Download
                        </a>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-gray-600">No PDF documents available.</p>
          );
        })()}
      </div>
      
      {/* Disclosure Timeline */}
      <div className="bg-white p-6 rounded-lg shadow mb-6">
        <DisclosureTimeline data={disclosures} mpName={mp.mp_name} />
      </div>
      
      {/* Filterable Disclosure Table */}
      <div className="bg-white p-6 rounded-lg shadow">
        {disclosures.length === 0 ? (
          <p className="text-gray-500">No disclosures found for this MP.</p>
        ) : (
          <FilterableDisclosureTable data={disclosures} mpName={mp.mp_name} />
        )}
      </div>
    </div>
  );
};

export default MPProfile; 