import React, { useMemo } from 'react';
import { DisclosureData } from '../../types';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';

interface DisclosureTimelineProps {
  data: DisclosureData[];
  mpName?: string;
  height?: number;
}

/**
 * Transforms disclosure data into a format suitable for a timeline visualization
 */
const transformToTimelineData = (data: DisclosureData[] = []) => {
  // Group disclosures by month
  const groupedByMonth: Record<string, number> = {};
  
  data.forEach(disclosure => {
    const date = new Date(disclosure.declaration_date);
    const monthYear = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
    
    groupedByMonth[monthYear] = (groupedByMonth[monthYear] || 0) + 1;
  });
  
  // Convert to array and sort by date
  return Object.entries(groupedByMonth)
    .map(([date, count]) => ({ date, count }))
    .sort((a, b) => a.date.localeCompare(b.date));
};

const DisclosureTimeline: React.FC<DisclosureTimelineProps> = ({ 
  data = [],
  mpName,
  height = 300
}) => {
  // Memoize the transformation to avoid recalculating on every render
  const timelineData = useMemo(() => transformToTimelineData(data), [data]);
  
  if (timelineData.length === 0) {
    return (
      <div className="text-center p-4 bg-gray-50 rounded-lg">
        <p className="text-gray-500">
          {mpName 
            ? `No timeline data available for ${mpName}`
            : 'No timeline data available'}
        </p>
      </div>
    );
  }
  
  return (
    <div>
      <h3 className="text-lg font-semibold mb-4">
        {mpName 
          ? `${mpName}'s Disclosure Timeline` 
          : 'Disclosure Timeline'}
      </h3>
      
      <ResponsiveContainer width="100%" height={height}>
        <LineChart
          data={timelineData}
          margin={{
            top: 5,
            right: 30,
            left: 20,
            bottom: 25
          }}
        >
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis 
            dataKey="date" 
            angle={-45} 
            textAnchor="end"
            tick={{ fontSize: 12 }}
          />
          <YAxis />
          <Tooltip 
            formatter={(value: number) => [`${value} disclosures`, 'Count']}
            labelFormatter={(label: string) => {
              const [year, month] = label.split('-');
              const date = new Date(parseInt(year), parseInt(month) - 1);
              return date.toLocaleDateString(undefined, { 
                year: 'numeric', 
                month: 'long' 
              });
            }}
          />
          <Legend />
          <Line
            type="monotone"
            dataKey="count"
            name="Disclosures"
            stroke="#8884d8"
            activeDot={{ r: 8 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default DisclosureTimeline; 