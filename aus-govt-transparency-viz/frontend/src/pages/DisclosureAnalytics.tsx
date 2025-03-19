import React, { useState, useMemo } from 'react';
import useDisclosureData from '../hooks/useDisclosureData';
import { DisclosureData } from '../types';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line
} from 'recharts';

// Define chart color palette
const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8', '#82ca9d', '#ffc658', '#8dd1e1'];

const DisclosureAnalytics: React.FC = () => {
  // State for category filter
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  
  // Fetch disclosure data (adjust limit as needed)
  const { data: disclosures, isLoading, error } = useDisclosureData({ limit: 1000 });
  
  // Get unique categories for filter dropdown
  const categories = useMemo(() => {
    if (!disclosures) return [];
    
    const uniqueCategories = Array.from(new Set(disclosures.map(d => d.category)));
    return ['All', ...uniqueCategories];
  }, [disclosures]);
  
  // Filter disclosures by selected category
  const filteredDisclosures = useMemo(() => {
    if (!disclosures) return [];
    
    return selectedCategory === 'All' 
      ? disclosures 
      : disclosures.filter(d => d.category === selectedCategory);
  }, [disclosures, selectedCategory]);
  
  // Prepare data for MP count by party chart
  const partyData = useMemo(() => {
    if (!filteredDisclosures.length) return [];
    
    const mpsByParty: Record<string, Set<string>> = {};
    
    filteredDisclosures.forEach(d => {
      const party = d.party || 'Unknown';
      if (!mpsByParty[party]) {
        mpsByParty[party] = new Set();
      }
      mpsByParty[party].add(d.mp_name);
    });
    
    return Object.entries(mpsByParty)
      .map(([party, mps]) => ({
        party,
        count: mps.size
      }))
      .sort((a, b) => b.count - a.count);
  }, [filteredDisclosures]);
  
  // Prepare data for disclosures by category chart
  const categoryData = useMemo(() => {
    if (!disclosures) return [];
    
    const countByCategory: Record<string, number> = {};
    
    disclosures.forEach(d => {
      countByCategory[d.category] = (countByCategory[d.category] || 0) + 1;
    });
    
    return Object.entries(countByCategory)
      .map(([category, count]) => ({
        category,
        count
      }))
      .sort((a, b) => b.count - a.count);
  }, [disclosures]);
  
  // Prepare data for disclosure timeline chart
  const timelineData = useMemo(() => {
    if (!filteredDisclosures.length) return [];
    
    const countByMonth: Record<string, number> = {};
    
    filteredDisclosures.forEach(d => {
      const date = new Date(d.declaration_date);
      const monthYear = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
      
      countByMonth[monthYear] = (countByMonth[monthYear] || 0) + 1;
    });
    
    return Object.entries(countByMonth)
      .map(([monthYear, count]) => ({
        monthYear,
        count
      }))
      .sort((a, b) => a.monthYear.localeCompare(b.monthYear));
  }, [filteredDisclosures]);
  
  // Prepare data for top MPs chart
  const topMPsData = useMemo(() => {
    if (!filteredDisclosures.length) return [];
    
    const countByMP: Record<string, number> = {};
    
    filteredDisclosures.forEach(d => {
      countByMP[d.mp_name] = (countByMP[d.mp_name] || 0) + 1;
    });
    
    return Object.entries(countByMP)
      .map(([mp, count]) => ({
        mp,
        count
      }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10); // Top 10 MPs
  }, [filteredDisclosures]);
  
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
    <div className="disclosure-analytics">
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">Disclosure Analytics</h1>
        <p className="text-gray-600">
          Explore patterns and insights from Parliamentary disclosures data.
        </p>
      </div>
      
      {/* Filter by category */}
      <div className="mb-6 bg-white p-4 rounded-lg shadow">
        <label htmlFor="category-filter" className="block font-medium text-gray-700 mb-2">
          Filter by Category:
        </label>
        <select
          id="category-filter"
          value={selectedCategory}
          onChange={(e) => setSelectedCategory(e.target.value)}
          className="block w-full max-w-xs rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
        >
          {categories.map(category => (
            <option key={category} value={category}>{category}</option>
          ))}
        </select>
        
        <div className="mt-4">
          <p className="text-gray-600">
            Showing {filteredDisclosures.length} disclosures
            {selectedCategory !== 'All' ? ` for category: ${selectedCategory}` : ''}
          </p>
        </div>
      </div>
      
      {/* Charts grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        {/* MPs by Party Chart */}
        <div className="bg-white p-4 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">MPs by Party</h2>
          
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={partyData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="party" />
              <YAxis />
              <Tooltip formatter={(value) => [`${value} MPs`, 'Count']} />
              <Legend />
              <Bar dataKey="count" fill="#0088FE" name="Number of MPs" />
            </BarChart>
          </ResponsiveContainer>
        </div>
        
        {/* Disclosures by Category Pie Chart */}
        <div className="bg-white p-4 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">Disclosures by Category</h2>
          
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={categoryData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="count"
                nameKey="category"
              >
                {categoryData.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(value) => [`${value} disclosures`, 'Count']} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
        
        {/* Disclosure Timeline Chart */}
        <div className="bg-white p-4 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">Disclosure Timeline</h2>
          
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={timelineData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="monthYear" />
              <YAxis />
              <Tooltip formatter={(value) => [`${value} disclosures`, 'Count']} />
              <Legend />
              <Line type="monotone" dataKey="count" stroke="#8884d8" activeDot={{ r: 8 }} name="Disclosures" />
            </LineChart>
          </ResponsiveContainer>
        </div>
        
        {/* Top MPs Chart */}
        <div className="bg-white p-4 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">Top MPs by Disclosure Count</h2>
          
          <ResponsiveContainer width="100%" height={300}>
            <BarChart
              data={topMPsData}
              layout="vertical"
              margin={{ top: 5, right: 30, left: 150, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" />
              <YAxis type="category" dataKey="mp" tick={{ fontSize: 12 }} width={150} />
              <Tooltip formatter={(value) => [`${value} disclosures`, 'Count']} />
              <Legend />
              <Bar dataKey="count" fill="#82ca9d" name="Number of Disclosures" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      
      {/* Key insights */}
      <div className="bg-white p-4 rounded-lg shadow mb-6">
        <h2 className="text-xl font-semibold mb-4">Key Insights</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <h3 className="text-lg font-medium mb-2">Most Common Category</h3>
            <p className="text-gray-700">
              {categoryData.length > 0 ? categoryData[0].category : 'No data'}
              {categoryData.length > 0 ? ` (${categoryData[0].count} disclosures)` : ''}
            </p>
          </div>
          
          <div>
            <h3 className="text-lg font-medium mb-2">MP with Most Disclosures</h3>
            <p className="text-gray-700">
              {topMPsData.length > 0 ? topMPsData[0].mp : 'No data'}
              {topMPsData.length > 0 ? ` (${topMPsData[0].count} disclosures)` : ''}
            </p>
          </div>
          
          <div>
            <h3 className="text-lg font-medium mb-2">Party with Most MPs</h3>
            <p className="text-gray-700">
              {partyData.length > 0 ? partyData[0].party : 'No data'}
              {partyData.length > 0 ? ` (${partyData[0].count} MPs)` : ''}
            </p>
          </div>
          
          <div>
            <h3 className="text-lg font-medium mb-2">Month with Most Disclosures</h3>
            <p className="text-gray-700">
              {timelineData.length > 0 
                ? timelineData.reduce((max, item) => item.count > max.count ? item : max, timelineData[0]).monthYear 
                : 'No data'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DisclosureAnalytics; 