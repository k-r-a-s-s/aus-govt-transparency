import { useQuery } from '@tanstack/react-query';
import { NetworkData } from '../types';
import { fetchNetworkData } from '../services/api';

interface UseNetworkDataProps {
  mp?: string;
  entity?: string;
  useCanonical?: boolean;
  enabled?: boolean;
  refetchOnWindowFocus?: boolean;
}

/**
 * Custom hook to fetch and manage network data for entity visualization
 * 
 * @param options Query parameters and options for the hook
 * @returns Query result with network data
 */
export const useNetworkData = (options: UseNetworkDataProps = {}) => {
  const { 
    enabled = true, 
    refetchOnWindowFocus = false,
    mp,
    entity,
    useCanonical = false
  } = options;
  
  // Prepare query key based on parameters
  const queryKey = ['network', { mp, entity, canonical: useCanonical }];
  
  // Use React Query to fetch and cache data
  return useQuery({
    queryKey,
    queryFn: async () => fetchNetworkData({ mp, entity, canonical: useCanonical }),
    enabled,
    refetchOnWindowFocus,
    staleTime: 5 * 60 * 1000, // Consider data fresh for 5 minutes
  });
};

export default useNetworkData; 