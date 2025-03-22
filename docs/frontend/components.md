# Frontend Components

The Australian Government Transparency Project frontend uses a component-based architecture with React and TypeScript. This document describes the key reusable components used throughout the application.

## Component Organization

Components are organized into three main categories:

1. **Common Components**: General-purpose UI components used throughout the application
2. **Layout Components**: Components for page layout and structure
3. **Visualization Components**: Components for data visualization and charts

## Common Components

### Button

A customizable button component with different variants.

**Props:**

| Prop | Type | Description | Default |
|------|------|-------------|---------|
| variant | 'primary' \| 'secondary' \| 'outline' | Button style variant | 'primary' |
| size | 'sm' \| 'md' \| 'lg' | Button size | 'md' |
| isLoading | boolean | Whether to show a loading state | false |
| isDisabled | boolean | Whether the button is disabled | false |
| children | ReactNode | Button content | - |
| onClick | () => void | Click handler | - |

**Usage:**

```tsx
<Button variant="primary" onClick={handleClick}>
  Click Me
</Button>
```

### Card

A component for displaying content in a card format.

**Props:**

| Prop | Type | Description | Default |
|------|------|-------------|---------|
| title | string | Card title | - |
| subtitle | string | Card subtitle | - |
| children | ReactNode | Card content | - |
| footer | ReactNode | Card footer content | - |
| className | string | Additional CSS classes | - |

**Usage:**

```tsx
<Card title="Disclosure Statistics" subtitle="Last 30 days">
  <p>Content goes here</p>
  <Button>Action</Button>
</Card>
```

### Dropdown

A dropdown menu component.

**Props:**

| Prop | Type | Description | Default |
|------|------|-------------|---------|
| label | string | Dropdown label | - |
| options | Array<{value: string, label: string}> | Options for the dropdown | [] |
| value | string | Selected value | - |
| onChange | (value: string) => void | Change handler | - |
| placeholder | string | Placeholder text | 'Select an option' |
| isDisabled | boolean | Whether the dropdown is disabled | false |

**Usage:**

```tsx
<Dropdown
  label="Category"
  options={[
    { value: 'asset', label: 'Asset' },
    { value: 'gift', label: 'Gift' }
  ]}
  value={selectedCategory}
  onChange={setSelectedCategory}
/>
```

### SearchInput

A search input component with debounced search.

**Props:**

| Prop | Type | Description | Default |
|------|------|-------------|---------|
| placeholder | string | Placeholder text | 'Search...' |
| value | string | Search value | - |
| onChange | (value: string) => void | Change handler | - |
| debounceMs | number | Debounce time in milliseconds | 300 |

**Usage:**

```tsx
<SearchInput
  placeholder="Search by MP name"
  value={searchTerm}
  onChange={setSearchTerm}
  debounceMs={500}
/>
```

### Pagination

A pagination component for navigating through pages of data.

**Props:**

| Prop | Type | Description | Default |
|------|------|-------------|---------|
| currentPage | number | Current page number | 1 |
| totalPages | number | Total number of pages | 1 |
| onPageChange | (page: number) => void | Page change handler | - |
| totalItems | number | Total number of items | 0 |
| pageSize | number | Number of items per page | 10 |

**Usage:**

```tsx
<Pagination
  currentPage={page}
  totalPages={10}
  onPageChange={setPage}
  totalItems={100}
  pageSize={10}
/>
```

### Badge

A badge component for displaying status or categories.

**Props:**

| Prop | Type | Description | Default |
|------|------|-------------|---------|
| variant | 'primary' \| 'secondary' \| 'success' \| 'warning' \| 'danger' | Badge style variant | 'primary' |
| children | ReactNode | Badge content | - |
| className | string | Additional CSS classes | - |

**Usage:**

```tsx
<Badge variant="success">Asset</Badge>
```

### Tabs

A tabbed navigation component.

**Props:**

| Prop | Type | Description | Default |
|------|------|-------------|---------|
| tabs | Array<{id: string, label: string}> | Tab definitions | [] |
| activeTab | string | ID of active tab | - |
| onTabChange | (tabId: string) => void | Tab change handler | - |
| children | ReactNode | Tab content | - |

**Usage:**

```tsx
<Tabs
  tabs={[
    { id: 'disclosures', label: 'Disclosures' },
    { id: 'statistics', label: 'Statistics' }
  ]}
  activeTab={activeTab}
  onTabChange={setActiveTab}
>
  {activeTab === 'disclosures' && <DisclosuresTab />}
  {activeTab === 'statistics' && <StatisticsTab />}
</Tabs>
```

### DataTable

A table component for displaying structured data.

**Props:**

| Prop | Type | Description | Default |
|------|------|-------------|---------|
| columns | Array<{key: string, header: string, render?: (row: any) => ReactNode}> | Column definitions | [] |
| data | Array<any> | Table data | [] |
| isLoading | boolean | Whether the table is loading | false |
| emptyState | ReactNode | Content to show when data is empty | 'No data available' |
| onRowClick | (row: any) => void | Row click handler | - |

**Usage:**

```tsx
<DataTable
  columns={[
    { key: 'mp_name', header: 'MP Name' },
    { key: 'party', header: 'Party' },
    { key: 'category', header: 'Category' },
    { 
      key: 'declaration_date', 
      header: 'Date',
      render: (row) => formatDate(row.declaration_date)
    }
  ]}
  data={disclosures}
  isLoading={isLoading}
  onRowClick={handleRowClick}
/>
```

## Layout Components

### Layout

The main layout component that wraps all pages.

**Props:**

| Prop | Type | Description | Default |
|------|------|-------------|---------|
| children | ReactNode | Layout content | - |

**Usage:**

```tsx
<Layout>
  <Home />
</Layout>
```

