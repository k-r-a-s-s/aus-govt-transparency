# Entity Explorer

The Entity Explorer is a powerful visualization tool in the Australian Government Transparency Project that allows users to explore connections between Members of Parliament (MPs) and entities through an interactive network graph.

## Overview

The Entity Explorer provides a comprehensive view of the relationships between MPs and entities (companies, organizations, individuals, etc.) based on the disclosure data. It helps users identify patterns, analyze connections, and understand the network of political donations and conflicts of interest.

## Key Features

### Network Visualization

The core of the Entity Explorer is an interactive network graph that displays:

- **MP nodes**: Represented by circles with party colors
- **Entity nodes**: Represented by squares
- **Connections**: Edges between MPs and entities represent disclosure relationships
- **Size variation**: Node size can represent the number of connections
- **Force-directed layout**: Intuitively arranges nodes based on their relationships

```typescript
// NetworkGraph component core structure
const NetworkGraph: React.FC<NetworkGraphProps> = ({ 
  data, 
  onNodeClick, 
  selectedNode 
}) => {
  // Force simulation setup
  useEffect(() => {
    const simulation = d3.forceSimulation(data.nodes)
      .force('link', d3.forceLink(data.links).id(d => d.id))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .on('tick', ticked);
    
    // Rendering and interaction code
    // ...
  }, [data]);
  
  // Component return
  return <svg className="network-graph" ref={svgRef} />;
};
```

### Search and Filter

The Entity Explorer includes robust search and filtering capabilities:

- **Entity search**: Find specific entities by name
- **MP filter**: Focus on specific MPs or parties
- **Category filter**: Filter by disclosure categories
- **Timeframe selection**: Limit visualization to specific time periods

### Entity Details Panel

When selecting an entity node, a detailed panel displays:

- **Entity name**: The name of the selected entity
- **Variant names**: When using canonical entities, shows all variant names
- **Connected MPs**: List of MPs connected to this entity
- **Disclosure count**: Total number of disclosures involving this entity
- **Disclosure timeline**: Visualization of disclosures over time

## Integration with Entity Deduplication

The Entity Explorer fully integrates with the entity deduplication feature, allowing users to:

1. **Toggle between original and canonical entity names**: Switch views to see either original entity names or their canonical (standardized) versions

```typescript
// Canonical entity toggle component
const CanonicalToggle: React.FC<{
  useCanonical: boolean;
  setUseCanonical: React.Dispatch<React.SetStateAction<boolean>>;
}> = ({ useCanonical, setUseCanonical }) => {
  return (
    <div className="canonical-toggle">
      <label className="toggle-switch">
        <input
          type="checkbox"
          checked={useCanonical}
          onChange={(e) => setUseCanonical(e.target.checked)}
        />
        <span className="toggle-slider"></span>
      </label>
      <span className="toggle-label">
        Use standardized entity names
      </span>
    </div>
  );
};
```

2. **View entity variants**: When viewing a canonical entity, see all the variant names that map to it

```typescript
// Entity detail component with variant support
const EntityDetail: React.FC<{
  entity: EntityDetails | null;
  isLoading: boolean;
}> = ({ entity, isLoading }) => {
  if (isLoading) return <div className="entity-detail-loading">Loading...</div>;
  if (!entity) return <div className="entity-detail-empty">Select an entity to view details</div>;
  
  return (
    <div className="entity-detail">
      <h2>{entity.entity}</h2>
      
      {entity.variants && entity.variants.length > 0 && (
        <div className="entity-variants">
          <h3>Also known as:</h3>
          <ul>
            {entity.variants.map(variant => (
              <li key={variant}>{variant}</li>
            ))}
          </ul>
        </div>
      )}
      
      <div className="entity-stats">
        <div className="stat">
          <span className="stat-label">Disclosures:</span>
          <span className="stat-value">{entity.count}</span>
        </div>
      </div>
      
      <h3>Connected MPs ({entity.connected_mps.length})</h3>
      <ul className="connected-mp-list">
        {entity.connected_mps.map(mp => (
          <li key={mp.name} className="connected-mp">
            <span className="mp-name">{mp.name}</span>
            <span className="mp-party" style={{ backgroundColor: getPartyColor(mp.party) }}>
              {mp.party}
            </span>
            <span className="mp-count">{mp.count} disclosures</span>
          </li>
        ))}
      </ul>
    </div>
  );
};
```

