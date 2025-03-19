import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/layout/Layout';
import Home from './pages/Home';
import MPProfile from './pages/MPProfile';
import EntityExplorer from './pages/EntityExplorer';
import DisclosureAnalytics from './pages/DisclosureAnalytics';
import GiftsAndTravel from './pages/GiftsAndTravel';
import GeographicView from './pages/GeographicView';
import Export from './pages/Export';

// Create React Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      retry: 1,
    },
  },
});

const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <Layout>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/mp/:name" element={<MPProfile />} />
            <Route path="/entities" element={<EntityExplorer />} />
            <Route path="/analytics" element={<DisclosureAnalytics />} />
            <Route path="/gifts-travel" element={<GiftsAndTravel />} />
            <Route path="/geographic" element={<GeographicView />} />
            <Route path="/export" element={<Export />} />
          </Routes>
        </Layout>
      </Router>
    </QueryClientProvider>
  );
};

export default App;
