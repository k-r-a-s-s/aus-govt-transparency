// MP data types
export interface MP {
  mp_name: string;
  party?: string;
  electorate?: string;
}

// Disclosure data types
export interface DisclosureData {
  id: string;
  mp_name: string;
  party?: string;
  electorate?: string;
  category: string;
  item?: string;
  entity?: string;
  entity_id?: string;
  declaration_date: string;
  details?: string;
  sub_category?: string;
  temporal_type?: string;
  start_date?: string;
  end_date?: string;
  pdf_url?: string;
}

// Type for disclosure statistics
export interface DisclosureStats {
  total_disclosures: number;
  total_mps: number;
  total_entities: number;
  categories: Array<{
    category: string;
    count: number;
  }>;
  top_mps: Array<{
    mp_name: string;
    party?: string;
    count: number;
  }>;
}

// Type for network data
export interface NetworkNode {
  id: string;
  name: string;
  type: 'mp' | 'entity';
  party?: string;
  size?: number;
}

export interface NetworkLink {
  source: string;
  target: string;
  weight: number;
}

export interface NetworkData {
  nodes: NetworkNode[];
  links: NetworkLink[];
}

// Type for gift analysis data
export interface GiftData {
  type: string;
  count: number;
  value?: number;
}

export interface GiftProvider {
  provider: string;
  count: number;
}

export interface GiftsByParty {
  party: string;
  count: number;
}

export interface GiftAnalysisData {
  byType: GiftData[];
  byProvider: GiftProvider[];
  byParty: GiftsByParty[];
  mostCommon: {
    type: string;
    provider: string;
    party: string;
  };
}

// API query parameters types
export interface DisclosureQueryParams {
  limit?: number;
  offset?: number;
  mp?: string;
  category?: string;
  party?: string;
  entity?: string;
}

// API response types
export interface APIResponse<T> {
  data: T;
  meta?: {
    total: number;
    limit: number;
    offset: number;
  };
}

// Error types
export interface APIError {
  status: number;
  message: string;
}

// Timeline data type
export interface TimelineData {
  timeline: Array<{
    month: string;
    count: number;
  }>;
  categories: Array<{
    month: string;
    category: string;
    count: number;
  }>;
}

// Dashboard data type
export interface DashboardData {
  recentDisclosures: DisclosureData[];
  stats: DisclosureStats;
  timeline: TimelineData;
} 