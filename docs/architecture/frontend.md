# Frontend Architecture

The frontend application is a React-based single-page application (SPA) built with TypeScript. It provides a user interface for exploring, analyzing, and visualizing parliamentary disclosure data fetched from the API server.

## Technology Stack

- **React**: JavaScript library for building user interfaces
- **TypeScript**: Typed superset of JavaScript
- **React Router**: Library for routing in React applications
- **TanStack Query**: Data fetching and caching library
- **D3.js**: Library for data visualizations
- **Tailwind CSS**: Utility-first CSS framework

## Core Architecture

The frontend follows a component-based architecture with several key patterns:

1. **Pages**: Top-level components representing different routes
2. **Components**: Reusable UI elements
3. **Services**: Functions for interacting with the API
4. **Hooks**: Custom React hooks for shared functionality
5. **Types**: TypeScript interfaces for type safety

## Folder Structure

```
frontend/
├── src/
│   ├── assets/            # Static assets
│   ├── components/        # Reusable UI components
│   │   ├── common/        # Common UI components
│   │   ├── layout/        # Layout components
│   │   └── visualizations/ # Data visualization components
│   ├── hooks/             # Custom React hooks
│   ├── pages/             # Page components
│   ├── services/          # API services
│   ├── types/             # TypeScript interfaces
│   ├── utils/             # Utility functions
│   ├── App.tsx            # Main application component
│   ├── index.css          # Global styles
│   └── main.tsx           # Application entry point
├── public/                # Public assets
├── index.html             # HTML template
├── tailwind.config.js     # Tailwind CSS configuration
├── tsconfig.json          # TypeScript configuration
└── package.json           # NPM package configuration
```

## Component Hierarchy

```
App
├── Layout
│   ├── Navbar
│   └── Footer
├── Routes
│   ├── Home
│   │   ├── StatsWidget
│   │   ├── RecentDisclosuresWidget
│   │   └── TimelineWidget
│   ├── MPProfile
│   │   ├── MPHeader
│   │   ├── DisclosureList
│   │   ├── CategoryBreakdown
│   │   └── EntityNetwork
│   ├── Members
│   │   ├── MPSearchForm
│   │   └── MPList
│   ├── EntityExplorer
│   │   ├── NetworkGraph
│   │   └── EntityDetails
│   ├── DisclosureAnalytics
│   │   ├── CategoryDistribution
│   │   ├── PartyComparison
│   │   └── TrendAnalysis
│   ├── TravelAnalysis
│   │   ├── TravelMap
│   │   └── TravelStats
│   └── Other pages...
```

## Data Flow

The frontend follows a unidirectional data flow pattern:

1. **Data Fetching**: API data is fetched using TanStack Query hooks
2. **State Management**: Component state and React Query cache manage application state
3. **Rendering**: Components render based on the current state
4. **User Interaction**: User actions trigger state updates or API calls

```
+----------------+            +----------------+            +----------------+
| API Service    |            | React Query    |            | Component      |
| (Data Source)  | ---------> | Hooks/Cache    | ---------> | State          |
+----------------+            +----------------+            +----------------+
                                                                    |
                                                                    v
+----------------+            +----------------+            +----------------+
| API Call       |            | User           |            | Component      |
| (Data Update)  | <--------- | Interaction    | <--------- | Rendering      |
+----------------+            +----------------+            +----------------+
```

## Key Components

### API Service

The `api.ts` file contains functions for interacting with the API server:

```typescript
export const fetchDisclosures = async (
  params?: DisclosureQueryParams
): Promise<DisclosureData[]> => {
  return fetchApi<DisclosureData[]>('disclosures', undefined, params);
};
```

### Data Hooks

Custom hooks wrap the API service functions for use in components:

```typescript
export const useDisclosures = (params: DisclosureQueryParams) => {
  return useQuery({
    queryKey: ['disclosures', params],
    queryFn: () => fetchDisclosures(params)
  });
};
```

### Visualization Components

D3.js is used to create interactive data visualizations:

```typescript
export const NetworkGraph: React.FC<{data: NetworkData}> = ({data}) => {
  const svgRef = useRef<SVGSVGElement>(null);
  
  useEffect(() => {
    if (!svgRef.current) return;
    // D3.js code to render network graph
  }, [data]);
  
  return <svg ref={svgRef} />;
};
```

## Responsive Design

The frontend is designed to be responsive and work well on different screen sizes:

- Mobile-first approach with Tailwind CSS
- Responsive layout components
- Adaptive visualizations

## State Management

State management is handled through a combination of:

1. **Local Component State**: For UI-specific state
2. **React Query Cache**: For server state
3. **URL Parameters**: For shareable/bookmarkable state

## Performance Considerations

Several strategies are employed to ensure good performance:

- Code splitting with lazy loading
- Memoization of expensive computations
- Optimized rendering with React.memo()
- Data caching with React Query

## Next Steps

- [Frontend Components](../frontend/components.md)
- [Pages Documentation](../frontend/pages.md)
- [Services Documentation](../frontend/services.md) 