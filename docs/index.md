# Australian Government Transparency Project Documentation

## Documentation Directory

This directory contains comprehensive documentation for the Australian Government Transparency Project. For project overview, motivation, and quick start guide, please refer to the [main README](../README.md) in the project root.

## Documentation Structure

- **Pipeline & Architecture**
  - [System Overview](./architecture/overview.md): High-level architecture and pipeline stages
  - [Pipeline Modules](../README.md#pipeline-workflow): Preparation, Parsing, Cleaning, Output

- **Data Processing**
  - [Database Schema](./backend/database.md): Canonical database structure and operations
  - [PDF Processing](./backend/pdf_processing.md): PDF scraping and extraction pipeline
  - [Data Standardization](./backend/data_standardization.md): Cleaning and standardization workflows
  - [Entity Deduplication](./backend/entity_deduplication.md): Entity name standardization and deduplication
  - [LLM Guidance](./backend/llm_guidance.md): Guidelines for using Gemini 2.0 Flash

- **Workflows**
  - [Setup Guide](./workflows/setup.md): Installation and configuration
  - [Development Workflow](./workflows/development.md): Development guidelines
  - [Deployment](./workflows/deployment.md): Deployment procedures

## Contributing to Documentation

When contributing to the documentation:

1. Keep documentation in Markdown format
2. Maintain the established directory structure
3. Update the relevant sections when making code changes
4. Include code examples where helpful
5. Use relative links to reference other documentation files 