### Navbar

The navigation bar component.

**Props:**

| Prop | Type | Description | Default |
|------|------|-------------|---------|
| transparent | boolean | Whether the navbar has a transparent background | false |

**Usage:**

```tsx
<Navbar transparent={isHomePage} />
```

### Footer

The footer component.

**Props:**

No props.

**Usage:**

```tsx
<Footer />
```

### Sidebar

A sidebar navigation component.

**Props:**

| Prop | Type | Description | Default |
|------|------|-------------|---------|
| isOpen | boolean | Whether the sidebar is open | false |
| onClose | () => void | Close handler | - |
| items | Array<{id: string, label: string, icon: ReactNode, href: string}> | Navigation items | [] |

**Usage:**

```tsx
<Sidebar
  isOpen={isSidebarOpen}
  onClose={closeSidebar}
  items={[
    { id: 'home', label: 'Home', icon: <HomeIcon />, href: '/' },
    { id: 'members', label: 'Members', icon: <UsersIcon />, href: '/members' }
  ]}
/>
```

### PageHeader

A page header component.

**Props:**

| Prop | Type | Description | Default |
|------|------|-------------|---------|
| title | string | Page title | - |
| subtitle | string | Page subtitle | - |
| actions | ReactNode | Action buttons | - |
| breadcrumbs | Array<{label: string, href: string}> | Breadcrumb items | [] |

**Usage:**

```tsx
<PageHeader
  title="Disclosure Analytics"
  subtitle="Insights into parliamentary disclosures"
  actions={<Button>Export</Button>}
  breadcrumbs={[
    { label: 'Home', href: '/' },
    { label: 'Analytics', href: '/analytics' }
  ]}
/>
```

## Visualization Components

### BarChart

A bar chart component for visualizing categorical data.

**Props:**

| Prop | Type | Description | Default |
|------|------|-------------|---------|
| data | Array<{label: string, value: number}> | Chart data | [] |
| height | number | Chart height | 300 |
| width | number | Chart width | 500 |
| title | string | Chart title | - |
| xAxisLabel | string | X-axis label | - |
| yAxisLabel | string | Y-axis label | - |
| colorScheme | string | D3 color scheme | 'schemeCategory10' |

**Usage:**

```tsx
<BarChart
  data={[
    { label: 'Asset', value: 180 },
    { label: 'Gift', value: 120 },
    { label: 'Travel', value: 95 }
  ]}
  height={350}
  width={600}
  title="Disclosures by Category"
  xAxisLabel="Category"
  yAxisLabel="Count"
/>
```

### NetworkGraph

A network graph for visualizing relationships between MPs and entities.

**Props:**

| Prop | Type | Description | Default |
|------|------|-------------|---------|
| data | NetworkData | Network data | { nodes: [], links: [] } |
| height | number | Graph height | 600 |
| width | number | Graph width | 800 |
| onNodeClick | (node: NetworkNode) => void | Node click handler | - |
| selectedNode | string | ID of selected node | - |

**Usage:**

```tsx
<NetworkGraph
  data={networkData}
  height={500}
  width={700}
  onNodeClick={handleNodeClick}
  selectedNode={selectedNodeId}
/>
```

### LineChart

A line chart component for visualizing time series data.

**Props:**

| Prop | Type | Description | Default |
|------|------|-------------|---------|
| data | Array<{date: string, value: number}> | Chart data | [] |
| height | number | Chart height | 300 |
| width | number | Chart width | 500 |
| title | string | Chart title | - |
| xAxisLabel | string | X-axis label | - |
| yAxisLabel | string | Y-axis label | - |
| dateFormat | string | Date format for x-axis | 'MMM YYYY' |

**Usage:**

```tsx
<LineChart
  data={[
    { date: '2023-01', value: 120 },
    { date: '2023-02', value: 95 },
    { date: '2023-03', value: 150 }
  ]}
  height={350}
  width={600}
  title="Disclosures Over Time"
  xAxisLabel="Month"
  yAxisLabel="Count"
/>
```

### PieChart

A pie chart component for visualizing proportions.

**Props:**

| Prop | Type | Description | Default |
|------|------|-------------|---------|
| data | Array<{label: string, value: number}> | Chart data | [] |
| height | number | Chart height | 300 |
| width | number | Chart width | 300 |
| title | string | Chart title | - |
| colorScheme | string | D3 color scheme | 'schemeCategory10' |
| innerRadius | number | Inner radius for donut chart | 0 |

**Usage:**

```tsx
<PieChart
  data={[
    { label: 'Liberal', value: 65 },
    { label: 'Labor', value: 60 },
    { label: 'Greens', value: 25 }
  ]}
  height={350}
  width={350}
  title="Disclosures by Party"
  innerRadius={50}
/>
```

### MapChart

A map chart component for geographic visualization.

**Props:**

| Prop | Type | Description | Default |
|------|------|-------------|---------|
| data | Array<{region: string, value: number}> | Map data | [] |
| height | number | Chart height | 500 |
| width | number | Chart width | 800 |
| title | string | Chart title | - |
| geoJsonPath | string | Path to GeoJSON data | '/assets/australia.json' |
| colorScale | Function | D3 color scale function | - |
| onRegionClick | (region: string) => void | Region click handler | - |

**Usage:**

```tsx
<MapChart
  data={[
    { region: 'NSW', value: 250 },
    { region: 'VIC', value: 200 },
    { region: 'QLD', value: 180 }
  ]}
  height={450}
  width={700}
  title="Disclosures by State"
  onRegionClick={handleRegionClick}
/>
```

## Next Steps

- [Pages Documentation](../frontend/pages.md)
- [Services Documentation](../frontend/services.md)
- [Documentation Index](../index.md) 