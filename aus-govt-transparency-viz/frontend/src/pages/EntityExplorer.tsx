import React, { useState, useMemo } from 'react';
import { useDisclosureData } from '../hooks/useDisclosureData';
import { transformToNetworkData } from '../utils/dataTransformers';
import MPNetworkGraph from '../components/visualizations/MPNetworkGraph';

const EntityExplorer: React.FC = () => {
  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  
  // Fetch disclosure data
  const { data: disclosures = [], isLoading } = useDisclosureData({ limit: 500 });
  
  // Filter disclosures based on search
  const filteredDisclosures = useMemo(() => {
    if (!searchQuery || !disclosures?.length) return disclosures || [];
    
    return disclosures.filter(d => 
      d.entity?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      d.mp_name?.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [disclosures, searchQuery]);
  
  // Transform to network data
  const networkData = useMemo(() => {
    return transformToNetworkData(filteredDisclosures || []);
  }, [filteredDisclosures]);
  
  return (
    <div className="entity-explorer">
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">Entity Network Explorer</h1>
        <p className="text-gray-600 mb-4">
          Discover connections between MPs and entities through disclosed relationships.
        </p>
        
        {/* Search Bar */}
        <div className="relative max-w-lg">
          <input
            type="text"
            placeholder="Search for MP or Entity..."
            className="w-full px-4 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button
              className="absolute right-2 top-1/2 transform -translate-y-1/2 text-gray-500 hover:text-gray-700"
              onClick={() => setSearchQuery('')}
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            </button>
          )}
        </div>
      </div>
      
      {isLoading ? (
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
        </div>
      ) : (
        <>
          {/* Network Graph */}
          <div className="bg-white p-6 rounded-lg shadow mb-6">
            <h2 className="text-2xl font-bold mb-4">MP-Entity Network</h2>
            <p className="text-gray-600 mb-4">
              This network graph shows connections between MPs and entities they have relationships with.
              Nodes represent MPs (colored by party) and entities. Edges represent disclosure relationships.
            </p>
            
            <div className="border rounded-md overflow-hidden">
              {networkData.nodes.length > 0 ? (
                <div className="h-[600px]">
                  <MPNetworkGraph data={networkData} width={1000} height={600} />
                </div>
              ) : (
                <div className="h-96 flex items-center justify-center text-gray-500">
                  <div className="text-center p-6">
                    <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <h3 className="mt-2 text-sm font-medium text-gray-900">No results found</h3>
                    <p className="mt-1 text-sm text-gray-500">Try adjusting your search query</p>
                  </div>
                </div>
              )}
            </div>
          </div>
          
          {/* Legend and Help */}
          <div className="bg-white p-6 rounded-lg shadow">
            <h2 className="text-2xl font-bold mb-4">How to Use the Network Graph</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h3 className="text-xl font-semibold mb-2">Interaction Tips</h3>
                <ul className="list-disc pl-5 space-y-2">
                  <li>Click and drag nodes to reposition them</li>
                  <li>Drag the canvas to pan the view</li>
                  <li>Hover over nodes to see entity/MP names</li>
                  <li>Use the search bar to filter connections</li>
                </ul>
              </div>
              
              <div>
                <h3 className="text-xl font-semibold mb-2">Graph Legend</h3>
                <ul className="list-disc pl-5 space-y-2">
                  <li><span className="inline-block w-3 h-3 rounded-full bg-[#E53935] mr-2"></span> Labor MP</li>
                  <li><span className="inline-block w-3 h-3 rounded-full bg-[#1565C0] mr-2"></span> Liberal MP</li>
                  <li><span className="inline-block w-3 h-3 rounded-full bg-[#43A047] mr-2"></span> Greens MP</li>
                  <li><span className="inline-block w-3 h-3 rounded-full bg-[#757575] mr-2"></span> Other Party MP</li>
                  <li><span className="inline-block w-3 h-3 rounded-full bg-[#FFC107] mr-2"></span> Entity/Organization</li>
                </ul>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default EntityExplorer; 