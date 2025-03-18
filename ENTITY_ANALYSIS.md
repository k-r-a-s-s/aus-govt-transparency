# Entity Analysis Tools

This directory contains tools for analyzing entities in parliamentary disclosure PDFs.

## Overview

The entity analysis tools allow you to:

1. Link disclosures to entities
2. Analyze entity timelines
3. Compare entities between MPs
4. Visualize entity data

## Tools

### 1. Link Entities

The `link_entities.py` script processes all existing disclosures and links them to entities in the database.

```bash
python link_entities.py --db-path disclosures.db
```

### 2. Analyze Entities

The `analyze_entities.py` script analyzes entity timelines for a specific MP or all MPs.

```bash
# List all MPs
python analyze_entities.py

# Analyze a specific MP's entities
python analyze_entities.py --mp "Peter Dutton" --output-dir outputs/analysis

# Analyze a specific entity
python analyze_entities.py --entity-id "b3f869ab-cd85-4e54-b75b-1e64ec2d8b97" --output-dir outputs/analysis

# Compare entities between two MPs
python analyze_entities.py --compare "Peter Dutton" "Anthony Albanese" --output-dir outputs/analysis
```

### 3. Visualize Entities

The `visualize_entities.py` script generates visualizations of entity timelines.

```bash
# Generate entity distribution visualization for an MP
python visualize_entities.py --mp "Peter Dutton" --output-dir outputs/visualizations

# Generate all visualizations for an MP
python visualize_entities.py --mp "Peter Dutton" --output-dir outputs/visualizations --all-visualizations

# Visualize a specific entity's timeline
python visualize_entities.py --entity-id "b3f869ab-cd85-4e54-b75b-1e64ec2d8b97" --output-dir outputs/visualizations
```

## Entity Timeline Analysis

The entity timeline analysis provides insights into:

- When an entity first appeared in disclosures
- When an entity last appeared in disclosures
- How many times an entity has appeared
- Changes in entity details over time

## Entity Comparison

The entity comparison tool allows you to:

- Compare entities between two MPs
- Identify common entities
- Analyze differences in entity portfolios

## Visualization Types

The visualization tools generate:

1. **Entity Distribution by Type**: Bar chart showing the distribution of entities by type for an MP
2. **Entity Changes Over Time**: Stacked area chart showing how an MP's entities change over time
3. **Entity Timeline**: Timeline visualization for a specific entity showing all appearances and details

## Database Schema

The entity analysis tools use the following database schema:

### Entities Table

- `id`: Unique identifier for the entity
- `entity_type`: Type of entity (e.g., Shares, Real Estate, etc.)
- `canonical_name`: Normalized name of the entity
- `first_appearance_date`: Date when the entity first appeared
- `last_appearance_date`: Date when the entity last appeared
- `is_active`: Whether the entity is currently active
- `mp_id`: MP who owns the entity
- `notes`: Additional notes about the entity

### Disclosures Table

- `id`: Unique identifier for the disclosure
- `mp_name`: Name of the MP
- `party`: Political party of the MP
- `electorate`: Electorate of the MP
- `declaration_date`: Date of the declaration
- `category`: Category of the disclosure
- `entity`: Name of the entity
- `details`: Details of the disclosure
- `pdf_url`: URL to the PDF
- `sub_category`: Sub-category of the disclosure
- `entity_id`: Foreign key to the entities table

## Future Improvements

- Add more sophisticated entity matching algorithms
- Implement entity relationship analysis
- Add temporal analysis of entity changes
- Create interactive visualizations
- Implement entity clustering by similarity