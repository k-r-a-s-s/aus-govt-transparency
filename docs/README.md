# Australian Government Transparency Project Documentation

This directory contains documentation for the Australian Government Transparency Project.

## Data Enrichment Features

### Entity Deduplication

We've implemented a robust entity deduplication system to address the issue of inconsistent entity naming in political disclosure data. The system uses fuzzy matching algorithms to identify and consolidate similar entity names.

- [Entity Deduplication Overview](backend/entity_deduplication.md) - Technical details about the deduplication approach
- [Entity Deduplication API](api/entity_endpoints.md) - API endpoints that utilize canonical entity names

### Double Disclosure Detection

Our double disclosure detection system identifies cases where a single record contains multiple distinct entities (e.g., "ANZ and Commonwealth Bank"). We've developed two approaches:

1. **Pattern-based detection** - Identifies common separators and patterns
2. **AI-powered detection** - Uses Google's Gemini AI to accurately identify true multiple entities with high confidence

- [Double Disclosure Detection Overview](backend/double_disclosure_detection.md) - Technical details about the double disclosure detection system
- [Running Double Disclosure Detection](guides/running_double_disclosure_detection.md) - Step-by-step guide to run the workflow

## Guides

- [Basic Usage](guides/basic_usage.md) - Getting started with the project
- [Entity Explorer Usage](guides/entity_explorer_usage.md) - How to use the Entity Explorer tool
- [Data Processing Workflow](guides/data_processing_workflow.md) - End-to-end workflow for data processing
- [Contributing](guides/contributing.md) - How to contribute to the project

## Backend Documentation

- [Database Schema](backend/database_schema.md) - Details about the database structure
- [Entity Services](backend/entity_services.md) - Services for entity management
- [Entity Deduplication](backend/entity_deduplication.md) - Technical details on entity deduplication
- [Double Disclosure Detection](backend/double_disclosure_detection.md) - Technical details on double disclosure detection

## Frontend Documentation

- [Component Structure](frontend/component_structure.md) - Overview of React component structure
- [Entity Explorer](frontend/entity_explorer.md) - Documentation for the Entity Explorer tool
- [Data Visualization](frontend/data_visualization.md) - Information about data visualization components
- [State Management](frontend/state_management.md) - How state is managed in the frontend

## API Documentation

- [API Overview](api/overview.md) - General API information
- [Authentication](api/authentication.md) - Authentication details
- [Entity Endpoints](api/entity_endpoints.md) - API endpoints for entity data
- [Disclosure Endpoints](api/disclosure_endpoints.md) - API endpoints for disclosure data
- [Search Endpoints](api/search_endpoints.md) - API endpoints for search functionality 