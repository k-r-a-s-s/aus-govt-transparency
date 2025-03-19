import React from 'react';
import { Container, Typography, Box, Paper, Link, Grid, Card, CardContent } from '@mui/material';

const About: React.FC = () => {
  return (
    <Container maxWidth="lg">
      <Box sx={{ mt: 4, mb: 6 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          About the Parliament Disclosures Project
        </Typography>
        
        <Paper elevation={2} sx={{ p: 3, mb: 4 }}>
          <Typography variant="h6" gutterBottom>
            Project Overview
          </Typography>
          <Typography paragraph>
            This project visualizes the relationships between Australian MPs and the entities mentioned in their 
            register of interests disclosures. It aims to make this important transparency data more accessible 
            and easier to understand for the public.
          </Typography>
          <Typography paragraph>
            The data comes from the Australian Parliament's publicly available register of members' interests,
            which contains information about MPs' financial interests, gifts, travel, and other potential
            conflicts of interest.
          </Typography>
        </Paper>

        <Typography variant="h5" gutterBottom>
          Features
        </Typography>
        
        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid item xs={12} md={4}>
            <Card elevation={2} sx={{ height: '100%' }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Data Exploration
                </Typography>
                <Typography>
                  Browse through MP profiles, view disclosure statistics, and explore the network
                  of relationships between politicians and entities.
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          
          <Grid item xs={12} md={4}>
            <Card elevation={2} sx={{ height: '100%' }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Travel Analysis
                </Typography>
                <Typography>
                  Analyze sponsored travel disclosures, including the most common sponsors
                  and destinations.
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          
          <Grid item xs={12} md={4}>
            <Card elevation={2} sx={{ height: '100%' }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Asset Explorer
                </Typography>
                <Typography>
                  Explore the geographical distribution of assets and properties
                  disclosed by MPs.
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        <Paper elevation={2} sx={{ p: 3, mb: 4 }}>
          <Typography variant="h6" gutterBottom>
            About g0v
          </Typography>
          <Typography paragraph>
            This project is part of the <Link href="https://g0v.tw/" target="_blank" rel="noopener">g0v (gov zero)</Link> initiative,
            a global civic tech community focused on improving transparency, citizen participation, and open government.
          </Typography>
          <Typography>
            All data visualized in this application is derived from public information. The code is open source 
            and available on GitHub.
          </Typography>
        </Paper>
        
        <Typography variant="body2" color="text.secondary" align="center" sx={{ mt: 4 }}>
          © {new Date().getFullYear()} Parliament Disclosures Project. All rights reserved.
        </Typography>
      </Box>
    </Container>
  );
};

export default About; 