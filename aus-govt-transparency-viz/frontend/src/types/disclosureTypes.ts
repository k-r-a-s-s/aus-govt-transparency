/**
 * Disclosure item from the API
 */
export interface DisclosureData {
  id: string;
  mp_name: string;
  party: string;
  electorate: string;
  declaration_date: string;
  category: string;
  sub_category: string;
  item: string;
  temporal_type: string;
  start_date: string;
  end_date: string;
  details: string;
  pdf_url: string;
  entity_id: string;
  entity: string;
}

/**
 * Statistics about disclosure data
 */
export interface DisclosureStats {
  categories: Array<{ category: string; count: number }>;
  parties: Array<{ party: string; count: number }>;
  years: Array<{ year: string; count: number }>;
  topMPs: Array<{ mp_name: string; count: number }>;
  categoryByParty: Array<{ category: string; party: string; count: number }>;
  gifts: Array<{ type: string; count: number }>;
  assets: Array<{ type: string; count: number }>;
}

/**
 * Gift data for analysis
 */
export interface GiftData extends DisclosureData {
  // Additional gift-specific fields
}

/**
 * Asset data for analysis
 */
export interface AssetData extends DisclosureData {
  // Additional asset-specific fields
}

/**
 * Pagination response from API
 */
export interface PaginatedResponse<T> {
  data: T[];
  pagination: {
    total: number;
    limit: number;
    offset: number;
    pages: number;
  };
}

/**
 * Filter parameters for disclosures
 */
export interface DisclosureFilters {
  mp_name?: string;
  party?: string;
  electorate?: string;
  category?: string;
  entity?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
} 