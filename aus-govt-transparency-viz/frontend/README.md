# Australian Government Transparency Dashboard

This is the frontend application for visualizing and exploring parliamentary disclosure data. It provides an interactive interface to analyze and understand financial interests and gifts received by Members of Parliament in Australia.

## Features

- **Dashboard Overview**: View key statistics and recent disclosures at a glance
- **MP Profiles**: Detailed profiles for each MP, including disclosure history and patterns
- **Disclosure Analytics**: Data visualizations showing disclosure trends, categories, and party comparisons
- **Gift Analysis**: Specialized analysis of gifts received by MPs, including type and source information
- **Entity Explorer**: Network visualization showing relationships between MPs and entities
- **Geographic View**: Visualize disclosures by electorate across Australia
- **Export Functionality**: Export raw data for further analysis in CSV or JSON formats

## Tech Stack

- **React**: Frontend UI library
- **TypeScript**: For type-safe code
- **React Router**: For navigation and routing
- **React Query**: For data fetching, caching, and state management
- **Recharts**: For data visualization and charts
- **Tailwind CSS**: For styling and responsive design

## Getting Started

### Prerequisites

- Node.js (v16 or higher)
- npm or yarn

### Installation

1. Clone the repository
```bash
git clone https://github.com/yourusername/aus-govt-transparency.git
cd aus-govt-transparency-viz/frontend
```

2. Install dependencies
```bash
npm install
# or
yarn install
```

3. Create a `.env` file with your API endpoint
```
VITE_API_URL=http://localhost:3001/api
```

4. Start the development server
```bash
npm run dev
# or
yarn dev
```

5. The application will be available at `http://localhost:5173`

## Project Structure

```
src/
├── components/          # Reusable UI components
│   ├── layout/          # Layout components (header, footer, etc.)
│   └── visualizations/  # Data visualization components
├── hooks/               # Custom React hooks
├── pages/               # Page components
├── services/            # API service layer
├── types/               # TypeScript type definitions
├── utils/               # Utility functions
├── App.tsx              # Main application component
├── main.tsx             # Application entry point
└── index.css            # Global styles
```

## Available Scripts

- `npm run dev` - Start the development server
- `npm run build` - Build the application for production
- `npm run preview` - Preview the production build locally
- `npm run lint` - Run ESLint to check for code quality issues
- `npm run test` - Run tests (when implemented)

## API Integration

The frontend communicates with a backend API to fetch disclosure data. The API endpoint is configured through the `.env` file. See the backend repository for API documentation.

## Future Enhancements

- Interactive network graph implementation
- Real-time data updates
- Member search with autocomplete
- Advanced filtering options
- User accounts for saving analyses
- Mobile-optimized views

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is part of the g0v (Gov Zero) initiative and is open-sourced under the MIT License.

## Acknowledgements

- Data provided by the Australian Parliament House
- Project inspired by the need for greater transparency in government
- g0v community for support and collaboration
