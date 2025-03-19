import { useQuery } from '@tanstack/react-query';
import { DisclosureData, DisclosureQueryParams } from '../types';
import { fetchDisclosures } from '../services/api';

interface UseDisclosureDataProps extends DisclosureQueryParams {
  // Additional options that apply to the custom hook
  enabled?: boolean;
  refetchOnWindowFocus?: boolean;
}

/**
 * Custom hook to fetch and manage disclosure data
 * 
 * @param options Query parameters and options for the hook
 * @returns Query result with disclosure data
 */
export const useDisclosureData = (options: UseDisclosureDataProps = {}) => {
  const { 
    enabled = true, 
    refetchOnWindowFocus = false,
    ...queryParams 
  } = options;
  
  // Prepare query key based on all parameters
  const queryKey = ['disclosures', queryParams];
  
  // Use React Query to fetch and cache data
  return useQuery({
    queryKey,
    queryFn: async () => fetchDisclosures(queryParams),
    enabled,
    refetchOnWindowFocus,
    staleTime: 5 * 60 * 1000, // Consider data fresh for 5 minutes
  });
};

// Also export as default for backward compatibility
export default useDisclosureData; 