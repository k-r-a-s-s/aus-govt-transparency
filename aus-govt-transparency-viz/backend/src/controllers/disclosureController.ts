import { getConnection } from '../models/database';
import { DisclosureFilters, DisclosurePagination, DisclosureStats } from '../types/disclosures';

/**
 * Get disclosures with filtering and pagination
 */
export async function getDisclosures(params: any): Promise<{ 
  data: any[]; 
  pagination: DisclosurePagination;
}> {
  const db = getConnection();
  
  // Extract filter parameters with defaults
  const filters: DisclosureFilters = {
    mp_name: params.mp_name as string,
    party: params.party as string,
    electorate: params.electorate as string,
    category: params.category as string,
    entity: params.entity as string,
    start_date: params.start_date as string,
    end_date: params.end_date as string,
  };
  
  // Extract pagination parameters
  const limit = params.limit ? parseInt(params.limit as string, 10) : 100;
  const offset = params.offset ? parseInt(params.offset as string, 10) : 0;
  
  // Build query dynamically
  let query = 'SELECT * FROM disclosures WHERE 1=1';
  const queryParams: any[] = [];
  
  // Add filter conditions
  if (filters.mp_name) {
    query += ' AND mp_name = ?';
    queryParams.push(filters.mp_name);
  }
  
  if (filters.party) {
    query += ' AND party = ?';
    queryParams.push(filters.party);
  }
  
  if (filters.electorate) {
    query += ' AND electorate = ?';
    queryParams.push(filters.electorate);
  }
  
  if (filters.category) {
    query += ' AND category = ?';
    queryParams.push(filters.category);
  }
  
  if (filters.entity) {
    query += ' AND entity LIKE ?';
    queryParams.push(`%${filters.entity}%`);
  }
  
  if (filters.start_date) {
    query += ' AND declaration_date >= ?';
    queryParams.push(filters.start_date);
  }
  
  if (filters.end_date) {
    query += ' AND declaration_date <= ?';
    queryParams.push(filters.end_date);
  }
  
  // Get total count for pagination info (before applying limit/offset)
  const countQuery = query.replace('SELECT *', 'SELECT COUNT(*) as total');
  const totalCount = await db.get<{ total: number }>(countQuery, queryParams);
  
  // Add pagination to main query
  query += ' ORDER BY declaration_date DESC LIMIT ? OFFSET ?';
  queryParams.push(limit, offset);
  
  // Execute main query
  const disclosures = await db.all(query, queryParams);
  
  return {
    data: disclosures,
    pagination: {
      total: totalCount.total,
      limit: limit,
      offset: offset,
      pages: Math.ceil(totalCount.total / limit)
    }
  };
}

/**
 * Get statistics about the disclosure data
 */
export async function getDisclosureStats(): Promise<DisclosureStats> {
  const db = getConnection();
  
  // Get count by category
  const categoryCounts = await db.all(`
    SELECT category, COUNT(*) as count 
    FROM disclosures 
    GROUP BY category
    ORDER BY count DESC
  `);
  
  // Get count by party
  const partyCounts = await db.all(`
    SELECT party, COUNT(*) as count 
    FROM disclosures 
    WHERE party IS NOT NULL
    GROUP BY party
    ORDER BY count DESC
  `);
  
  // Get count by year
  const yearCounts = await db.all(`
    SELECT 
      strftime('%Y', declaration_date) as year,
      COUNT(*) as count
    FROM disclosures
    GROUP BY year
    ORDER BY year
  `);
  
  // Get top MPs by disclosure count
  const topMPs = await db.all(`
    SELECT mp_name, COUNT(*) as count
    FROM disclosures
    GROUP BY mp_name
    ORDER BY count DESC
    LIMIT 10
  `);
  
  // Get disclosure count by category and party
  const categoryByParty = await db.all(`
    SELECT 
      category,
      party,
      COUNT(*) as count
    FROM disclosures
    WHERE party IS NOT NULL
    GROUP BY category, party
    ORDER BY category, count DESC
  `);
  
  // Get gift stats
  const giftStats = await db.all(`
    SELECT 
      sub_category as type,
      COUNT(*) as count
    FROM disclosures
    WHERE category = 'Gift'
    GROUP BY sub_category
    ORDER BY count DESC
  `);
  
  // Get asset stats
  const assetStats = await db.all(`
    SELECT 
      sub_category as type,
      COUNT(*) as count
    FROM disclosures
    WHERE category = 'Asset'
    GROUP BY sub_category
    ORDER BY count DESC
  `);
  
  return {
    categories: categoryCounts,
    parties: partyCounts,
    years: yearCounts,
    topMPs,
    categoryByParty,
    gifts: giftStats,
    assets: assetStats
  };
} 