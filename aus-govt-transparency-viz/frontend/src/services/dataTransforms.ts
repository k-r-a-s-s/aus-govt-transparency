import { DisclosureData } from '../types/disclosureTypes';
import { MPNetworkData, Node, Link, EntityConnection } from '../types/networkTypes';

/**
 * Transform disclosure data into network graph format
 */
export const transformToNetworkData = (disclosures: DisclosureData[]): MPNetworkData => {
  const nodes: Node[] = [];
  const links: Link[] = [];
  const mpIds = new Set<string>();
  const entityIds = new Set<string>();
  
  // First pass: create nodes
  disclosures.forEach(disclosure => {
    // Add MP node if not already added
    if (disclosure.mp_name && !mpIds.has(disclosure.mp_name)) {
      mpIds.add(disclosure.mp_name);
      nodes.push({
        id: disclosure.mp_name,
        name: disclosure.mp_name,
        type: 'mp',
        party: disclosure.party
      });
    }
    
    // Add entity node if not already added
    if (disclosure.entity && !entityIds.has(disclosure.entity)) {
      entityIds.add(disclosure.entity);
      nodes.push({
        id: disclosure.entity,
        name: disclosure.entity,
        type: 'entity'
      });
    }
  });
  
  // Second pass: create links
  disclosures.forEach(disclosure => {
    if (disclosure.mp_name && disclosure.entity) {
      // Check if link already exists
      const existingLink = links.find(link => 
        (link.source === disclosure.mp_name && link.target === disclosure.entity) ||
        (link.source === disclosure.entity && link.target === disclosure.mp_name)
      );
      
      if (existingLink) {
        // Increment weight of existing link
        existingLink.value += 1;
      } else {
        // Create new link
        links.push({
          source: disclosure.mp_name,
          target: disclosure.entity,
          value: 1,
          type: disclosure.category
        });
      }
    }
  });
  
  return { nodes, links };
};

/**
 * Transform disclosure data into timeline format
 */
export const transformToTimelineData = (disclosures: DisclosureData[]) => {
  // Sort by date
  const sortedDisclosures = [...disclosures].sort(
    (a, b) => new Date(a.declaration_date).getTime() - new Date(b.declaration_date).getTime()
  );
  
  // Group by year and category
  const timelineData = sortedDisclosures.reduce((acc, disclosure) => {
    const year = new Date(disclosure.declaration_date).getFullYear();
    const yearKey = year.toString();
    
    if (!acc[yearKey]) {
      acc[yearKey] = {
        year,
        Assets: 0,
        Liabilities: 0,
        Income: 0,
        Gifts: 0,
        Travel: 0,
        Memberships: 0
      };
    }
    
    // Increment the appropriate category
    if (disclosure.category === 'Asset') acc[yearKey].Assets++;
    else if (disclosure.category === 'Liability') acc[yearKey].Liabilities++;
    else if (disclosure.category === 'Income') acc[yearKey].Income++;
    else if (disclosure.category === 'Gift') acc[yearKey].Gifts++;
    else if (disclosure.category === 'Travel') acc[yearKey].Travel++;
    else if (disclosure.category === 'Membership') acc[yearKey].Memberships++;
    
    return acc;
  }, {} as Record<string, any>);
  
  // Convert to array
  return Object.values(timelineData);
};

/**
 * Transform disclosure data into gift analysis format
 */
export const transformToGiftAnalysis = (disclosures: DisclosureData[]) => {
  const giftDisclosures = disclosures.filter(d => d.category === 'Gift');
  
  // Gift sub-categories
  const subCategories = giftDisclosures.reduce((acc, gift) => {
    const subCat = gift.sub_category || 'Unspecified';
    
    if (acc[subCat]) {
      acc[subCat]++;
    } else {
      acc[subCat] = 1;
    }
    
    return acc;
  }, {} as Record<string, number>);
  
  // Gift donors
  const donors = giftDisclosures.reduce((acc, gift) => {
    if (gift.entity) {
      if (acc[gift.entity]) {
        acc[gift.entity]++;
      } else {
        acc[gift.entity] = 1;
      }
    }
    
    return acc;
  }, {} as Record<string, number>);
  
  // Gifts by party
  const byParty = giftDisclosures.reduce((acc, gift) => {
    if (gift.party) {
      if (acc[gift.party]) {
        acc[gift.party]++;
      } else {
        acc[gift.party] = 1;
      }
    }
    
    return acc;
  }, {} as Record<string, number>);
  
  return {
    subCategories: Object.entries(subCategories).map(([name, value]) => ({ name, value })),
    donors: Object.entries(donors)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([name, count]) => ({ name, count })),
    byParty: Object.entries(byParty).map(([name, value]) => ({ name, value }))
  };
};

/**
 * Transform disclosure data into entity connections
 */
export const transformToEntityConnections = (disclosures: DisclosureData[], entityName: string): EntityConnection[] => {
  return disclosures
    .filter(d => d.entity === entityName)
    .map(d => ({
      entity: d.entity,
      mp_name: d.mp_name,
      relationship_type: d.category,
      value: d.details || '',
      date_logged: d.declaration_date,
      party: d.party
    }));
};

/**
 * Transform asset disclosure data for change detection
 */
export const transformForAssetChangeDetection = (disclosures: DisclosureData[], mpName: string) => {
  const mpDisclosures = disclosures.filter(d => d.mp_name === mpName && d.category === 'Asset');
  
  // Group by date
  const dateMap: Record<string, Record<string, number>> = {};
  
  mpDisclosures.forEach(d => {
    const date = d.declaration_date;
    const subCategory = d.sub_category || 'Other';
    
    if (!dateMap[date]) {
      dateMap[date] = {};
    }
    
    dateMap[date][subCategory] = (dateMap[date][subCategory] || 0) + 1;
  });
  
  // Transform into timeline data
  const dates = Object.keys(dateMap).sort((a, b) => 
    new Date(a).getTime() - new Date(b).getTime()
  );
  
  const result = [];
  let cumulativeValues: Record<string, number> = {};
  
  for (const date of dates) {
    const entry = {
      date,
      ...dateMap[date],
      changes: {} as Record<string, number>
    };
    
    // Calculate changes
    for (const subCategory in dateMap[date]) {
      const prevValue = cumulativeValues[subCategory] || 0;
      const currentValue = dateMap[date][subCategory];
      const change = currentValue - prevValue;
      
      if (change !== 0) {
        entry.changes[subCategory] = change;
      }
      
      cumulativeValues[subCategory] = currentValue;
    }
    
    result.push(entry);
  }
  
  return result;
}; 