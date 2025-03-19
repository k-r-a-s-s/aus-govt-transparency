import { 
  DisclosureData, 
  DisclosureStats,
  DisclosureQueryParams,
  MP,
  APIResponse,
  APIError
} from '../types';

// Get API URL from environment variable
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3001/api';

// Flag to determine whether to use mock data (for development)
const USE_MOCK_DATA = false;

// Mock data for development
const MOCK_DISCLOSURES: DisclosureData[] = Array.from({ length: 50 }, (_, i) => ({
  id: i,
  mp_name: ['Jane Smith', 'John Doe', 'Sarah Connor', 'Thomas Anderson', 'Alex Johnson'][Math.floor(Math.random() * 5)],
  party: ['Labor', 'Liberal', 'Greens', 'Independent'][Math.floor(Math.random() * 4)],
  electorate: ['Sydney', 'Melbourne', 'Brisbane', 'Perth', 'Adelaide'][Math.floor(Math.random() * 5)],
  category: ['Gift', 'Travel', 'Asset', 'Income', 'Liability'][Math.floor(Math.random() * 5)],
  item: `Item ${i}`,
  entity: ['Company A', 'Organization B', 'Corporation C', 'Foundation D'][Math.floor(Math.random() * 4)],
  declaration_date: new Date(2022, Math.floor(Math.random() * 12), Math.floor(Math.random() * 28) + 1).toISOString(),
  parliament_id: 46
}));

const MOCK_STATS: DisclosureStats = {
  total_disclosures: 543,
  total_mps: 150,
  total_entities: 320,
  disclosures_by_category: {
    'Gift': 120,
    'Travel': 95,
    'Asset': 180,
    'Income': 78,
    'Liability': 70
  },
  disclosures_by_party: {
    'Labor': 240,
    'Liberal': 230,
    'Greens': 50,
    'Independent': 23
  },
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
      const response: APIResponse<DisclosureData[]> = {
        data: MOCK_DISCLOSURES
      };
      return response as unknown as T;
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
): Promise<APIResponse<DisclosureData[]>> => {
  return fetchApi<APIResponse<DisclosureData[]>>('disclosures', undefined, params);
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
): Promise<{ mp: MP; disclosures: DisclosureData[] }> => {
  return fetchApi<{ mp: MP; disclosures: DisclosureData[] }>(
    `mps/${encodeURIComponent(mpName)}`
  );
};

/**
 * Fetch all MPs
 */
export const fetchMPs = async (
  params?: { party?: string; electorate?: string }
): Promise<MP[]> => {
  return fetchApi<MP[]>('mps', undefined, params);
};

/**
 * Fetch entities (organizations, individuals) mentioned in disclosures
 */
export const fetchEntities = async (
  params?: { name?: string; limit?: number; offset?: number }
): Promise<{ name: string; count: number }[]> => {
  return fetchApi<{ name: string; count: number }[]>('entities', undefined, params);
};

/**
 * Fetch gifts data for analysis
 */
export const fetchGiftsData = async (): Promise<DisclosureData[]> => {
  return fetchApi<DisclosureData[]>('disclosures', undefined, { 
    category: 'Gift',
    limit: 1000 
  });
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
  params?: { mp_name?: string; entity?: string; limit?: number }
): Promise<{ nodes: any[]; links: any[] }> => {
  return fetchApi<{ nodes: any[]; links: any[] }>('network', undefined, params);
};

/**
 * Fetch disclosure timeline data
 */
export const fetchTimelineData = async (
  params?: { 
    mp_name?: string; 
    category?: string;
    from_date?: string;
    to_date?: string;
  }
): Promise<{ date: string; count: number }[]> => {
  return fetchApi<{ date: string; count: number }[]>('timeline', undefined, params);
}; 