3. **Network simplification**: Canonical entities consolidate duplicate nodes, creating a cleaner and more accurate network visualization

## API Integration

The Entity Explorer uses several API endpoints:

1. **Network data**: `GET /api/network?canonical=[true|false]`
2. **Entity details**: `GET /api/entity/:name?canonical=[true|false]`
3. **Entity search**: `GET /api/search/entities?q=:query&canonical=[true|false]`

### Custom Hooks

The Entity Explorer uses custom React hooks to manage data fetching:

```typescript
// Network data hook
const useNetworkData = (
  options: {
    mp?: string;
    entity?: string;
    useCanonical?: boolean;
  } = {}
) => {
  const { mp, entity, useCanonical = false } = options;
  const queryKey = ['network', { mp, entity, canonical: useCanonical }];
  
  return useQuery({
    queryKey,
    queryFn: async () => {
      const url = new URL(`${API_BASE}/network`);
      if (mp) url.searchParams.append('mp', mp);
      if (entity) url.searchParams.append('entity', entity);
      if (useCanonical) url.searchParams.append('canonical', 'true');
      
      const response = await fetch(url);
      if (!response.ok) throw new Error('Network error');
      return response.json();
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

// Entity details hook
const useEntityDetails = (
  entityName: string | null,
  options: {
    useCanonical?: boolean;
  } = {}
) => {
  const { useCanonical = false } = options;
  const queryKey = ['entity', entityName, { canonical: useCanonical }];
  
  return useQuery({
    queryKey,
    queryFn: async () => {
      if (!entityName) return null;
      
      const url = new URL(`${API_BASE}/entity/${encodeURIComponent(entityName)}`);
      if (useCanonical) url.searchParams.append('canonical', 'true');
      
      const response = await fetch(url);
      if (!response.ok) throw new Error('Network error');
      return response.json();
    },
    enabled: !!entityName,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};
```

## User Flow

A typical user flow in the Entity Explorer:

1. User lands on the Entity Explorer page, seeing a network of MPs and top entities
2. User toggles "Use standardized entity names" to view canonical entities
3. User searches for a specific entity (e.g., "Shell")
4. User clicks on an entity node to view detailed information
5. User explores connected MPs and their relationships
6. User clicks on an MP to focus the network on that MP's connections

## Benefits of Entity Deduplication

The integration of entity deduplication in the Entity Explorer provides several benefits:

1. **Reduced visual clutter**: Fewer duplicated nodes in the network visualization
2. **More accurate analysis**: Consolidated entity data provides better insights
3. **Improved search**: Users can find entities regardless of naming variations
4. **Complete context**: Variant names are displayed when viewing canonical entities

## Technical Details

### State Management

The Entity Explorer uses React state to manage:

- Network data and loading state
- Selected entity and MP
- Canonical entity toggle state
- Search and filter criteria

### Performance Optimization

Several optimizations improve performance:

- **Lazy loading**: Details are fetched only when needed
- **Memoization**: Expensive calculations are cached
- **Virtual lists**: Large MP or entity lists use virtualization
- **Throttled interactions**: Network interactions are throttled for smooth performance

### Accessibility Considerations

The Entity Explorer implements accessibility features:

- **Keyboard navigation**: Full keyboard support for navigation
- **Screen reader support**: ARIA attributes and semantic HTML
- **Color contrast**: Compliant with WCAG standards
- **Text alternatives**: Network visualization has text-based alternatives

## Conclusion

The Entity Explorer, with its integration of entity deduplication, provides a powerful tool for exploring the network of political connections in the Australian Government Transparency Project. By combining visual analytics with data standardization, it enables users to discover insights that would be difficult to identify through traditional methods. 