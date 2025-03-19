import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { fetchDisclosureStats } from '../services/api';
import DisclosureTimeline from '../components/visualizations/DisclosureTimeline';
import { useDisclosureData } from '../hooks/useDisclosureData';

const Home: React.FC = () => {
  // Fetch disclosure data for visualizations
  const { data: disclosures = [], isLoading: isLoadingDisclosures } = useDisclosureData({ limit: 1000 });
  
  // Fetch statistics
  const { data: stats, isLoading: isLoadingStats } = useQuery({
    queryKey: ['disclosure-stats'],
    queryFn: fetchDisclosureStats,
  });
  
  const isLoading = isLoadingDisclosures || isLoadingStats;
  
  return (
    <div className="dashboard">
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">Parliamentary Disclosure Dashboard</h1>
        <p className="text-gray-600">
          Visualizing and analyzing financial disclosure data from Australian Members of Parliament.
        </p>
      </div>
      
      {isLoading ? (
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
        </div>
      ) : (
        <>
          {/* Stats Overview */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div className="bg-white p-4 rounded-lg shadow">
              <h3 className="text-lg font-semibold mb-2">Total Disclosures</h3>
              <p className="text-3xl font-bold text-blue-600">
                {stats?.total_disclosures?.toLocaleString() || '0'}
              </p>
            </div>
            
            <div className="bg-white p-4 rounded-lg shadow">
              <h3 className="text-lg font-semibold mb-2">MPs with Disclosures</h3>
              <p className="text-3xl font-bold text-green-600">
                {stats?.total_mps?.toLocaleString() || '0'}
              </p>
            </div>
            
            <div className="bg-white p-4 rounded-lg shadow">
              <h3 className="text-lg font-semibold mb-2">Disclosed Entities</h3>
              <p className="text-3xl font-bold text-amber-600">
                {stats?.total_entities?.toLocaleString() || '0'}
              </p>
            </div>
          </div>
          
          {/* Timeline Chart */}
          <div className="bg-white p-4 rounded-lg shadow mb-6">
            <DisclosureTimeline data={disclosures} />
          </div>
          
          {/* Top MPs and Categories */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div className="bg-white p-4 rounded-lg shadow">
              <h3 className="text-lg font-semibold mb-4">Top MPs by Disclosures</h3>
              <div className="space-y-2">
                {stats?.top_mps?.slice(0, 5).map((mp) => (
                  <div key={mp.mp_name} className="flex justify-between items-center border-b pb-2">
                    <Link 
                      to={`/mp/${encodeURIComponent(mp.mp_name)}`}
                      className="text-blue-600 hover:text-blue-800"
                    >
                      {mp.mp_name}
                    </Link>
                    <span className="font-semibold">{mp.count} disclosures</span>
                  </div>
                )) || <div className="text-gray-500">No data available</div>}
              </div>
              <div className="mt-4">
                <Link 
                  to="/analytics" 
                  className="text-blue-600 hover:text-blue-800 text-sm flex items-center"
                >
                  View all MPs
                  <svg 
                    xmlns="http://www.w3.org/2000/svg" 
                    className="h-4 w-4 ml-1" 
                    viewBox="0 0 20 20" 
                    fill="currentColor"
                  >
                    <path 
                      fillRule="evenodd" 
                      d="M10.293 5.293a1 1 0 011.414 0l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414-1.414L12.586 11H5a1 1 0 110-2h7.586l-2.293-2.293a1 1 0 010-1.414z" 
                      clipRule="evenodd" 
                    />
                  </svg>
                </Link>
              </div>
            </div>
            
            <div className="bg-white p-4 rounded-lg shadow">
              <h3 className="text-lg font-semibold mb-4">Disclosure Categories</h3>
              <div className="space-y-2">
                {stats && stats.disclosures_by_category && Object.entries(stats.disclosures_by_category).map(([category, count]) => (
                  <div key={category} className="flex justify-between items-center border-b pb-2">
                    <span>{category}</span>
                    <span className="font-semibold">{count} disclosures</span>
                  </div>
                )) || <div className="text-gray-500">No data available</div>}
              </div>
              <div className="mt-4">
                <Link 
                  to="/analytics" 
                  className="text-blue-600 hover:text-blue-800 text-sm flex items-center"
                >
                  Explore category analysis
                  <svg 
                    xmlns="http://www.w3.org/2000/svg" 
                    className="h-4 w-4 ml-1" 
                    viewBox="0 0 20 20" 
                    fill="currentColor"
                  >
                    <path 
                      fillRule="evenodd" 
                      d="M10.293 5.293a1 1 0 011.414 0l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414-1.414L12.586 11H5a1 1 0 110-2h7.586l-2.293-2.293a1 1 0 010-1.414z" 
                      clipRule="evenodd" 
                    />
                  </svg>
                </Link>
              </div>
            </div>
          </div>
          
          {/* Quick Links */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Link 
              to="/gifts-travel" 
              className="bg-gradient-to-r from-pink-500 to-purple-500 p-4 rounded-lg shadow text-white hover:from-pink-600 hover:to-purple-600 transition-colors"
            >
              <h3 className="text-lg font-semibold mb-2">Travel Analysis</h3>
              <p>Explore patterns in travel benefits and sponsorships received by MPs.</p>
            </Link>
            
            <Link 
              to="/entities" 
              className="bg-gradient-to-r from-blue-500 to-teal-500 p-4 rounded-lg shadow text-white hover:from-blue-600 hover:to-teal-600 transition-colors"
            >
              <h3 className="text-lg font-semibold mb-2">Entity Network</h3>
              <p>Discover connections between MPs and organizations through their disclosed relationships.</p>
            </Link>
            
            <Link 
              to="/geographic" 
              className="bg-gradient-to-r from-amber-500 to-orange-500 p-4 rounded-lg shadow text-white hover:from-amber-600 hover:to-orange-600 transition-colors"
            >
              <h3 className="text-lg font-semibold mb-2">Asset Explorer</h3>
              <p>View asset disclosure patterns across Australian Members of Parliament.</p>
            </Link>
          </div>
        </>
      )}
    </div>
  );
};

export default Home; 