import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchMPs } from '../../services/api';
import { MP } from '../../types';
import { debounce } from 'lodash'; // Make sure to install lodash if not already present

const MPSearch: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [mps, setMPs] = useState<MP[]>([]);
  const [filteredMPs, setFilteredMPs] = useState<MP[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  // Fetch MPs on component mount
  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const data = await fetchMPs();
        setMPs(data);
      } catch (err) {
        setError('Failed to load MPs');
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, []);

  // Filter MPs based on search term
  useEffect(() => {
    if (!searchTerm.trim()) {
      setFilteredMPs([]);
      return;
    }

    const lowerSearchTerm = searchTerm.toLowerCase();
    const filtered = mps
      .filter(mp => 
        mp.mp_name.toLowerCase().includes(lowerSearchTerm) || 
        (mp.party && mp.party.toLowerCase().includes(lowerSearchTerm)) ||
        (mp.electorate && mp.electorate.toLowerCase().includes(lowerSearchTerm))
      )
      .slice(0, 10); // Limit to 10 results for better UX
    
    setFilteredMPs(filtered);
  }, [searchTerm, mps]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  // Debounce search input to prevent excessive filtering
  const handleSearchChange = debounce((value: string) => {
    setSearchTerm(value);
    setIsOpen(!!value);
  }, 300);

  // Handle MP selection
  const handleMPSelect = (mp: MP) => {
    navigate(`/mp/${encodeURIComponent(mp.mp_name)}`);
    setIsOpen(false);
    setSearchTerm('');
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <div className="relative">
        <input
          type="text"
          placeholder="Search for an MP..."
          onChange={(e) => handleSearchChange(e.target.value)}
          onFocus={() => searchTerm && setIsOpen(true)}
          className="block w-full bg-gray-700 border border-gray-600 rounded-md py-1.5 pl-3 pr-10 text-sm text-white placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
        />
        {isLoading && (
          <span className="absolute inset-y-0 right-0 flex items-center pr-2">
            <span className="animate-spin h-4 w-4 border-t-2 border-blue-500 rounded-full"></span>
          </span>
        )}
      </div>

      {isOpen && filteredMPs.length > 0 && (
        <div className="absolute z-10 mt-1 w-full bg-white rounded-md shadow-lg max-h-60 overflow-auto">
          <ul className="py-1">
            {filteredMPs.map((mp) => (
              <li
                key={mp.mp_name}
                className="cursor-pointer hover:bg-gray-100 px-4 py-2 text-sm text-gray-700"
                onClick={() => handleMPSelect(mp)}
              >
                <div className="font-medium">{mp.mp_name}</div>
                <div className="text-xs text-gray-500">
                  {mp.party}{mp.electorate ? ` • ${mp.electorate}` : ''}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {isOpen && searchTerm && filteredMPs.length === 0 && !isLoading && (
        <div className="absolute z-10 mt-1 w-full bg-white rounded-md shadow-lg p-4 text-center text-sm text-gray-500">
          No MPs found matching "{searchTerm}"
        </div>
      )}

      {error && (
        <div className="absolute z-10 mt-1 w-full bg-red-50 rounded-md shadow-lg p-4 text-center text-sm text-red-500">
          {error}
        </div>
      )}
    </div>
  );
};

export default MPSearch; 