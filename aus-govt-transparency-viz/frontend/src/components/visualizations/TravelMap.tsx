import React from 'react';
import { Box, Typography, Paper } from '@mui/material';

interface TravelMapProps {
  data?: any[];
}

const TravelMap: React.FC<TravelMapProps> = ({ data = [] }) => {
  return (
    <Paper sx={{ p: 3, mt: 2 }}>
      <Typography variant="h6" gutterBottom>
        Travel Destinations Map
      </Typography>
      <Typography variant="body2" color="text.secondary" paragraph>
        Interactive map showing travel destinations will be displayed here.
        This is a placeholder component that will be implemented in the future.
      </Typography>
      <Box sx={{ 
        height: 300, 
        bgcolor: '#f5f5f5', 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center',
        borderRadius: 1
      }}>
        <Typography variant="body1" color="text.secondary">
          Map visualization coming soon
        </Typography>
      </Box>
    </Paper>
  );
};

export default TravelMap; 