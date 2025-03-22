# System Architecture Overview

The Australian Government Transparency Project is composed of three main components that work together to provide a complete solution for extracting, storing, and visualizing parliamentary financial disclosures.

## High-Level Architecture

![Architecture Diagram](../assets/architecture_diagram.png)

The system follows a three-tier architecture:

1. **Data Processing Backend**: Python scripts for scraping, processing PDFs, and database management
2. **API Server**: Flask-based REST API for accessing the structured data
3. **Frontend Visualization**: React-based web application for exploring and analyzing the data

## Component Interactions

```
+-------------------+       +---------------+       +-------------------+
| Data Processing   | ====> | SQLite        | <==== | API Server        |
| Backend           |       | Database      |       | (Flask)           |
+-------------------+       +---------------+       +-------------------+
                                                           ^
                                                           |
                                                           v
                                                   +-------------------+
                                                   | Frontend          |
                                                   | (React + TS)      |
                                                   +-------------------+
```

### Data Flow

1. **PDF Processing Pipeline**:
   - PDFs are downloaded from parliamentary websites
   - Gemini AI processes PDFs to extract structured data
   - Data is standardized and stored in SQLite database

2. **Data Access Pipeline**:
   - Frontend sends requests to the API server
   - API server queries the SQLite database
   - API server returns structured JSON data
   - Frontend transforms and visualizes the data

## Key Technologies

- **Backend**: Python, Google Gemini AI API, SQLite
- **API**: Flask, Flask-CORS
- **Frontend**: React, TypeScript, TanStack Query, D3.js for visualizations
- **Deployment**: Docker (optional)

## Directory Structure

```
/
├── api/                    # API server
│   └── app.py              # Main Flask application
├── aus-govt-transparency-viz/
│   ├── frontend/           # React frontend application
│   └── backend/            # Additional backend services
├── db/                     # Database modules and schema
├── pdfs/                   # Downloaded PDF files
├── scripts/                # Utility scripts
├── democracy/              # Core democracy modules
├── entity/                 # Entity extraction and analysis
├── utils/                  # Shared utility functions
└── docs/                   # Documentation
```

## Next Steps

- [Backend Architecture](./backend.md)
- [API Server Architecture](./api.md)
- [Frontend Architecture](./frontend.md) 