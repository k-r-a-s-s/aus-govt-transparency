/**
 * Disclosure item as stored in the database
 */
export interface Disclosure {
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
 * Filters for querying disclosures
 */
export interface DisclosureFilters {
  mp_name?: string;
  party?: string;
  electorate?: string;
  category?: string;
  entity?: string;
  start_date?: string;
  end_date?: string;
}

/**
 * Pagination information for disclosure results
 */
export interface DisclosurePagination {
  total: number;
  limit: number;
  offset: number;
  pages: number;
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
 * Entity information
 */
export interface Entity {
  id: string;
  entity_type: string;
  canonical_name: string;
  first_appearance_date: string;
  last_appearance_date: string;
  is_active: boolean;
  confidence_score: number;
  mp_id: string;
  notes: string;
}

/**
 * Relationship between MP and entity
 */
export interface Relationship {
  relationship_id: string;
  mp_name: string;
  entity: string;
  relationship_type: string;
  value: string;
  date_logged: string;
} 