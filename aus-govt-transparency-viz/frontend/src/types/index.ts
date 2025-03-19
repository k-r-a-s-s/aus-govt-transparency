// MP data types
export interface MP {
  id: number;
  mp_name: string;
  party?: string;
  electorate?: string;
}

// Disclosure data types
export interface DisclosureData {
  id: number;
  mp_name: string;
  party?: string;
  electorate?: string;
  category: string;
  item: string;
  entity?: string;
  declaration_date: string;
  parliament_id: number;
}

// Type for disclosure statistics
export interface DisclosureStats {
  total_disclosures: number;
  total_mps: number;
  total_entities: number;
  disclosures_by_category: Record<string, number>;
  disclosures_by_party: Record<string, number>;
  top_mps: Array<{
    mp_name: string;
    count: number;
    party?: string;
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
  value: number;
  category?: string;
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
  mp_name?: string;
  category?: string;
  party?: string;
  electorate?: string;
  entity?: string;
  from_date?: string;
  to_date?: string;
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

// Dashboard data type
export interface DashboardData {
  recentDisclosures: DisclosureData[];
  stats: DisclosureStats;
  timeline: {
    date: string;
    count: number;
  }[];
} 