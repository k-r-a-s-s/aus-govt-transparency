import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import Layout from './components/layout/Layout';
import Home from './pages/Home';
import MPProfile from './pages/MPProfile';
import EntityExplorer from './pages/EntityExplorer';
import DisclosureAnalytics from './pages/DisclosureAnalytics';
import TravelAnalysis from './pages/TravelAnalysis';
import GeographicView from './pages/GeographicView';
import Export from './pages/Export';
import About from './pages/About';
import Privacy from './pages/Privacy';
import Terms from './pages/Terms';
import Contact from './pages/Contact';

// Create React Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 5 * 60 * 1000,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <Layout>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/mp/:name" element={<MPProfile />} />
            <Route path="/travel" element={<TravelAnalysis />} />
            <Route path="/entities" element={<EntityExplorer />} />
            <Route path="/analytics" element={<DisclosureAnalytics />} />
            <Route path="/geography" element={<GeographicView />} />
            <Route path="/export" element={<Export />} />
            <Route path="/about" element={<About />} />
            <Route path="/privacy" element={<Privacy />} />
            <Route path="/terms" element={<Terms />} />
            <Route path="/contact" element={<Contact />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </Layout>
      </Router>
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}

export default App;
