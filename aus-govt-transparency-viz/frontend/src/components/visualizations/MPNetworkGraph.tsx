import React, { useEffect, useRef, useState } from 'react';
import { NetworkData } from '../../types';

interface MPNetworkGraphProps {
  data: NetworkData;
  height?: number;
  width?: number;
  onNodeClick?: (nodeId: string) => void;
}

const MPNetworkGraph: React.FC<MPNetworkGraphProps> = ({
  data,
  height = 600,
  width = 800,
  onNodeClick
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isInitialized, setIsInitialized] = useState(false);
  
  // This is a placeholder implementation - in a real app, you would implement
  // this with a graph visualization library like D3.js or vis-network
  useEffect(() => {
    if (!containerRef.current || !data.nodes.length || isInitialized) return;
    
    // Display a message about the network graph
    setIsInitialized(true);
    
    // In a real implementation, you would initialize and render the graph here
    // Example libraries to consider:
    // - D3.js Force Graph: https://d3js.org
    // - vis-network: https://visjs.github.io/vis-network/
    // - react-force-graph: https://github.com/vasturiano/react-force-graph
  }, [data, isInitialized]);
  
  // Empty data check
  if (!data.nodes.length) {
    return (
      <div className="flex items-center justify-center bg-gray-50 rounded-lg p-6" style={{ height }}>
        <p className="text-gray-500">No network data available. Try adjusting your search criteria.</p>
      </div>
    );
  }
  
  return (
    <div className="mp-network-graph">
      {/* Graph Stats */}
      <div className="graph-stats bg-blue-50 p-4 mb-4 rounded-lg">
        <div className="grid grid-cols-3 gap-4">
          <div>
            <p className="text-sm text-gray-600">MPs</p>
            <p className="text-xl font-bold">
              {data.nodes.filter(node => node.type === 'mp').length}
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-600">Entities</p>
            <p className="text-xl font-bold">
              {data.nodes.filter(node => node.type === 'entity').length}
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-600">Connections</p>
            <p className="text-xl font-bold">{data.links.length}</p>
          </div>
        </div>
      </div>
      
      {/* Network Graph Placeholder */}
      <div 
        ref={containerRef}
        className="border-2 border-dashed border-gray-300 rounded-lg flex flex-col items-center justify-center p-6 bg-gray-50"
        style={{ height, width: '100%' }}
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="h-16 w-16 text-gray-400 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
        </svg>
        
        <h3 className="text-lg font-medium text-gray-700 mb-2">Network Graph Visualization</h3>
        
        <p className="text-gray-500 text-center mb-4 max-w-lg">
          This area would display an interactive network graph showing connections between MPs and entities.
          In a production environment, this would be implemented using a graph visualization library.
        </p>
        
        <div className="bg-white rounded-lg p-4 shadow-sm w-full max-w-xl">
          <h4 className="font-medium mb-2">Network Summary</h4>
          
          <div className="text-sm text-gray-600">
            <p className="mb-1">
              <span className="font-medium">Top MP by connections:</span>{' '}
              {data.nodes
                .filter(node => node.type === 'mp')
                .sort((a, b) => (b.size || 0) - (a.size || 0))[0]?.name || 'N/A'}
            </p>
            
            <p className="mb-1">
              <span className="font-medium">Top Entity by connections:</span>{' '}
              {data.nodes
                .filter(node => node.type === 'entity')
                .sort((a, b) => (b.size || 0) - (a.size || 0))[0]?.name || 'N/A'}
            </p>
            
            <p>
              <span className="font-medium">Most common connection type:</span>{' '}
              {(() => {
                const categoryCounts: Record<string, number> = {};
                data.links.forEach(link => {
                  if (link.category) {
                    categoryCounts[link.category] = (categoryCounts[link.category] || 0) + 1;
                  }
                });
                
                return Object.entries(categoryCounts)
                  .sort((a, b) => b[1] - a[1])
                  .map(([category]) => category)[0] || 'N/A';
              })()}
            </p>
          </div>
        </div>
      </div>
      
      {/* Graph Legend */}
      <div className="graph-legend mt-4 bg-white p-4 rounded-lg shadow-sm">
        <h4 className="font-medium mb-2">Legend</h4>
        
        <div className="grid grid-cols-2 gap-4">
          <div className="flex items-center">
            <div className="h-4 w-4 rounded-full bg-blue-500 mr-2"></div>
            <span className="text-sm">MP Node</span>
          </div>
          
          <div className="flex items-center">
            <div className="h-4 w-4 rounded-full bg-green-500 mr-2"></div>
            <span className="text-sm">Entity Node</span>
          </div>
          
          <div className="flex items-center">
            <div className="h-1 w-8 bg-gray-400 mr-2"></div>
            <span className="text-sm">Connection</span>
          </div>
          
          <div className="flex items-center">
            <div className="h-2 w-8 bg-gray-600 mr-2"></div>
            <span className="text-sm">Strong Connection (multiple disclosures)</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MPNetworkGraph; 