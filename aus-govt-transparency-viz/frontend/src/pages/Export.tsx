import React, { useState, useMemo } from 'react';
import useDisclosureData from '../hooks/useDisclosureData';
import { DisclosureData } from '../types';

const Export: React.FC = () => {
  // States for export options
  const [selectedFormat, setSelectedFormat] = useState<string>('csv');
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [selectedParty, setSelectedParty] = useState<string>('All');
  const [dateRange, setDateRange] = useState<{ from: string; to: string }>({
    from: '',
    to: ''
  });
  
  // Fetch disclosure data
  const { data: disclosures, isLoading, error } = useDisclosureData({ limit: 5000 });
  
  // Get unique categories and parties for filters
  const { categories, parties } = useMemo(() => {
    if (!disclosures) return { categories: [], parties: [] };
    
    const uniqueCategories = Array.from(new Set(disclosures.map(d => d.category)));
    const uniqueParties = Array.from(
      new Set(disclosures.map(d => d.party).filter(Boolean))
    );
    
    return { 
      categories: ['All', ...uniqueCategories],
      parties: ['All', ...uniqueParties]
    };
  }, [disclosures]);
  
  // Filter data based on selections
  const filteredData = useMemo(() => {
    if (!disclosures) return [];
    
    return disclosures.filter(d => {
      // Filter by category
      if (selectedCategory !== 'All' && d.category !== selectedCategory) {
        return false;
      }
      
      // Filter by party
      if (selectedParty !== 'All' && d.party !== selectedParty) {
        return false;
      }
      
      // Filter by date range
      if (dateRange.from && new Date(d.declaration_date) < new Date(dateRange.from)) {
        return false;
      }
      
      if (dateRange.to && new Date(d.declaration_date) > new Date(dateRange.to)) {
        return false;
      }
      
      return true;
    });
  }, [disclosures, selectedCategory, selectedParty, dateRange]);
  
  // Function to generate and download export
  const handleExport = () => {
    if (!filteredData.length) {
      alert('No data to export with the current filters.');
      return;
    }
    
    let content = '';
    let filename = `parliamentary-disclosures-${new Date().toISOString().slice(0, 10)}`;
    
    if (selectedFormat === 'csv') {
      // Generate CSV
      const headers = ['MP Name', 'Party', 'Electorate', 'Category', 'Item', 'Entity', 'Declaration Date'];
      content = headers.join(',') + '\n';
      
      content += filteredData.map(d => {
        // Properly escape CSV values
        return [
          `"${d.mp_name || ''}"`,
          `"${d.party || ''}"`,
          `"${d.electorate || ''}"`,
          `"${d.category || ''}"`,
          `"${(d.item || '').replace(/"/g, '""')}"`, // Escape quotes in CSV
          `"${(d.entity || '').replace(/"/g, '""')}"`,
          `"${d.declaration_date || ''}"`
        ].join(',');
      }).join('\n');
      
      filename += '.csv';
    } else if (selectedFormat === 'json') {
      // Generate JSON
      content = JSON.stringify(filteredData, null, 2);
      filename += '.json';
    }
    
    // Create download link
    const blob = new Blob([content], { type: selectedFormat === 'csv' ? 'text/csv' : 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
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
  if (error || !disclosures) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-800 p-4 rounded-md">
        <h3 className="text-lg font-semibold">Error Loading Data</h3>
        <p>{error instanceof Error ? error.message : 'Failed to load disclosure data'}</p>
      </div>
    );
  }
  
  return (
    <div className="export-page">
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">Export Data</h1>
        <p className="text-gray-600">
          Export parliamentary disclosure data for further analysis or integration with other tools.
        </p>
      </div>
      
      <div className="bg-white p-6 rounded-lg shadow mb-6">
        <h2 className="text-xl font-semibold mb-4">Export Options</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Export Format */}
          <div>
            <label htmlFor="format" className="block font-medium text-gray-700 mb-2">
              Export Format:
            </label>
            <select
              id="format"
              value={selectedFormat}
              onChange={(e) => setSelectedFormat(e.target.value)}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
            >
              <option value="csv">CSV (Comma Separated Values)</option>
              <option value="json">JSON (JavaScript Object Notation)</option>
            </select>
          </div>
          
          {/* Category Filter */}
          <div>
            <label htmlFor="category" className="block font-medium text-gray-700 mb-2">
              Filter by Category:
            </label>
            <select
              id="category"
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
            >
              {categories.map(category => (
                <option key={category} value={category}>{category}</option>
              ))}
            </select>
          </div>
          
          {/* Party Filter */}
          <div>
            <label htmlFor="party" className="block font-medium text-gray-700 mb-2">
              Filter by Party:
            </label>
            <select
              id="party"
              value={selectedParty}
              onChange={(e) => setSelectedParty(e.target.value)}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
            >
              {parties.map(party => (
                <option key={party} value={party}>{party}</option>
              ))}
            </select>
          </div>
          
          {/* Date Range */}
          <div>
            <label className="block font-medium text-gray-700 mb-2">
              Date Range:
            </label>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="date-from" className="block text-sm text-gray-500 mb-1">
                  From:
                </label>
                <input
                  type="date"
                  id="date-from"
                  value={dateRange.from}
                  onChange={(e) => setDateRange({ ...dateRange, from: e.target.value })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                />
              </div>
              <div>
                <label htmlFor="date-to" className="block text-sm text-gray-500 mb-1">
                  To:
                </label>
                <input
                  type="date"
                  id="date-to"
                  value={dateRange.to}
                  onChange={(e) => setDateRange({ ...dateRange, to: e.target.value })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                />
              </div>
            </div>
          </div>
        </div>
        
        {/* Export Button */}
        <div className="mt-6">
          <button
            onClick={handleExport}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            Export {filteredData.length} Records
          </button>
          <p className="mt-2 text-sm text-gray-500">
            {filteredData.length === 0 ? 
              'No records match your filter criteria.' : 
              `${filteredData.length} records will be exported.`}
          </p>
        </div>
      </div>
      
      {/* Data Preview */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-semibold mb-4">Data Preview</h2>
        
        {filteredData.length === 0 ? (
          <p className="text-gray-500">No data matches your filter criteria.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    MP Name
                  </th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Party
                  </th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Category
                  </th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Item
                  </th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Date
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredData.slice(0, 10).map((disclosure, index) => (
                  <tr key={index}>
                    <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-900">
                      {disclosure.mp_name}
                    </td>
                    <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">
                      {disclosure.party || 'N/A'}
                    </td>
                    <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">
                      {disclosure.category}
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-500 max-w-xs truncate">
                      {disclosure.item}
                    </td>
                    <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">
                      {new Date(disclosure.declaration_date).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            
            {filteredData.length > 10 && (
              <p className="mt-4 text-sm text-gray-500">
                Showing 10 of {filteredData.length} records. Export to see all data.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default Export; 