import React from 'react';
import { EntityDetails } from '../../services/api';
import { Link } from 'react-router-dom';

interface EntityDetailProps {
  entityDetails: EntityDetails;
  isLoading: boolean;
}

const EntityDetail: React.FC<EntityDetailProps> = ({ entityDetails, isLoading }) => {
  if (isLoading) {
    return (
      <div className="p-4 border rounded-lg bg-white animate-pulse">
        <div className="h-6 bg-gray-200 rounded w-3/4 mb-4"></div>
        <div className="h-4 bg-gray-200 rounded w-1/2 mb-2"></div>
        <div className="h-4 bg-gray-200 rounded w-1/3 mb-4"></div>
        <div className="h-20 bg-gray-200 rounded w-full"></div>
      </div>
    );
  }

  if (!entityDetails) {
    return null;
  }

  return (
    <div className="p-4 border rounded-lg bg-white">
      <h3 className="text-xl font-semibold mb-2">{entityDetails.entity}</h3>
      <p className="text-gray-600 mb-4">
        Mentioned {entityDetails.count} {entityDetails.count === 1 ? 'time' : 'times'} in disclosures
      </p>
      
      {entityDetails.variants.length > 0 && (
        <div className="mb-4">
          <h4 className="font-medium text-gray-700 mb-2">Also known as:</h4>
          <div className="flex flex-wrap gap-2">
            {entityDetails.variants.map((variant) => (
              <span 
                key={variant}
                className="px-2 py-1 bg-blue-50 text-blue-700 rounded-md text-sm"
              >
                {variant}
              </span>
            ))}
          </div>
        </div>
      )}
      
      <div className="mt-6">
        <h4 className="font-medium text-gray-700 mb-2">Connected MPs ({entityDetails.connected_mps.length})</h4>
        {entityDetails.connected_mps.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {entityDetails.connected_mps.map((mp) => (
              <div 
                key={mp.mp_name} 
                className="flex items-center p-2 border rounded-md hover:bg-gray-50"
              >
                <div className="flex-grow">
                  <Link to={`/mp/${encodeURIComponent(mp.mp_name)}`} className="text-blue-600 hover:underline">
                    {mp.mp_name}
                  </Link>
                  <div className="text-sm text-gray-500">{mp.party}</div>
                  <div className="text-xs text-gray-400">{mp.electorate}</div>
                </div>
                <div className="flex-shrink-0">
                  <span className={`px-2 py-1 rounded-full text-xs ${
                    mp.political_bloc === 'Labor' ? 'bg-red-100 text-red-800' :
                    mp.political_bloc === 'Coalition' ? 'bg-blue-100 text-blue-800' :
                    mp.political_bloc === 'Greens' ? 'bg-green-100 text-green-800' :
                    mp.political_bloc === 'Independent' ? 'bg-purple-100 text-purple-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {mp.political_bloc}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-500 italic">No connected MPs found</p>
        )}
      </div>
    </div>
  );
};

export default EntityDetail; 