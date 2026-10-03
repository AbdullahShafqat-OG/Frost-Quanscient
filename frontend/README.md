# Pipe Freeze-Risk Analyser Frontend

A Vue 3 application for analysing the freeze risk of a water pipe (underground, indoors or outdoors).

## Tech Stack

- **Vue 3** with Composition API
- **TypeScript** for type safety
- **Pinia** for state management
- **Chart.js + vue-chartjs** for temperature and ice-fraction charts
- **Tailwind CSS** for styling
- **Vite** for development and building

## Setup

1. Install dependencies:
```bash
npm install
```

2. Start development server:
```bash
npm run dev
```

The app will be available at http://localhost:5173

## Features

- **Inputs** in three groups: Pipe (wall, diameter, material, insulation + thickness), External conditions (location — fixed to outdoors and shown disabled — outside temperature, cold snap), Water (initial temperature, drip)
- **Cross-section diagram**: water / wall / insulation drawn from the inputs on a location backdrop, with the ice layer after a run
- **Charts**: water temperature (coldest + average) with a 0 °C line, ice fraction, and first-ice / blockage markers
- **Verdict card**: critical outside temperature, time to first ice and blockage, advice, assumed conditions, per-temperature table, model limits
- **Two modes**: Full simulation (Allsolve) or Demo (local estimate, instant)

## Project Structure

```
src/
├── api/                 # API client for backend
│   └── analysis.ts
├── assets/              # CSS and static assets
├── components/          # Vue components
│   ├── GeometryViewer.vue    # Pipe cross-section diagram
│   ├── ParameterPanel.vue    # Inputs + Full/Demo toggle
│   ├── ResultsChart.vue      # Temperature and ice charts
│   └── VerdictCard.vue       # Verdict, key numbers, advice
├── stores/              # Pinia stores
│   └── analysisStore.ts
├── types/               # TypeScript type definitions
├── App.vue              # Root component
└── main.ts              # Application entry
```

## Development

### Build for production
```bash
npm run build
```

### Preview production build
```bash
npm run preview
```

## Configuration

The frontend proxies API requests to `http://localhost:8000` during development.
Update `vite.config.ts` to change the backend URL.
