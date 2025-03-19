import React from 'react';
import { Box, Typography, Paper } from '@mui/material';

interface TravelMapProps {
  disclosures?: Array<{
    id: number;
    mp_name: string;
    entity: string;
    description: string;
    date: string;
  }>;
}

const TravelMap: React.FC<TravelMapProps> = ({ disclosures = [] }) => {
  // This is a placeholder component for now
  // In a future update, this would be replaced with an actual map visualization
  // using libraries like react-leaflet, mapbox-gl, or google-maps-react
  
  return (
    <Paper 
      elevation={0} 
      sx={{ 
        p: 3, 
        height: 300, 
        display: 'flex', 
        flexDirection: 'column', 
        justifyContent: 'center', 
        alignItems: 'center',
        backgroundColor: '#f5f5f5',
        border: '1px dashed #ccc'
      }}
    >
      <Box 
        sx={{ 
          width: 60, 
          height: 60, 
          borderRadius: '50%', 
          backgroundColor: '#e0e0e0', 
          display: 'flex', 
          justifyContent: 'center', 
          alignItems: 'center',
          mb: 2
        }}
      >
        <Box component="span" sx={{ fontSize: '2rem' }}>🌍</Box>
      </Box>
      <Typography variant="h6" gutterBottom>
        Travel Map Visualization
      </Typography>
      <Typography variant="body2" color="text.secondary" align="center">
        A geographical visualization of travel destinations will be available in a future update.
        {disclosures.length > 0 && ` Currently analyzing ${disclosures.length} travel records.`}
      </Typography>
    </Paper>
  );
};

export default TravelMap; 