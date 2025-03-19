import React from 'react';
import { TimelineData } from '../../types';
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
  timelineData: TimelineData;
  mpName?: string;
  height?: number;
}

const DisclosureTimeline: React.FC<DisclosureTimelineProps> = ({ 
  timelineData,
  mpName,
  height = 300
}) => {
  if (!timelineData || !timelineData.timeline || timelineData.timeline.length === 0) {
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
          data={timelineData.timeline}
          margin={{
            top: 5,
            right: 30,
            left: 20,
            bottom: 25
          }}
        >
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis 
            dataKey="month" 
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