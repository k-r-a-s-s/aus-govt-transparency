import { 
  DisclosureData, 
  GiftAnalysisData, 
  NetworkData, 
  NetworkNode, 
  NetworkLink 
} from '../types';

/**
 * Transforms disclosure data into gift analysis data
 */
export const transformToGiftAnalysis = (
  disclosures: DisclosureData[]
): GiftAnalysisData => {
  // Filter to ensure we're only working with gift disclosures
  const giftDisclosures = disclosures.filter(d => 
    d.category === 'Gift' || d.category.toLowerCase().includes('gift')
  );
  
  if (giftDisclosures.length === 0) {
    return {
      byType: [],
      byProvider: [],
      byParty: [],
      mostCommon: {
        type: '',
        provider: '',
        party: ''
      }
    };
  }
  
  // Extract gift types
  const giftTypes: Record<string, number> = {};
  
  giftDisclosures.forEach(disclosure => {
    // Attempt to categorize gifts based on the item description
    const item = disclosure.item.toLowerCase();
    let type = 'Other';
    
    if (item.includes('ticket') || item.includes('admission') || item.includes('event')) {
      type = 'Tickets & Events';
    } else if (item.includes('book') || item.includes('publication')) {
      type = 'Books & Publications';
    } else if (item.includes('alcohol') || item.includes('wine') || item.includes('champagne')) {
      type = 'Alcohol';
    } else if (item.includes('food') || item.includes('lunch') || item.includes('dinner') || item.includes('meal')) {
      type = 'Food & Dining';
    } else if (item.includes('travel') || item.includes('accommodation') || item.includes('flight')) {
      type = 'Travel & Accommodation';
    } else if (item.includes('membership') || item.includes('subscription')) {
      type = 'Memberships';
    } else if (item.includes('artwork') || item.includes('painting') || item.includes('sculpture')) {
      type = 'Artwork';
    } else if (item.includes('electronic') || item.includes('device') || item.includes('gadget') || item.includes('phone')) {
      type = 'Electronics';
    }
    
    giftTypes[type] = (giftTypes[type] || 0) + 1;
  });
  
  // Extract gift providers
  const giftProviders: Record<string, number> = {};
  
  giftDisclosures.forEach(disclosure => {
    if (disclosure.entity) {
      const provider = disclosure.entity.trim();
      giftProviders[provider] = (giftProviders[provider] || 0) + 1;
    }
  });
  
  // Extract gifts by party
  const giftsByParty: Record<string, number> = {};
  
  giftDisclosures.forEach(disclosure => {
    if (disclosure.party) {
      const party = disclosure.party.trim();
      giftsByParty[party] = (giftsByParty[party] || 0) + 1;
    }
  });
  
  // Find most common type, provider, and party
  const mostCommonType = Object.entries(giftTypes)
    .sort((a, b) => b[1] - a[1])
    .map(([type]) => type)[0] || '';
    
  const mostCommonProvider = Object.entries(giftProviders)
    .sort((a, b) => b[1] - a[1])
    .map(([provider]) => provider)[0] || '';
    
  const mostCommonParty = Object.entries(giftsByParty)
    .sort((a, b) => b[1] - a[1])
    .map(([party]) => party)[0] || '';
  
  return {
    byType: Object.entries(giftTypes)
      .map(([type, count]) => ({ type, count }))
      .sort((a, b) => b.count - a.count),
    byProvider: Object.entries(giftProviders)
      .map(([provider, count]) => ({ provider, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10), // Top 10 providers
    byParty: Object.entries(giftsByParty)
      .map(([party, count]) => ({ party, count }))
      .sort((a, b) => b.count - a.count),
    mostCommon: {
      type: mostCommonType,
      provider: mostCommonProvider,
      party: mostCommonParty
    }
  };
};

/**
 * Transforms disclosure data into network data
 */
export const transformToNetworkData = (
  disclosures: DisclosureData[],
  filterMPName?: string,
  filterEntity?: string
): NetworkData => {
  const nodes: NetworkNode[] = [];
  const links: NetworkLink[] = [];
  
  // Maps to track unique nodes
  const mpNodes = new Map<string, NetworkNode>();
  const entityNodes = new Map<string, NetworkNode>();
  
  // Maps to track connections for link weights
  const connections = new Map<string, { count: number; categories: Record<string, number> }>();
  
  // Filter disclosures if needed
  const filteredDisclosures = disclosures.filter(d => {
    if (filterMPName && d.mp_name !== filterMPName) {
      return false;
    }
    if (filterEntity && d.entity !== filterEntity) {
      return false;
    }
    return true;
  });
  
  // Process disclosures to create nodes and links
  filteredDisclosures.forEach(disclosure => {
    const mpName = disclosure.mp_name;
    const entity = disclosure.entity;
    
    // Skip if no entity
    if (!entity) return;
    
    // Add MP node if not exists
    if (!mpNodes.has(mpName)) {
      mpNodes.set(mpName, {
        id: `mp-${mpName}`,
        name: mpName,
        type: 'mp',
        party: disclosure.party,
        size: 1
      });
    } else {
      // Increment MP node size
      const node = mpNodes.get(mpName)!;
      node.size = (node.size || 1) + 1;
    }
    
    // Add entity node if not exists
    if (!entityNodes.has(entity)) {
      entityNodes.set(entity, {
        id: `entity-${entity}`,
        name: entity,
        type: 'entity',
        size: 1
      });
    } else {
      // Increment entity node size
      const node = entityNodes.get(entity)!;
      node.size = (node.size || 1) + 1;
    }
    
    // Track connection
    const connectionKey = `${mpName}-${entity}`;
    if (!connections.has(connectionKey)) {
      connections.set(connectionKey, { count: 0, categories: {} });
    }
    
    const connection = connections.get(connectionKey)!;
    connection.count += 1;
    
    if (disclosure.category) {
      connection.categories[disclosure.category] = 
        (connection.categories[disclosure.category] || 0) + 1;
    }
  });
  
  // Create links from connections
  connections.forEach((connection, key) => {
    const [mpName, entity] = key.split('-');
    
    // Get predominant category
    let category = '';
    let maxCategoryCount = 0;
    
    Object.entries(connection.categories).forEach(([cat, count]) => {
      if (count > maxCategoryCount) {
        category = cat;
        maxCategoryCount = count;
      }
    });
    
    links.push({
      source: `mp-${mpName}`,
      target: `entity-${entity}`,
      value: connection.count,
      category
    });
  });
  
  // Combine all nodes
  nodes.push(...Array.from(mpNodes.values()));
  nodes.push(...Array.from(entityNodes.values()));
  
  return { nodes, links };
};

/**
 * Extracts unique values from disclosure data
 */
export const extractUniqueValues = (
  disclosures: DisclosureData[],
  field: keyof DisclosureData
) => {
  const uniqueValues = new Set<string>();
  
  disclosures.forEach(disclosure => {
    const value = disclosure[field];
    if (typeof value === 'string' && value.trim()) {
      uniqueValues.add(value.trim());
    }
  });
  
  return Array.from(uniqueValues).sort();
}; 