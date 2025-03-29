# Frontend Services

The frontend services layer in the Australian Government Transparency Project provides a structured way to interact with the API, implementing data fetching, caching, and transformation logic.

## API Service

The API service provides functions for interacting with the backend API endpoints. These functions handle error handling, request formatting, and result parsing.

### Base URL Configuration

The API service is configured with the base URL for API requests:

```typescript
// Default to localhost for development
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:3001/api';
```

### API Request Helper

The `fetchApi` helper function handles common API request logic:

```typescript
const fetchApi = async <T>(
  endpoint: string, 
  options?: RequestInit,
  params?: Record<string, any>
): Promise<T> => {
  const url = buildUrl(endpoint, params);
  
  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error(`Error fetching ${url}:`, error);
    throw error;
  }
};
```

## Key API Services

### Disclosure Service

Functions for fetching disclosure data:

```typescript
export const fetchDisclosures = async (
  params?: DisclosureQueryParams
): Promise<DisclosureData[]> => {
  return fetchApi<DisclosureData[]>('disclosures', undefined, params);
};
```

### MP Service

Functions for fetching MP data:

```typescript
export const fetchMPs = async (
  params?: { name?: string; party?: string }
): Promise<MP[]> => {
  return fetchApi<MP[]>('mps', undefined, params);
};

export const fetchMPDetails = async (
  mpName: string
): Promise<MP & { disclosures: DisclosureData[], categories: any[], entities: any[] }> => {
  return fetchApi<any>(`mp/${encodeURIComponent(mpName)}`);
};
```

### Entity Service

Functions for working with entities, including support for canonical entity names:

```typescript
export const fetchEntities = async (
  params?: { name?: string; limit?: number; canonical?: boolean }
): Promise<{ entity: string; count: number }[]> => {
  return fetchApi<{ entity: string; count: number }[]>('entities', undefined, params);
};

export const fetchEntityDetails = async (
  entityName: string,
  params?: { canonical?: boolean }
): Promise<EntityDetails> => {
  return fetchApi<EntityDetails>(`entity/${encodeURIComponent(entityName)}`, undefined, params);
};

export const searchEntities = async (
  searchTerm: string,
  params?: { limit?: number; canonical?: boolean }
): Promise<{ entity: string; count: number }[]> => {
  return fetchApi<{ entity: string; count: number }[]>(
    'search/entities', 
    undefined, 
    { q: searchTerm, ...params }
  );
};
```

### Network Service

Functions for working with network data:

```typescript
export const fetchNetworkData = async (
  params?: { mp?: string; entity?: string; canonical?: boolean }
): Promise<NetworkData> => {
  return fetchApi<NetworkData>('network', undefined, params);
};
```

## React Query Hooks

The application uses React Query for data fetching and caching. Custom hooks wrap the API service functions.

### useDisclosureData

Hook for fetching disclosure data:

```typescript
export const useDisclosureData = (options: UseDisclosureDataProps = {}) => {
  const { 
    enabled = true, 
    refetchOnWindowFocus = false,
    ...queryParams
  } = options;
  
  const queryKey = ['disclosures', queryParams];
  
  return useQuery({
    queryKey,
    queryFn: async () => fetchDisclosures(queryParams),
    enabled,
    refetchOnWindowFocus,
    staleTime: 5 * 60 * 1000, // Consider data fresh for 5 minutes
  });
};
```

### useEntitySearch

Hook for searching entities with canonical entity support:

```typescript
export const useEntitySearch = (options: UseEntitySearchProps) => {
  const { 
    searchTerm,
    limit = 20,
    useCanonical = false,
    enabled = !!searchTerm,
    refetchOnWindowFocus = false
  } = options;
  
  const queryKey = ['entitySearch', searchTerm, { limit, canonical: useCanonical }];
  
  return useQuery({
    queryKey,
    queryFn: async () => searchEntities(searchTerm, { limit, canonical: useCanonical }),
    enabled,
    refetchOnWindowFocus,
    staleTime: 5 * 60 * 1000,
  });
};
```

### useEntityDetails

Hook for fetching entity details with canonical entity support:

```typescript
export const useEntityDetails = (options: UseEntityDetailsProps) => {
  const { 
    entityName,
    useCanonical = false,
    enabled = !!entityName,
    refetchOnWindowFocus = false
  } = options;
  
  const queryKey = ['entityDetails', entityName, { canonical: useCanonical }];
  
  return useQuery<EntityDetails>({
    queryKey,
    queryFn: async () => fetchEntityDetails(entityName, { canonical: useCanonical }),
    enabled,
    refetchOnWindowFocus,
    staleTime: 5 * 60 * 1000,
  });
};
```

### useNetworkData

Hook for fetching network data with canonical entity support:

```typescript
export const useNetworkData = (options: UseNetworkDataProps = {}) => {
  const { 
    enabled = true, 
    refetchOnWindowFocus = false,
    mp,
    entity,
    useCanonical = false
  } = options;
  
  const queryKey = ['network', { mp, entity, canonical: useCanonical }];
  
  return useQuery({
    queryKey,
    queryFn: async () => fetchNetworkData({ mp, entity, canonical: useCanonical }),
    enabled,
    refetchOnWindowFocus,
    staleTime: 5 * 60 * 1000,
  });
};
```

## Data Transformation Utilities

The services layer also includes utility functions for data transformation:

### formatDate

```typescript
export const formatDate = (dateString: string): string => {
  if (!dateString) return 'Unknown Date';
  
  const date = new Date(dateString);
  return date.toLocaleDateString('en-AU', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  });
};
```

### transformToNetworkData

```typescript
export const transformToNetworkData = (
  disclosures: DisclosureData[],
  filterMPName?: string,
  filterEntity?: string
): NetworkData => {
  // Implementation details omitted for brevity
  // This function transforms disclosure data into nodes and links
};
```

## Example Usage

Here's an example of using the services in a React component:

```tsx
import { useNetworkData } from '../hooks/useNetworkData';
import { useEntityDetails } from '../hooks/useEntityDetails';

const EntityExplorer: React.FC = () => {
  const [selectedEntity, setSelectedEntity] = useState<string | null>(null);
  const [useCanonical, setUseCanonical] = useState(true);
  
  // Fetch network data
  const { data: networkData } = useNetworkData({
    entity: selectedEntity || undefined,
    useCanonical
  });
  
  // Fetch entity details when an entity is selected
  const { data: entityDetails } = useEntityDetails({
    entityName: selectedEntity || '',
    useCanonical,
    enabled: !!selectedEntity
  });
  
  // Component implementation...
};
```

## Error Handling

The services layer includes standardized error handling:

1. API errors are caught and logged
2. React Query hooks expose `isError` and `error` states
3. Components can display appropriate error messages

## Caching Strategy

React Query provides a robust caching strategy:

1. Data is cached for 5 minutes by default (staleTime)
2. Refetching on window focus is disabled by default
3. Query keys ensure proper cache invalidation

## Conclusion

The services layer provides a clean, type-safe interface to the API, with full support for the entity deduplication feature through the `canonical` parameters and specialized hooks. 