import React from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import DisclosureTimeline from '../components/visualizations/DisclosureTimeline';
import { fetchMPDetails } from '../services/api';

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
  const mp = data?.mp;
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
    <div className="mp-profile">
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
      
      {/* Disclosure Timeline */}
      <div className="bg-white p-6 rounded-lg shadow mb-6">
        <DisclosureTimeline data={disclosures} mpName={mp.mp_name} />
      </div>
      
      {/* Recent Disclosures */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-2xl font-bold mb-4">Recent Disclosures</h2>
        
        {disclosures.length === 0 ? (
          <p className="text-gray-500">No disclosures found for this MP.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Date
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Category
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Item
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Entity
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {disclosures.slice(0, 10).map((disclosure) => (
                  <tr key={disclosure.id}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(disclosure.declaration_date).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {disclosure.category}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500 max-w-md truncate">
                      {disclosure.item}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {disclosure.entity || 'N/A'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default MPProfile; 