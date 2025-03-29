import { 
  DisclosureData, 
  DisclosureStats,
  DisclosureQueryParams,
  MP,
  APIError,
  NetworkData,
  TimelineData
} from '../types';

// Get API URL from environment variable
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3001/api';

// Flag to determine whether to use mock data (for development)
const USE_MOCK_DATA = false;

// Mock data for development
const MOCK_DISCLOSURES: DisclosureData[] = Array.from({ length: 50 }, (_, i) => ({
  id: `${i}`,
  mp_name: ['Jane Smith', 'John Doe', 'Sarah Connor', 'Thomas Anderson', 'Alex Johnson'][Math.floor(Math.random() * 5)],
  party: ['Labor', 'Liberal', 'Greens', 'Independent'][Math.floor(Math.random() * 4)],
  electorate: ['Sydney', 'Melbourne', 'Brisbane', 'Perth', 'Adelaide'][Math.floor(Math.random() * 5)],
  category: ['Gift', 'Travel', 'Asset', 'Income', 'Liability'][Math.floor(Math.random() * 5)],
  item: `Item ${i}`,
  entity: ['Company A', 'Organization B', 'Corporation C', 'Foundation D'][Math.floor(Math.random() * 4)],
  declaration_date: new Date(2022, Math.floor(Math.random() * 12), Math.floor(Math.random() * 28) + 1).toISOString()
}));

const MOCK_STATS: DisclosureStats = {
  total_disclosures: 543,
  total_mps: 150,
  total_entities: 320,
  categories: [
    { category: 'Gift', count: 120 },
    { category: 'Travel', count: 95 },
    { category: 'Asset', count: 180 },
    { category: 'Income', count: 78 },
    { category: 'Liability', count: 70 }
  ],
  top_mps: [
    { mp_name: 'Jane Smith', count: 32, party: 'Labor' },
    { mp_name: 'John Doe', count: 28, party: 'Liberal' },
    { mp_name: 'Sarah Connor', count: 22, party: 'Greens' },
    { mp_name: 'Thomas Anderson', count: 19, party: 'Labor' },
    { mp_name: 'Alex Johnson', count: 17, party: 'Independent' }
  ]
};

/**
 * Helper function to build URL with query parameters
 */
const buildUrl = (endpoint: string, params?: Record<string, any>): string => {
  const url = new URL(`${API_URL}/${endpoint}`);
  
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.append(key, String(value));
      }
    });
  }
  
  return url.toString();
};

/**
 * Generic fetch function with error handling
 */
const fetchApi = async <T>(
  endpoint: string, 
  options?: RequestInit,
  params?: Record<string, any>
): Promise<T> => {
  // If using mock data, return appropriate mock responses
  if (USE_MOCK_DATA) {
    if (endpoint === 'disclosures') {
      return MOCK_DISCLOSURES as unknown as T;
    }
    
    if (endpoint === 'stats') {
      return MOCK_STATS as unknown as T;
    }
    
    // Add more mock endpoints as needed
  }

  try {
    const url = buildUrl(endpoint, params);
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
      },
      ...options,
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw {
        status: response.status,
        message: errorData.message || 'An error occurred',
      } as APIError;
    }

    return await response.json() as T;
  } catch (error) {
    if ((error as APIError).status) {
      throw error;
    }
    throw {
      status: 500,
      message: (error as Error).message || 'Network error',
    } as APIError;
  }
};

/**
 * Fetch disclosure data with optional filters
 */
export const fetchDisclosures = async (
  params?: DisclosureQueryParams
): Promise<DisclosureData[]> => {
  return fetchApi<DisclosureData[]>('disclosures', undefined, params);
};

/**
 * Fetch disclosure statistics
 */
export const fetchDisclosureStats = async (): Promise<DisclosureStats> => {
  return fetchApi<DisclosureStats>('stats');
};

/**
 * Fetch MP details including their disclosures
 */
export const fetchMPDetails = async (
  mpName: string
): Promise<MP & { disclosures: DisclosureData[], categories: any[], entities: any[] }> => {
  return fetchApi<MP & { disclosures: DisclosureData[], categories: any[], entities: any[] }>(
    `mp/${encodeURIComponent(mpName)}`
  );
};

/**
 * Fetch all MPs
 */
export const fetchMPs = async (
  params?: { name?: string; party?: string }
): Promise<MP[]> => {
  return fetchApi<MP[]>('mps', undefined, params);
};

/**
 * Fetch entities (organizations, individuals) mentioned in disclosures
 */
export const fetchEntities = async (
  params?: { name?: string; limit?: number; canonical?: boolean }
): Promise<{ entity: string; count: number }[]> => {
  return fetchApi<{ entity: string; count: number }[]>('entities', undefined, params);
};

/**
 * Fetch travel data for analysis
 */
export const fetchTravelData = async (): Promise<DisclosureData[]> => {
  return fetchApi<DisclosureData[]>('disclosures', undefined, { 
    category: 'Travel',
    limit: 1000 
  });
};

/**
 * Fetch network data for entity explorer
 */
export const fetchNetworkData = async (
  params?: { mp?: string; entity?: string; canonical?: boolean }
): Promise<NetworkData> => {
  if (USE_MOCK_DATA) {
    // Generate mock network data
    const mockMPs = [
      { name: 'Jane Smith', party: 'Labor' },
      { name: 'John Doe', party: 'Liberal' },
      { name: 'Sarah Connor', party: 'Greens' },
      { name: 'Thomas Anderson', party: 'Labor' },
      { name: 'Alex Johnson', party: 'Independent' }
    ];
    
    const mockEntities = [
      'Acme Corporation',
      'Global Industries',
      'Tech Solutions Inc',
      'Legal & General',
      'Finance Partners',
      'Media Group',
      'Energy Enterprises'
    ];
    
    // Create nodes
    const nodes = [
      // MP nodes
      ...mockMPs.map(mp => ({
        id: `mp-${mp.name}`,
        name: mp.name,
        type: 'mp' as const,
        party: mp.party,
        size: Math.floor(Math.random() * 5) + 1
      })),
      
      // Entity nodes
      ...mockEntities.map(entity => ({
        id: `entity-${entity}`,
        name: entity,
        type: 'entity' as const,
        size: Math.floor(Math.random() * 5) + 1
      }))
    ];
    
    // Create links
    const links = [];
    for (let i = 0; i < 20; i++) {
      const mp = mockMPs[Math.floor(Math.random() * mockMPs.length)];
      const entity = mockEntities[Math.floor(Math.random() * mockEntities.length)];
      
      links.push({
        source: `mp-${mp.name}`,
        target: `entity-${entity}`,
        weight: Math.floor(Math.random() * 3) + 1
      });
    }
    
    return { nodes, links };
  }
  
  return fetchApi<NetworkData>('network', undefined, params);
};

/**
 * Fetch disclosure timeline data
 */
export const fetchTimelineData = async (): Promise<TimelineData> => {
  return fetchApi<TimelineData>('timeline');
};

/**
 * Entity details including variants and connected MPs
 */
export interface EntityDetails {
  entity: string;
  count: number;
  variants: string[];
  connected_mps: {
    mp_name: string;
    party: string;
    electorate: string;
    political_bloc: string;
  }[];
}

/**
 * Fetch details about a specific entity
 */
export const fetchEntityDetails = async (
  entityName: string,
  params?: { canonical?: boolean }
): Promise<EntityDetails> => {
  return fetchApi<EntityDetails>(`entity/${encodeURIComponent(entityName)}`, undefined, params);
};

/**
 * Search for entities by name
 */
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