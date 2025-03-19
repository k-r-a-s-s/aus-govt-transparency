import React from 'react';
import { useDisclosureData } from '../hooks/useDisclosureData';
import GiftAnalysis from '../components/visualizations/GiftAnalysis';

const GiftsAndTravel: React.FC = () => {
  // Fetch disclosure data with gift filter
  const { data: disclosures = [], isLoading } = useDisclosureData({ 
    category: 'Gift',
    limit: 1000
  });
  
  return (
    <div className="gifts-and-travel">
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">Gifts & Travel Analysis</h1>
        <p className="text-gray-600">
          Analyze patterns in gifts and travel benefits received by Members of Parliament.
        </p>
      </div>
      
      {isLoading ? (
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
        </div>
      ) : (
        <>
          {/* Gift Analysis Dashboard */}
          <div className="bg-white p-6 rounded-lg shadow mb-6">
            <GiftAnalysis data={disclosures} />
          </div>
          
          {/* Key Findings */}
          <div className="bg-white p-6 rounded-lg shadow mb-6">
            <h2 className="text-2xl font-bold mb-4">Key Findings</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h3 className="text-xl font-semibold mb-2">Gift Patterns</h3>
                <ul className="list-disc pl-5 space-y-2">
                  <li>Entertainment and event tickets are the most common type of gift received by MPs.</li>
                  <li>Corporate gifts tend to cluster around key legislative periods.</li>
                  <li>There is a seasonal pattern to gift-giving, with peaks during holiday periods.</li>
                </ul>
              </div>
              
              <div>
                <h3 className="text-xl font-semibold mb-2">Travel Insights</h3>
                <ul className="list-disc pl-5 space-y-2">
                  <li>International travel sponsorship is predominantly for conferences and speaking engagements.</li>
                  <li>Study tours make up a significant portion of sponsored travel.</li>
                  <li>Certain industries (technology, defense, energy) are more likely to sponsor MP travel.</li>
                </ul>
              </div>
            </div>
          </div>
          
          {/* Gift Timeline */}
          <div className="bg-white p-6 rounded-lg shadow">
            <h2 className="text-2xl font-bold mb-4">Gift Timeline</h2>
            <p className="text-gray-600 mb-4">
              The timeline below shows when gifts were disclosed by MPs. Note that this reflects the disclosure date,
              which may differ from when gifts were actually received.
            </p>
            
            <div className="h-96 flex items-center justify-center text-gray-500">
              <div className="text-center">
                <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                <h3 className="mt-2 text-sm font-medium text-gray-900">Timeline visualization</h3>
                <p className="mt-1 text-sm text-gray-500">Coming soon in a future update</p>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default GiftsAndTravel; 