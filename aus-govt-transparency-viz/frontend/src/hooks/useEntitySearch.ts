import { useQuery } from '@tanstack/react-query';
import { searchEntities } from '../services/api';

interface UseEntitySearchProps {
  searchTerm: string;
  limit?: number;
  useCanonical?: boolean;
  enabled?: boolean;
  refetchOnWindowFocus?: boolean;
}

/**
 * Custom hook to search for entities
 * 
 * @param options Search parameters and options for the hook
 * @returns Query result with entity search results
 */
export const useEntitySearch = (options: UseEntitySearchProps) => {
  const { 
    searchTerm,
    limit = 20,
    useCanonical = false,
    enabled = !!searchTerm, // Only enable when there's a search term
    refetchOnWindowFocus = false
  } = options;
  
  // Prepare query key based on parameters
  const queryKey = ['entitySearch', searchTerm, { limit, canonical: useCanonical }];
  
  // Use React Query to fetch and cache data
  return useQuery({
    queryKey,
    queryFn: async () => searchEntities(searchTerm, { limit, canonical: useCanonical }),
    enabled,
    refetchOnWindowFocus,
    staleTime: 5 * 60 * 1000, // Consider data fresh for 5 minutes
  });
};

export default useEntitySearch; 