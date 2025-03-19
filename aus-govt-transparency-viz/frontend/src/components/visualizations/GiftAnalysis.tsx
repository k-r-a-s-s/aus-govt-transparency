import React, { useMemo } from 'react';
import { DisclosureData } from '../../types';
import { transformToGiftAnalysis } from '../../utils/dataTransformers';
import {
  PieChart, Pie, Cell, 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer
} from 'recharts';

interface GiftAnalysisProps {
  data: DisclosureData[];
}

// Chart colors
const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8', '#82ca9d', '#ffc658', '#8dd1e1'];

const GiftAnalysis: React.FC<GiftAnalysisProps> = ({ data }) => {
  // Transform data for gift analysis
  const giftAnalysis = useMemo(() => transformToGiftAnalysis(data), [data]);
  
  // If no gift data, show a message
  if (giftAnalysis.byType.length === 0) {
    return (
      <div className="text-center p-4 bg-gray-50 rounded-lg">
        <p className="text-gray-500">No gift data available for analysis.</p>
      </div>
    );
  }
  
  return (
    <div className="gift-analysis">
      <h2 className="text-xl font-semibold mb-4">Gift Analysis</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-6">
        {/* Gift Types Pie Chart */}
        <div className="bg-white p-4 rounded-lg shadow">
          <h3 className="text-lg font-medium mb-3">Types of Gifts</h3>
          
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={giftAnalysis.byType}
                cx="50%"
                cy="50%"
                labelLine={false}
                outerRadius={80}
                fill="#8884d8"
                dataKey="count"
                nameKey="type"
                label={({ type, percent }) => `${type}: ${(percent * 100).toFixed(0)}%`}
              >
                {giftAnalysis.byType.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(value) => [`${value} gifts`, 'Count']} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        
        {/* Top Gift Providers Bar Chart */}
        <div className="bg-white p-4 rounded-lg shadow">
          <h3 className="text-lg font-medium mb-3">Top Gift Providers</h3>
          
          <ResponsiveContainer width="100%" height={280}>
            <BarChart
              layout="vertical"
              data={giftAnalysis.byProvider.slice(0, 5)}
              margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" />
              <YAxis 
                type="category" 
                dataKey="provider" 
                width={120}
                tick={{ fontSize: 12 }}
              />
              <Tooltip formatter={(value) => [`${value} gifts`, 'Count']} />
              <Legend />
              <Bar dataKey="count" name="Number of Gifts" fill="#82ca9d" />
            </BarChart>
          </ResponsiveContainer>
        </div>
        
        {/* Gifts by Party Pie Chart */}
        <div className="bg-white p-4 rounded-lg shadow">
          <h3 className="text-lg font-medium mb-3">Gifts by Party</h3>
          
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={giftAnalysis.byParty}
                cx="50%"
                cy="50%"
                labelLine={false}
                outerRadius={80}
                fill="#8884d8"
                dataKey="count"
                nameKey="party"
                label={({ party, percent }) => `${party}: ${(percent * 100).toFixed(0)}%`}
              >
                {giftAnalysis.byParty.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(value) => [`${value} gifts`, 'Count']} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
      
      {/* Key Insights */}
      <div className="bg-white p-4 rounded-lg shadow mb-6">
        <h3 className="text-lg font-medium mb-3">Key Insights</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <p className="text-sm text-gray-600">Most Common Gift Type</p>
            <p className="text-lg font-semibold">{giftAnalysis.mostCommon.type}</p>
          </div>
          <div>
            <p className="text-sm text-gray-600">Top Gift Provider</p>
            <p className="text-lg font-semibold">{giftAnalysis.mostCommon.provider}</p>
          </div>
          <div>
            <p className="text-sm text-gray-600">Party Receiving Most Gifts</p>
            <p className="text-lg font-semibold">{giftAnalysis.mostCommon.party}</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default GiftAnalysis; 