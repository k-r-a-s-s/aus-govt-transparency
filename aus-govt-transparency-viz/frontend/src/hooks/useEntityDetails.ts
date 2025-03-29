import { useQuery } from '@tanstack/react-query';
import { fetchEntityDetails, EntityDetails } from '../services/api';

interface UseEntityDetailsProps {
  entityName: string;
  useCanonical?: boolean;
  enabled?: boolean;
  refetchOnWindowFocus?: boolean;
}

/**
 * Custom hook to fetch details about a specific entity
 * 
 * @param options Parameters and options for the hook
 * @returns Query result with entity details
 */
export const useEntityDetails = (options: UseEntityDetailsProps) => {
  const { 
    entityName,
    useCanonical = false,
    enabled = !!entityName, // Only enable when there's an entity name
    refetchOnWindowFocus = false
  } = options;
  
  // Prepare query key based on parameters
  const queryKey = ['entityDetails', entityName, { canonical: useCanonical }];
  
  // Use React Query to fetch and cache data
  return useQuery<EntityDetails>({
    queryKey,
    queryFn: async () => fetchEntityDetails(entityName, { canonical: useCanonical }),
    enabled,
    refetchOnWindowFocus,
    staleTime: 5 * 60 * 1000, // Consider data fresh for 5 minutes
  });
};

export default useEntityDetails; 