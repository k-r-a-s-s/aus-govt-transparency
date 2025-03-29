# API Data Models

This document describes the data models used in the Australian Government Transparency Project API. These models define the structure of data exchanged between the API and clients.

## Disclosure

The Disclosure model represents a single disclosure entry from an MP's register of interests.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| id | string | Unique identifier (UUID) |
| mp_name | string | MP's full name |
| party | string | Political party affiliation |
| electorate | string | Electoral district represented by the MP |
| category | string | Category of disclosure (Asset, Liability, etc.) |
| sub_category | string | Subcategory of disclosure (Real Estate, Shares, etc.) |
| item | string | Description of the disclosed item |
| entity | string | Associated entity or source |
| entity_id | string | Reference to the entity in the entities table |
| declaration_date | string | Date of declaration (YYYY-MM-DD format) |
| details | string | Additional details about the disclosure |
| temporal_type | string | Temporal nature (one-time, recurring, ongoing) |
| start_date | string | Start date for recurring/ongoing items |
| end_date | string | End date for recurring/ongoing items |
| pdf_url | string | URL to the source PDF document |
| pdf_page | number | Page number in the PDF |
| confidence | number | AI confidence score (0-1) |
| last_updated | string | Timestamp of last update |

### Example

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "mp_name": "Jane Smith",
  "party": "Labor",
  "electorate": "Sydney",
  "category": "Asset",
  "sub_category": "Real Estate",
  "item": "Residential property",
  "entity": "N/A",
  "entity_id": null,
  "declaration_date": "2023-05-15",
  "details": "Family home in Sydney",
  "temporal_type": "ongoing",
  "start_date": "2020-01-01",
  "end_date": null,
  "pdf_url": "/api/pdf/smith_jane_47th.pdf",
  "pdf_page": 3,
  "confidence": 0.95,
  "last_updated": "2023-06-01T14:30:00Z"
}
```

## MP

The MP model represents a Member of Parliament.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| mp_name | string | MP's full name |
| party | string | Political party affiliation |
| electorate | string | Electoral district represented by the MP |

### Example

```json
{
  "mp_name": "Jane Smith",
  "party": "Labor",
  "electorate": "Sydney"
}
```

## Entity

The Entity model represents an organization, company, or individual mentioned in disclosures.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| id | string | Unique identifier (UUID) |
| name | string | Entity name |
| entity_type | string | Type of entity (Company, Organization, etc.) |
| category | string | Primary category of interest |
| abn | string | Australian Business Number |
| description | string | Entity description |
| first_appearance | string | Date of first appearance |
| last_appearance | string | Date of last appearance |
| appearances_count | number | Number of times entity appears |

### Example

```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Acme Corporation",
  "entity_type": "Company",
  "category": "Private Sector",
  "abn": "12345678901",
  "description": "Multinational conglomerate",
  "first_appearance": "2020-03-15",
  "last_appearance": "2023-05-20",
  "appearances_count": 15
}
```

## StatisticsResponse

The StatisticsResponse model represents statistical data about disclosures.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| total_disclosures | number | Total number of disclosures |
| total_mps | number | Total number of MPs with disclosures |
| total_entities | number | Total number of unique entities |
| categories | array | Array of category statistics |
| top_mps | array | Array of MP disclosure statistics |

### Category Statistics

| Property | Type | Description |
|----------|------|-------------|
| category | string | Category name |
| count | number | Number of disclosures in this category |

### MP Statistics

| Property | Type | Description |
|----------|------|-------------|
| mp_name | string | MP's name |
| party | string | Political party |
| count | number | Number of disclosures |

### Example

```json
{
  "total_disclosures": 5432,
  "total_mps": 150,
  "total_entities": 320,
  "categories": [
    { "category": "Asset", "count": 1800 },
    { "category": "Liability", "count": 950 },
    { "category": "Income", "count": 780 },
    { "category": "Gift", "count": 650 },
    { "category": "Travel", "count": 450 },
    { "category": "Membership", "count": 320 },
    { "category": "Unknown", "count": 482 }
  ],
  "top_mps": [
    { "mp_name": "Jane Smith", "party": "Labor", "count": 45 },
    { "mp_name": "John Doe", "party": "Liberal", "count": 42 },
    { "mp_name": "Sarah Connor", "party": "Greens", "count": 38 }
  ]
}
```

## NetworkData

The NetworkData model represents network data for entity explorer visualization.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| nodes | array | Array of network nodes |
| links | array | Array of network links |

### Network Node

| Property | Type | Description |
|----------|------|-------------|
| id | string | Unique identifier |
| name | string | Display name |
| type | string | Node type ('mp' or 'entity') |
| party | string | Political party (for MPs) |
| size | number | Node size (optional) |

### Network Link

| Property | Type | Description |
|----------|------|-------------|
| source | string | Source node ID |
| target | string | Target node ID |
| weight | number | Link weight (number of connections) |

### Example

```json
{
  "nodes": [
    {
      "id": "Jane Smith",
      "name": "Jane Smith",
      "type": "mp",
      "party": "Labor",
      "size": 5
    },
    {
      "id": "Acme Corporation",
      "name": "Acme Corporation",
      "type": "entity",
      "size": 3
    }
  ],
  "links": [
    {
      "source": "Jane Smith",
      "target": "Acme Corporation",
      "weight": 3
    }
  ]
}
```

## MPDetails

The MPDetails model extends the MP model with additional details about disclosures.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| mp_name | string | MP's full name |
| party | string | Political party affiliation |
| electorate | string | Electoral district represented by the MP |
| disclosures | array | Array of disclosure entries |
| categories | array | Array of category statistics |
| entities | array | Array of entity statistics |

### Example

```json
{
  "mp_name": "Jane Smith",
  "party": "Labor",
  "electorate": "Sydney",
  "disclosures": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "category": "Asset",
      "sub_category": "Real Estate",
      "item": "Residential property",
      "entity": "N/A",
      "declaration_date": "2023-05-15",
      "details": "Family home in Sydney"
    }
  ],
  "categories": [
    { "category": "Asset", "count": 15 },
    { "category": "Liability", "count": 8 }
  ],
  "entities": [
    { "entity": "Acme Corporation", "count": 3 },
    { "entity": "Global Industries", "count": 2 }
  ]
}
```

## TimelineData

The TimelineData model represents timeline data for visualizations.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| timeline | array | Array of monthly disclosure counts |
| categories | array | Array of monthly category counts |

### Monthly Count

| Property | Type | Description |
|----------|------|-------------|
| month | string | Month in YYYY-MM format |
| count | number | Number of disclosures |

### Monthly Category Count

| Property | Type | Description |
|----------|------|-------------|
| month | string | Month in YYYY-MM format |
| category | string | Category name |
| count | number | Number of disclosures |

### Example

```json
{
  "timeline": [
    { "month": "2023-01", "count": 120 },
    { "month": "2023-02", "count": 95 }
  ],
  "categories": [
    { "month": "2023-01", "category": "Asset", "count": 45 },
    { "month": "2023-01", "category": "Gift", "count": 30 },
    { "month": "2023-02", "category": "Asset", "count": 40 },
    { "month": "2023-02", "category": "Gift", "count": 25 }
  ]
}
```

## PDFInfo

The PDFInfo model represents information about PDFs for a specific MP.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| pdfs | array | Array of PDF information |

### PDF Information

| Property | Type | Description |
|----------|------|-------------|
| filename | string | PDF filename |
| url | string | URL to access the PDF |
| parliament | string | Parliament (e.g., "47th") |
| date | string | PDF date |

### Example

```json
{
  "pdfs": [
    {
      "filename": "smith_jane_47th.pdf",
      "url": "/api/pdf/smith_jane_47th.pdf",
      "parliament": "47th",
      "date": "2023-05-15"
    },
    {
      "filename": "smith_jane_46th.pdf",
      "url": "/api/pdf/smith_jane_46th.pdf",
      "parliament": "46th",
      "date": "2021-03-10"
    }
  ]
}
```

## NilEntriesStats

The NilEntriesStats model represents statistics about "nil" entries.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| total_nil_entries | number | Total number of "nil" entries |
| nil_by_category | array | Array of "nil" entries by category |
| nil_by_party | array | Array of "nil" entries by party |

### Example

```json
{
  "total_nil_entries": 850,
  "nil_by_category": [
    { "category": "Asset", "count": 320 },
    { "category": "Liability", "count": 220 }
  ],
  "nil_by_party": [
    { "party": "Labor", "count": 380 },
    { "party": "Liberal", "count": 350 }
  ]
}
```

## ErrorResponse

The ErrorResponse model represents an error response from the API.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| error | string | Error message |
| status | number | HTTP status code |

### Example

```json
{
  "error": "Invalid query parameter: category",
  "status": 400
}
```

## Next Steps

- [Frontend Components](../frontend/components.md)
- [Frontend Services](../frontend/services.md)

## Disclosure Schema

The Disclosure schema represents an individual interest disclosure entry.

```typescript
interface Disclosure {
  id: string;
  mp_name: string;
  party: string;
  electorate: string;
  political_bloc: string;
  category: string;
  sub_category: string;
  item: string;
  entity: string;
  canonical_entity: string; // Standard form of the entity name
  declaration_date: string;
  details: string;
  pdf_source: string;
}
```

| Field | Type | Description |
|-------|------|-------------|
| id | string | Unique identifier for the disclosure entry |
| mp_name | string | Name of the MP who made the disclosure |
| party | string | Political party of the MP |
| electorate | string | Electorate represented by the MP |
| political_bloc | string | Political bloc (e.g., "Labor", "Coalition", "Independent") |
| category | string | Primary category of the disclosure (e.g., "Asset", "Liability") |
| sub_category | string | Sub-category of the disclosure (e.g., "Real Estate", "Mortgage") |
| item | string | Specific item disclosed |
| entity | string | Entity related to the disclosure, if any |
| canonical_entity | string | Standardized form of the entity name, used to group variants |
| declaration_date | string | Date when the disclosure was made (YYYY-MM-DD) |
| details | string | Additional details about the disclosure |
| pdf_source | string | Name of the PDF file from which the disclosure was extracted |

## Entity Details Schema

The Entity Details schema represents detailed information about an entity and its connections.

```typescript
interface EntityDetails {
  entity: string;
  count: number;
  variants: string[]; // Only populated when using canonical entities
  connected_mps: {
    mp_name: string;
    party: string;
    electorate: string;
    political_bloc: string;
  }[];
}
```

| Field | Type | Description |
|-------|------|-------------|
| entity | string | Name of the entity |
| count | number | Number of disclosures mentioning this entity |
| variants | string[] | List of variant names that map to this canonical entity (only when canonical=true) |
| connected_mps | array | Array of MPs connected to this entity |
| connected_mps[].mp_name | string | Name of the connected MP |
| connected_mps[].party | string | Party of the connected MP |
| connected_mps[].electorate | string | Electorate of the connected MP |
| connected_mps[].political_bloc | string | Political bloc of the connected MP |

## Network Data Schema

The Network Data schema represents the nodes and links for the entity network visualization.

```typescript
interface NetworkData {
  nodes: NetworkNode[];
  links: NetworkLink[];
}

interface NetworkNode {
  id: string;
  name: string;
  type: 'mp' | 'entity';
  party?: string; // Only for MP nodes
  size?: number;
  political_bloc?: string; // Only for MP nodes
}

interface NetworkLink {
  source: string;
  target: string;
  weight: number;
}
```

| Field | Type | Description |
|-------|------|-------------|
| nodes | array | Array of nodes in the network |
| nodes[].id | string | Unique identifier for the node |
| nodes[].name | string | Display name for the node |
| nodes[].type | string | Type of node ("mp" or "entity") |
| nodes[].party | string | Political party (for MP nodes only) |
| nodes[].political_bloc | string | Political bloc (for MP nodes only) |
| nodes[].size | number | Relative size of the node (based on connections) |
| links | array | Array of links between nodes |
| links[].source | string | ID of the source node |
| links[].target | string | ID of the target node |
| links[].weight | number | Weight/strength of the connection |

When the `canonical=true` parameter is used, entity nodes will represent canonical entities rather than original entity names. 