import React, { useState, useMemo } from 'react';
import useDisclosureData from '../hooks/useDisclosureData';
import { DisclosureData } from '../types';

const GeographicView: React.FC = () => {
  // State for filter
  const [selectedParty, setSelectedParty] = useState<string>('All');
  
  // Fetch disclosure data
  const { data: disclosures, isLoading, error } = useDisclosureData({ limit: 1000 });
  
  // Get unique parties for filter dropdown
  const parties = useMemo(() => {
    if (!disclosures) return [];
    
    const uniqueParties = Array.from(
      new Set(disclosures.map(d => d.party).filter(Boolean))
    );
    return ['All', ...uniqueParties];
  }, [disclosures]);
  
  // Get electorate data
  const electorateData = useMemo(() => {
    if (!disclosures) return {};
    
    const data: Record<string, { 
      count: number; 
      mps: Set<string>; 
      party?: string;
      categories: Record<string, number>;
    }> = {};
    
    // Filter by selected party if needed
    const filteredDisclosures = selectedParty === 'All' 
      ? disclosures 
      : disclosures.filter(d => d.party === selectedParty);
    
    filteredDisclosures.forEach(d => {
      if (!d.electorate) return;
      
      if (!data[d.electorate]) {
        data[d.electorate] = {
          count: 0,
          mps: new Set(),
          party: d.party,
          categories: {}
        };
      }
      
      data[d.electorate].count += 1;
      data[d.electorate].mps.add(d.mp_name);
      
      if (d.category) {
        data[d.electorate].categories[d.category] = 
          (data[d.electorate].categories[d.category] || 0) + 1;
      }
    });
    
    return data;
  }, [disclosures, selectedParty]);
  
  // Get electorate stats
  const stats = useMemo(() => {
    const electorates = Object.keys(electorateData).length;
    
    // Find electorate with most disclosures
    let maxElectorate = '';
    let maxCount = 0;
    
    Object.entries(electorateData).forEach(([electorate, data]) => {
      if (data.count > maxCount) {
        maxCount = data.count;
        maxElectorate = electorate;
      }
    });
    
    return {
      totalElectorates: electorates,
      mostDisclosures: {
        electorate: maxElectorate,
        count: maxCount
      }
    };
  }, [electorateData]);
  
  // Handle loading state
  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }
  
  // Handle error state
  if (error || !disclosures) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-800 p-4 rounded-md">
        <h3 className="text-lg font-semibold">Error Loading Data</h3>
        <p>{error instanceof Error ? error.message : 'Failed to load disclosure data'}</p>
      </div>
    );
  }
  
  return (
    <div className="geographic-view">
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">Geographic View</h1>
        <p className="text-gray-600">
          Explore parliamentary disclosures by electorate and geographic region.
        </p>
      </div>
      
      {/* Filter by party */}
      <div className="mb-6 bg-white p-4 rounded-lg shadow">
        <label htmlFor="party-filter" className="block font-medium text-gray-700 mb-2">
          Filter by Party:
        </label>
        <select
          id="party-filter"
          value={selectedParty}
          onChange={(e) => setSelectedParty(e.target.value)}
          className="block w-full max-w-xs rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
        >
          {parties.map(party => (
            <option key={party} value={party}>{party}</option>
          ))}
        </select>
      </div>
      
      {/* Map placeholder */}
      <div className="bg-white p-4 rounded-lg shadow mb-6">
        <h2 className="text-xl font-semibold mb-4">Disclosure Map</h2>
        
        <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 bg-gray-50 flex flex-col items-center justify-center" style={{ height: '500px' }}>
          <svg xmlns="http://www.w3.org/2000/svg" className="h-16 w-16 text-gray-400 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
          </svg>
          <p className="text-gray-500 text-center mb-2">
            Interactive Map Coming Soon
          </p>
          <p className="text-gray-400 text-center text-sm max-w-lg">
            This area will display an interactive map of Australia showing disclosures by electorate.
            Each electorate will be colored based on disclosure count or selected metric.
          </p>
        </div>
      </div>
      
      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <div className="bg-white p-4 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">Electorate Overview</h2>
          
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="bg-blue-50 p-4 rounded-lg">
              <p className="text-sm text-gray-600">Total Electorates with Disclosures</p>
              <p className="text-2xl font-bold text-blue-700">{stats.totalElectorates}</p>
            </div>
            
            <div className="bg-green-50 p-4 rounded-lg">
              <p className="text-sm text-gray-600">Electorate with Most Disclosures</p>
              <p className="text-2xl font-bold text-green-700">
                {stats.mostDisclosures.electorate || 'N/A'}
              </p>
              <p className="text-sm text-gray-500">
                {stats.mostDisclosures.count ? `${stats.mostDisclosures.count} disclosures` : ''}
              </p>
            </div>
          </div>
        </div>
        
        <div className="bg-white p-4 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">Top Electorates</h2>
          
          {Object.keys(electorateData).length === 0 ? (
            <p className="text-gray-500">No data available for the selected filter.</p>
          ) : (
            <div className="overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Electorate
                    </th>
                    <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      MPs
                    </th>
                    <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Disclosures
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {Object.entries(electorateData)
                    .sort((a, b) => b[1].count - a[1].count)
                    .slice(0, 5)
                    .map(([electorate, data]) => (
                      <tr key={electorate}>
                        <td className="px-4 py-2 whitespace-nowrap text-sm font-medium text-gray-900">
                          {electorate}
                        </td>
                        <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">
                          {data.mps.size}
                        </td>
                        <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">
                          {data.count}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
      
      {/* Electorate Details */}
      <div className="bg-white p-4 rounded-lg shadow mb-6">
        <h2 className="text-xl font-semibold mb-4">Electorate Details</h2>
        
        {Object.keys(electorateData).length === 0 ? (
          <p className="text-gray-500">No data available for the selected filter.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Electorate
                  </th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Party
                  </th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    MPs
                  </th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Total Disclosures
                  </th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Top Category
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {Object.entries(electorateData)
                  .sort((a, b) => b[1].count - a[1].count)
                  .map(([electorate, data]) => {
                    // Find top category
                    let topCategory = '';
                    let topCategoryCount = 0;
                    
                    Object.entries(data.categories).forEach(([category, count]) => {
                      if (count > topCategoryCount) {
                        topCategoryCount = count;
                        topCategory = category;
                      }
                    });
                    
                    return (
                      <tr key={electorate}>
                        <td className="px-4 py-2 whitespace-nowrap text-sm font-medium text-gray-900">
                          {electorate}
                        </td>
                        <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">
                          {data.party || 'Unknown'}
                        </td>
                        <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">
                          {Array.from(data.mps).join(', ')}
                        </td>
                        <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">
                          {data.count}
                        </td>
                        <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">
                          {topCategory ? `${topCategory} (${topCategoryCount})` : 'N/A'}
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default GeographicView; 