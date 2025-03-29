import React, { useEffect, useRef, useState } from 'react';
import { NetworkData, NetworkNode } from '../../types';
import ForceGraph2D from 'react-force-graph-2d';

interface MPNetworkGraphProps {
  data: NetworkData;
  height?: number;
  width?: number;
  onNodeClick?: (node: NetworkNode) => void;
}

const MPNetworkGraph: React.FC<MPNetworkGraphProps> = ({
  data,
  height = 600,
  width = 800,
  onNodeClick
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width, height });
  
  // Apply party colors to nodes
  const getNodeColor = (node: NetworkNode): string => {
    if (node.type === 'entity') return '#FFC107'; // Yellow for entities
    
    // MP colors by party
    switch(node.party?.toLowerCase()) {
      case 'labor': return '#E53935'; // Red
      case 'liberal': return '#1565C0'; // Blue
      case 'greens': return '#43A047'; // Green
      default: return '#757575'; // Grey for others/unknown
    }
  };

  // Update dimensions when container size changes
  useEffect(() => {
    if (!containerRef.current) return;
    
    const updateDimensions = () => {
      if (!containerRef.current) return;
      
      // Use container width but fixed height
      const width = containerRef.current.offsetWidth;
      setDimensions({ width, height });
    };
    
    // Initial update
    updateDimensions();
    
    // Listen for window resize
    window.addEventListener('resize', updateDimensions);
    
    return () => {
      window.removeEventListener('resize', updateDimensions);
    };
  }, [height]);
  
  // Transform data for ForceGraph
  const graphData = {
    nodes: data.nodes.map(node => ({
      ...node,
      // Set node size based on number of connections or default size
      val: node.size || 1
    })),
    links: data.links.map(link => ({
      ...link,
      // ForceGraph expects 'value' instead of 'weight'
      value: link.weight,
      // Add original nodes as source/target for reference
      sourceNode: data.nodes.find(n => n.id === link.source),
      targetNode: data.nodes.find(n => n.id === link.target)
    }))
  };
  
  // Empty data check
  if (!data.nodes.length) {
    return (
      <div className="flex items-center justify-center bg-gray-50 rounded-lg p-6" style={{ height }}>
        <p className="text-gray-500">No network data available. Try adjusting your search criteria.</p>
      </div>
    );
  }
  
  return (
    <div className="mp-network-graph" ref={containerRef}>
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
      
      {/* Network Graph */}
      <div className="border rounded-lg overflow-hidden">
        <ForceGraph2D
          graphData={graphData}
          nodeId="id"
          nodeVal={node => (node as any).val || 1}
          nodeLabel={node => `${(node as NetworkNode).name} (${(node as NetworkNode).type})`}
          nodeColor={node => getNodeColor(node as NetworkNode)}
          linkWidth={link => (link.value as number) * 0.5}
          linkDirectionalParticles={link => (link.value as number)}
          linkDirectionalParticleWidth={1.5}
          backgroundColor="#f8fafc"
          width={dimensions.width}
          height={dimensions.height}
          onNodeClick={node => onNodeClick?.(node as NetworkNode)}
        />
      </div>
      
      {/* Graph Legend */}
      <div className="graph-legend mt-4 bg-white p-4 rounded-lg shadow-sm">
        <h4 className="font-medium mb-2">Legend</h4>
        
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="flex items-center">
            <div className="h-4 w-4 rounded-full bg-[#E53935] mr-2"></div>
            <span className="text-sm">Labor MP</span>
          </div>
          
          <div className="flex items-center">
            <div className="h-4 w-4 rounded-full bg-[#1565C0] mr-2"></div>
            <span className="text-sm">Liberal MP</span>
          </div>
          
          <div className="flex items-center">
            <div className="h-4 w-4 rounded-full bg-[#43A047] mr-2"></div>
            <span className="text-sm">Greens MP</span>
          </div>
          
          <div className="flex items-center">
            <div className="h-4 w-4 rounded-full bg-[#757575] mr-2"></div>
            <span className="text-sm">Other Party MP</span>
          </div>
          
          <div className="flex items-center">
            <div className="h-4 w-4 rounded-full bg-[#FFC107] mr-2"></div>
            <span className="text-sm">Entity</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MPNetworkGraph; 