import React, { useState, useMemo } from 'react';
import { 
  Container, Typography, Box, Grid, Card, CardContent,
  CircularProgress, Paper, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Divider
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { fetchDisclosures } from '../services/api';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, 
         PieChart, Pie, Legend, Sector } from 'recharts';
import TravelMap from '../components/visualizations/TravelMap';

// Define types
interface TravelDisclosure {
  id: number;
  mp_name: string;
  entity: string;
  description: string;
  date: string;
  party: string;
}

interface EntityCount {
  name: string;
  value: number;
  color?: string;
}

interface MPCount {
  name: string;
  value: number;
  party: string;
}

// Define color for political parties
const partyColors: Record<string, string> = {
  'Liberal Party': '#0047AB',
  'Labor Party': '#B22222',
  'National Party': '#006400',
  'Australian Greens': '#00A36C',
  'Independent': '#808080',
  'Liberal National Party': '#1E3F66',
  'Centre Alliance': '#FF8C00',
  'Jacqui Lambie Network': '#8A2BE2',
  'One Nation': '#FF4500',
  'United Australia Party': '#FFD700'
};

// Default color for unknown parties
const defaultColor = '#777777';

// Colors for entities
const entityColors = [
  '#8884d8', '#83a6ed', '#8dd1e1', '#82ca9d', '#a4de6c',
  '#d0ed57', '#ffc658', '#ff8042', '#ff6361', '#bc5090'
];

export const TravelAnalysis: React.FC = () => {
  const [activeEntityIndex, setActiveEntityIndex] = useState<number | undefined>(undefined);
  const [activeMPIndex, setActiveMPIndex] = useState<number | undefined>(undefined);

  // Fetch travel disclosures
  const { data: travelData, isLoading, error } = useQuery({
    queryKey: ['disclosures', 'Travel'],
    queryFn: () => fetchDisclosures({ category: 'Travel', limit: 500 })
  });

  // Process travel data
  const processTravelData = useMemo(() => {
    if (!travelData) return { byEntity: [], byMP: [], disclosures: [] };

    const disclosures = travelData as TravelDisclosure[];
    const entitiesMap = new Map<string, number>();
    const mpsMap = new Map<string, { count: number; party: string }>();

    // Count by entity and MP
    disclosures.forEach(disclosure => {
      if (disclosure.entity) {
        entitiesMap.set(disclosure.entity, (entitiesMap.get(disclosure.entity) || 0) + 1);
      }
      if (disclosure.mp_name) {
        const currentMP = mpsMap.get(disclosure.mp_name);
        if (currentMP) {
          currentMP.count += 1;
        } else {
          mpsMap.set(disclosure.mp_name, { count: 1, party: disclosure.party || 'Unknown' });
        }
      }
    });

    // Convert to array and sort
    const byEntity: EntityCount[] = Array.from(entitiesMap, ([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 10)
      .map((item, index) => ({
        ...item,
        color: entityColors[index % entityColors.length]
      }));

    const byMP: MPCount[] = Array.from(mpsMap, ([name, data]) => ({ 
      name, 
      value: data.count,
      party: data.party
    }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 10);

    return { byEntity, byMP, disclosures };
  }, [travelData]);

  const renderActiveEntityShape = (props: any) => {
    const { cx, cy, innerRadius, outerRadius, startAngle, endAngle, fill } = props;
    return (
      <g>
        <Sector
          cx={cx}
          cy={cy}
          innerRadius={innerRadius}
          outerRadius={outerRadius + 6}
          startAngle={startAngle}
          endAngle={endAngle}
          fill={fill}
        />
      </g>
    );
  };

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="60vh">
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="error">Error loading travel data.</Typography>
      </Box>
    );
  }

  const { byEntity, byMP, disclosures } = processTravelData;

  return (
    <Container maxWidth="lg">
      <Box sx={{ my: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Travel Sponsorship Analysis
        </Typography>
        <Typography variant="body1" color="text.secondary" paragraph>
          Explore travel arrangements, accommodations, and sponsorships disclosed by Members of Parliament.
          This visualization highlights patterns in sponsored travel and the organizations providing these benefits.
        </Typography>

        <Grid container spacing={3} sx={{ mt: 2 }}>
          {/* Top travel sponsors chart */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Top Travel Sponsors
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  Organizations that most frequently sponsor MP travel
                </Typography>
                <Box sx={{ height: 300 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={byEntity}
                      margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                    >
                      <XAxis dataKey="name" angle={-45} textAnchor="end" height={100} />
                      <YAxis />
                      <Tooltip />
                      <Bar dataKey="value" name="Number of sponsorships">
                        {byEntity.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          {/* MPs with most travel chart */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  MPs with Most Travel
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  Members of Parliament who disclosed the most sponsored travel
                </Typography>
                <Box sx={{ height: 300 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        activeIndex={activeMPIndex}
                        activeShape={renderActiveEntityShape}
                        data={byMP}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={80}
                        dataKey="value"
                        onMouseEnter={(_, index) => setActiveMPIndex(index)}
                        onMouseLeave={() => setActiveMPIndex(undefined)}
                      >
                        {byMP.map((entry, index) => (
                          <Cell 
                            key={`cell-${index}`} 
                            fill={partyColors[entry.party] || defaultColor} 
                          />
                        ))}
                      </Pie>
                      <Tooltip formatter={(value, name, props) => {
                        const entry = props.payload;
                        return [`${value} trips`, `${entry.name} (${entry.party})`];
                      }} />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          {/* Key Findings */}
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Key Findings in Travel Disclosures
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} md={6}>
                  <Typography variant="subtitle1">Travel Sponsors</Typography>
                  <Typography paragraph>
                    The data shows that international organizations, industry bodies, and foreign governments 
                    are the most frequent sponsors of MP travel. Many trips include accommodations, flights, 
                    and conference registrations.
                  </Typography>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Typography variant="subtitle1">Travel Patterns</Typography>
                  <Typography paragraph>
                    Ministers and shadow ministers typically receive more sponsored travel than backbenchers.
                    Travel related to trade delegations, fact-finding missions, and conferences make up the 
                    majority of disclosures.
                  </Typography>
                </Grid>
              </Grid>
            </Paper>
          </Grid>

          {/* Travel Destinations Map */}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Recent Travel Disclosures
                </Typography>
                <TableContainer component={Paper} sx={{ maxHeight: 400 }}>
                  <Table stickyHeader size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>MP</TableCell>
                        <TableCell>Party</TableCell>
                        <TableCell>Sponsor</TableCell>
                        <TableCell>Description</TableCell>
                        <TableCell>Date</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {disclosures.slice(0, 20).map((row) => (
                        <TableRow key={row.id} hover>
                          <TableCell>{row.mp_name}</TableCell>
                          <TableCell>{row.party}</TableCell>
                          <TableCell>{row.entity}</TableCell>
                          <TableCell>{row.description}</TableCell>
                          <TableCell>{new Date(row.date).toLocaleDateString()}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Box>
    </Container>
  );
};

export default TravelAnalysis; 