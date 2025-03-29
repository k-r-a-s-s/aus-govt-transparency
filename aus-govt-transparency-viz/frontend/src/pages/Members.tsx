import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchMPs } from '../services/api';
import { MP } from '../types';

const Members: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [partyFilter, setPartyFilter] = useState<string>('');
  const [blocFilter, setBlocFilter] = useState<string>('');
  
  // Fetch all MPs
  const { data: mps, isLoading, error } = useQuery({
    queryKey: ['mps'],
    queryFn: fetchMPs,
  });
  
  // Extract unique parties for filtering
  const parties = useMemo(() => {
    if (!mps) return [];
    
    const partySet = new Set<string>();
    mps.forEach(mp => {
      if (mp.party) {
        partySet.add(mp.party);
      }
    });
    
    return Array.from(partySet).sort();
  }, [mps]);
  
  // Extract unique political blocs for filtering
  const blocs = useMemo(() => {
    if (!mps) return [];
    
    const blocSet = new Set<string>();
    mps.forEach(mp => {
      if (mp.political_bloc) {
        blocSet.add(mp.political_bloc);
      }
    });
    
    return Array.from(blocSet).sort();
  }, [mps]);
  
  // Filter MPs based on search term, party filter, and bloc filter
  const filteredMPs = useMemo(() => {
    if (!mps) return [];
    
    return mps.filter(mp => {
      const matchesSearch = searchTerm 
        ? mp.mp_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
          (mp.electorate && mp.electorate.toLowerCase().includes(searchTerm.toLowerCase()))
        : true;
        
      const matchesParty = partyFilter
        ? mp.party === partyFilter
        : true;
        
      const matchesBloc = blocFilter
        ? mp.political_bloc === blocFilter
        : true;
        
      return matchesSearch && matchesParty && matchesBloc;
    });
  }, [mps, searchTerm, partyFilter, blocFilter]);
  
  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-800 p-4 rounded-md">
        <h3 className="text-lg font-semibold">Error Loading Members</h3>
        <p>{error instanceof Error ? error.message : 'Failed to load members'}</p>
      </div>
    );
  }
  
  return (
    <div className="members-page">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-800">Members of Parliament</h1>
        <p className="text-gray-600 mt-2">
          Browse and search for MPs to view their financial disclosure records.
        </p>
      </div>
      
      {/* Filters */}
      <div className="bg-white p-6 rounded-lg shadow mb-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label htmlFor="search" className="block text-sm font-medium text-gray-700 mb-1">
              Search MPs
            </label>
            <input
              type="text"
              id="search"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by name or electorate"
              className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
            />
          </div>
          
          <div>
            <label htmlFor="party-filter" className="block text-sm font-medium text-gray-700 mb-1">
              Filter by Party
            </label>
            <select
              id="party-filter"
              value={partyFilter}
              onChange={(e) => setPartyFilter(e.target.value)}
              className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
            >
              <option value="">All Parties</option>
              {parties.map(party => (
                <option key={party} value={party}>{party}</option>
              ))}
            </select>
          </div>
          
          <div>
            <label htmlFor="bloc-filter" className="block text-sm font-medium text-gray-700 mb-1">
              Filter by Political Bloc
            </label>
            <select
              id="bloc-filter"
              value={blocFilter}
              onChange={(e) => setBlocFilter(e.target.value)}
              className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
            >
              <option value="">All Political Blocs</option>
              {blocs.map(bloc => (
                <option key={bloc} value={bloc}>{bloc}</option>
              ))}
            </select>
          </div>
        </div>
      </div>
      
      {/* Results */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="p-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-700">
            {filteredMPs.length} {filteredMPs.length === 1 ? 'Member' : 'Members'} Found
          </h2>
        </div>
        
        {filteredMPs.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 p-4">
            {filteredMPs.map(mp => (
              <Link 
                key={mp.mp_name} 
                to={`/mp/${encodeURIComponent(mp.mp_name)}`}
                className="block border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors p-4"
              >
                <div className="flex items-start space-x-4">
                  <div className="flex-shrink-0 bg-gray-200 h-12 w-12 rounded-full flex items-center justify-center text-gray-600">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zm-4 7a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="font-medium text-gray-900">{mp.mp_name}</h3>
                    <div className="text-sm text-gray-500">
                      {mp.party && <span className="block">{mp.party}</span>}
                      {mp.political_bloc && mp.party !== mp.political_bloc && (
                        <span className="block text-xs text-gray-400">Bloc: {mp.political_bloc}</span>
                      )}
                      {mp.electorate && <span className="block">{mp.electorate}</span>}
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className="p-8 text-center text-gray-500">
            No members found matching your search criteria.
          </div>
        )}
      </div>
    </div>
  );
};

export default Members; 