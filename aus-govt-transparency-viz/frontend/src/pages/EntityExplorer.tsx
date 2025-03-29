import React, { useState, useEffect } from 'react';
import useNetworkData from '../hooks/useNetworkData';
import useEntityDetails from '../hooks/useEntityDetails';
import MPNetworkGraph from '../components/visualizations/MPNetworkGraph';
import EntityDetail from '../components/visualizations/EntityDetail';
import { NetworkNode } from '../types';

const EntityExplorer: React.FC = () => {
  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedEntity, setSelectedEntity] = useState<string | null>(null);
  const [selectedMP, setSelectedMP] = useState<string | null>(null);
  const [useCanonical, setUseCanonical] = useState(true); // Default to using canonical entities
  
  // Fetch network data
  const { 
    data: networkData = { nodes: [], links: [] }, 
    isLoading: isLoadingNetwork, 
    isError: isErrorNetwork 
  } = useNetworkData({
    entity: selectedEntity || undefined,
    mp: selectedMP || undefined,
    useCanonical
  });
  
  // Fetch entity details when an entity is selected
  const {
    data: entityDetails,
    isLoading: isLoadingEntityDetails
  } = useEntityDetails({
    entityName: selectedEntity || '',
    useCanonical,
    enabled: !!selectedEntity
  });
  
  // Reset selected node when search changes
  useEffect(() => {
    setSelectedEntity(null);
    setSelectedMP(null);
  }, [searchQuery]);
  
  // Filter network data based on search
  const filteredNetworkData = React.useMemo(() => {
    if (!searchQuery || !networkData.nodes.length) return networkData;
    
    // Filter nodes that match the search query
    const matchingNodes = networkData.nodes.filter(node => 
      node.name.toLowerCase().includes(searchQuery.toLowerCase())
    );
    
    // Get matching node IDs for filtering links
    const matchingNodeIds = new Set(matchingNodes.map(node => node.id));
    
    // Filter links that connect to matching nodes
    const matchingLinks = networkData.links.filter(link => 
      matchingNodeIds.has(link.source as string) || 
      matchingNodeIds.has(link.target as string)
    );
    
    // Find all nodes that are connected to the matching nodes
    const connectedNodeIds = new Set<string>();
    matchingLinks.forEach(link => {
      connectedNodeIds.add(link.source as string);
      connectedNodeIds.add(link.target as string);
    });
    
    // Include all nodes that are either matching or connected to matching nodes
    const relevantNodes = networkData.nodes.filter(node => 
      matchingNodeIds.has(node.id) || connectedNodeIds.has(node.id)
    );
    
    return {
      nodes: relevantNodes,
      links: matchingLinks
    };
  }, [networkData, searchQuery]);
  
  // Handle node click
  const handleNodeClick = (node: NetworkNode) => {
    if (node.type === 'mp') {
      setSelectedMP(node.id);
      setSelectedEntity(null);
    } else {
      setSelectedEntity(node.id);
      setSelectedMP(null);
    }
  };
  
  // Get stats for selected node
  const selectedNodeDetails = React.useMemo(() => {
    if (!selectedEntity && !selectedMP) return null;
    
    const nodeId = selectedEntity || selectedMP;
    const node = networkData.nodes.find(n => n.id === nodeId);
    
    if (!node) return null;
    
    // Find all links connected to this node
    const connectedLinks = networkData.links.filter(link => 
      link.source === nodeId || link.target === nodeId
    );
    
    // Get all connected node ids
    const connectedNodeIds = new Set<string>();
    connectedLinks.forEach(link => {
      if (link.source === nodeId) {
        connectedNodeIds.add(link.target as string);
      } else {
        connectedNodeIds.add(link.source as string);
      }
    });
    
    // Get connected nodes
    const connectedNodes = networkData.nodes.filter(n => connectedNodeIds.has(n.id));
    
    return {
      node,
      connections: connectedLinks.length,
      connectedNodes,
      isMP: node.type === 'mp'
    };
  }, [networkData, selectedEntity, selectedMP]);
  
  // Reset selection
  const handleResetSelection = () => {
    setSelectedEntity(null);
    setSelectedMP(null);
  };
  
  return (
    <div className="entity-explorer">
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">Entity Network Explorer</h1>
        <p className="text-gray-600 mb-4">
          Discover connections between MPs and entities through disclosed relationships.
        </p>
        
        {/* Search and Filter Bar */}
        <div className="flex flex-wrap items-center gap-4 mb-4">
          {/* Search Input */}
          <div className="relative flex-grow max-w-lg">
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
          
          {/* Canonical Toggle */}
          <div className="flex items-center">
            <span className="text-sm text-gray-600 mr-2">Use standardized entity names:</span>
            <label className="inline-flex items-center cursor-pointer">
              <input 
                type="checkbox" 
                checked={useCanonical}
                onChange={() => setUseCanonical(!useCanonical)}
                className="sr-only peer"
              />
              <div className="relative w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
          </div>
          
          {/* Selection Pills */}
          {(selectedEntity || selectedMP) && (
            <div className="flex items-center">
              <span className="text-sm text-gray-600 mr-2">Filtered by:</span>
              <div className="flex items-center bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm">
                {selectedEntity ? 'Entity: ' : 'MP: '}
                <span className="font-medium ml-1">{selectedEntity || selectedMP}</span>
                <button 
                  className="ml-2 text-blue-600 hover:text-blue-800" 
                  onClick={handleResetSelection}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                  </svg>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Network Graph (2/3 width on large screens) */}
        <div className={`${selectedEntity ? 'lg:col-span-2' : 'lg:col-span-3'} mb-6`}>
          {isLoadingNetwork ? (
            <div className="flex items-center justify-center bg-gray-50 rounded-lg p-6" style={{ height: 600 }}>
              <p className="text-gray-500">Loading network data...</p>
            </div>
          ) : isErrorNetwork ? (
            <div className="flex items-center justify-center bg-gray-50 rounded-lg p-6" style={{ height: 600 }}>
              <p className="text-red-500">Error loading network data. Please try again.</p>
            </div>
          ) : (
            <MPNetworkGraph 
              data={filteredNetworkData} 
              height={600} 
              onNodeClick={handleNodeClick} 
            />
          )}
        </div>
        
        {/* Entity Details (1/3 width on large screens) */}
        {selectedEntity && (
          <div className="lg:col-span-1">
            <h2 className="text-xl font-bold mb-4">Entity Details</h2>
            <EntityDetail 
              entityDetails={entityDetails || {
                entity: selectedEntity,
                count: 0,
                variants: [],
                connected_mps: []
              }}
              isLoading={isLoadingEntityDetails}
            />
          </div>
        )}
      </div>
      
      {/* Instructions Panel */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-2xl font-bold mb-4">How to Use the Network Graph</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h3 className="text-xl font-semibold mb-2">Interaction Tips</h3>
            <ul className="list-disc pl-5 space-y-2">
              <li>Click and drag nodes to reposition them</li>
              <li>Drag the canvas to pan the view</li>
              <li>Hover over nodes to see entity/MP names</li>
              <li>Click on a node to see detailed connections</li>
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
      
      {/* Statistics Panel */}
      <div className="bg-white p-6 rounded-lg shadow mt-6">
        <h2 className="text-xl font-bold mb-4">Network Statistics</h2>
        
        <div className="space-y-4">
          <div>
            <h3 className="text-lg font-semibold mb-2">Overview</h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-blue-50 p-3 rounded-lg">
                <p className="text-sm text-gray-600">Total MPs</p>
                <p className="text-xl font-bold">
                  {networkData.nodes.filter(n => n.type === 'mp').length}
                </p>
              </div>
              <div className="bg-yellow-50 p-3 rounded-lg">
                <p className="text-sm text-gray-600">Total Entities</p>
                <p className="text-xl font-bold">
                  {networkData.nodes.filter(n => n.type === 'entity').length}
                </p>
              </div>
            </div>
          </div>
          
          <div>
            <h3 className="text-lg font-semibold mb-2">Top Connected</h3>
            
            <div className="space-y-2">
              <p className="text-sm">
                <span className="font-medium">Top MP:</span>{' '}
                {networkData.nodes
                  .filter(n => n.type === 'mp')
                  .sort((a, b) => (b.size || 0) - (a.size || 0))[0]?.name || 'N/A'}
              </p>
              
              <p className="text-sm">
                <span className="font-medium">Top Entity:</span>{' '}
                {networkData.nodes
                  .filter(n => n.type === 'entity')
                  .sort((a, b) => (b.size || 0) - (a.size || 0))[0]?.name || 'N/A'}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default EntityExplorer; 