# API Endpoints Reference

The Australian Government Transparency Project provides a RESTful API for accessing the structured disclosure data. This document details all available endpoints, their parameters, and response formats.

## Base URL

All API endpoints are relative to the base URL:

```
http://localhost:3001/api
```

In production, this would be replaced with your actual API domain.

## Authentication

Currently, the API does not require authentication. For production use, consider implementing API key authentication.

## Response Format

All API responses are in JSON format. Successful responses typically return an array or object with the requested data. Error responses follow this format:

```json
{
  "error": "Error message",
  "status": 400
}
```

## Endpoints

### Get Disclosures

Retrieves disclosure entries with optional filtering.

```
GET /api/disclosures
```

#### Query Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| mp_name | string | Filter by MP name (partial match) | None |
| category | string | Filter by category (exact match) | None |
| entity | string | Filter by entity (partial match) | None |
| limit | integer | Maximum number of results to return | 100 |
| offset | integer | Number of results to skip | 0 |
| filter_nil | boolean | Whether to filter out "nil" entries | true |

#### Response

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "mp_name": "Jane Smith",
    "party": "Labor",
    "electorate": "Sydney",
    "category": "Asset",
    "sub_category": "Real Estate",
    "item": "Residential property",
    "entity": "N/A",
    "declaration_date": "2023-05-15",
    "details": "Family home in Sydney"
  },
  ...more disclosures...
]
```

#### Example

```
GET /api/disclosures?mp_name=Smith&category=Gift&limit=5
```

### Get Statistics

Retrieves statistics about disclosures, MPs, and entities.

```
GET /api/stats
```

#### Query Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| filter_nil | boolean | Whether to filter out "nil" entries | true |

#### Response

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
    { "mp_name": "Sarah Connor", "party": "Greens", "count": 38 },
    ...more MPs...
  ]
}
```

#### Example

```
GET /api/stats?filter_nil=false
```

### Get MPs

Retrieves a list of MPs with optional filtering.

```
GET /api/mps
```

#### Query Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| name | string | Filter by MP name (partial match) | None |
| party | string | Filter by party (exact match) | None |

#### Response

```json
[
  {
    "mp_name": "Jane Smith",
    "party": "Labor",
    "electorate": "Sydney"
  },
  {
    "mp_name": "John Doe",
    "party": "Liberal",
    "electorate": "Melbourne"
  },
  ...more MPs...
]
```

#### Example

```
GET /api/mps?party=Labor
```

### Get Entities

Retrieves a list of entities mentioned in disclosures.

```
GET /api/entities
```

#### Query Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| name | string | Filter by entity name (partial match) | None |
| limit | integer | Maximum number of results to return | 100 |

#### Response

```json
[
  {
    "entity": "Acme Corporation",
    "count": 15
  },
  {
    "entity": "Global Industries",
    "count": 12
  },
  ...more entities...
]
```

#### Example

```
GET /api/entities?name=Global&limit=5
```

### Get Network Data

Retrieves network data for entity explorer visualization.

```
GET /api/network
```

#### Query Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| filter_nil | boolean | Whether to filter out "nil" entries | true |

#### Response

```json
{
  "nodes": [
    {
      "id": "Jane Smith",
      "name": "Jane Smith",
      "type": "mp",
      "party": "Labor"
    },
    {
      "id": "Acme Corporation",
      "name": "Acme Corporation",
      "type": "entity"
    },
    ...more nodes...
  ],
  "links": [
    {
      "source": "Jane Smith",
      "target": "Acme Corporation",
      "weight": 3
    },
    ...more links...
  ]
}
```

#### Example

```
GET /api/network?filter_nil=true
```

### Get MP Details

Retrieves detailed information about a specific MP and their disclosures.

```
GET /api/mp/:name
```

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| name | string | MP name |

#### Response

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
    },
    ...more disclosures...
  ],
  "categories": [
    { "category": "Asset", "count": 15 },
    { "category": "Liability", "count": 8 },
    ...more categories...
  ],
  "entities": [
    { "entity": "Acme Corporation", "count": 3 },
    { "entity": "Global Industries", "count": 2 },
    ...more entities...
  ]
}
```

#### Example

```
GET /api/mp/Jane%20Smith
```

### Get PDF File

Serves a PDF file by filename.

```
GET /api/pdf/:filename
```

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| filename | string | PDF filename |

#### Response

Binary PDF file with appropriate content type.

#### Example

```
GET /api/pdf/smith_jane_47th.pdf
```

### Get PDF Info

Retrieves information about PDFs for a specific MP.

```
GET /api/pdf-info/:mp_name
```

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| mp_name | string | MP name |

#### Response

```json
{
  "pdfs": [
    {
      "filename": "smith_jane_47th.pdf",
      "url": "/api/pdf/smith_jane_47th.pdf",
      "parliament": "47th",
      "date": "2023-05-15"
    },
    ...more PDFs...
  ]
}
```

#### Example

```
GET /api/pdf-info/Jane%20Smith
```

### Get Timeline Data

Retrieves timeline data for visualizations.

```
GET /api/timeline
```

#### Response

```json
{
  "timeline": [
    { "month": "2023-01", "count": 120 },
    { "month": "2023-02", "count": 95 },
    ...more months...
  ],
  "categories": [
    { "month": "2023-01", "category": "Asset", "count": 45 },
    { "month": "2023-01", "category": "Gift", "count": 30 },
    ...more data...
  ]
}
```

#### Example

```
GET /api/timeline
```

### Get Nil Entries Statistics

Retrieves statistics about "nil" entries.

```
GET /api/nil-entries
```

#### Response

```json
{
  "total_nil_entries": 850,
  "nil_by_category": [
    { "category": "Asset", "count": 320 },
    { "category": "Liability", "count": 220 },
    ...more categories...
  ],
  "nil_by_party": [
    { "party": "Labor", "count": 380 },
    { "party": "Liberal", "count": 350 },
    ...more parties...
  ]
}
```

#### Example

```
GET /api/nil-entries
```

## Error Codes

| Status Code | Description |
|-------------|-------------|
| 400 | Bad Request - Invalid query parameters |
| 404 | Not Found - Resource not found |
| 500 | Internal Server Error - Server-side error |

## Rate Limits

Currently, there are no rate limits implemented. For production use, consider implementing rate limiting to prevent abuse.

## Next Steps

- [API Data Models](./data_models.md)
- [Frontend Services](../frontend/services.md) 