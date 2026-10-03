# Pipe Freeze-Risk Analyser Frontend

A Vue 3 application for analysing the freeze risk of a water pipe (underground, indoors or outdoors).

## Tech Stack

- **Vue 3** with Composition API
- **TypeScript** for type safety
- **Pinia** for state management
- **Chart.js + vue-chartjs** for temperature and ice-fraction charts
- **three.js** for the interactive 3D pipe model (lazy-loaded in its own chunk)
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
- **Cross-section diagram (front)**: water / wall / insulation drawn from the inputs on a location backdrop, with the ice layer after a run
- **Lengthwise section (side)**: the same layers cut along the pipe axis, with break lines, centre line and diameters
- **3D model**: stepped, cut-away pipe you can orbit with the mouse (drag / scroll) or keyboard (arrows, + / −, Home); exterior surfaces use physically based materials (brushed copper/steel, plastics, fibrous or cellular insulation), cut faces use the same hatching as the 2D sections
- **Accessible visuals**: every layer has its own section-lining pattern (45° lines for metals, cross-hatch for plastics, batt / zigzag / cell symbols for insulation, dashes for water, crystals for ice) so nothing relies on colour alone; views have text descriptions for screen readers
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
│   ├── GeometryViewer.vue    # Front cross-section (A–A)
│   ├── PipeSideSection.vue   # Lengthwise section (B–B)
│   ├── PipeViewer3D.vue      # Interactive 3D model (three.js)
│   ├── MaterialLegend.vue    # Hatched legend shared by the views
│   ├── SectionPatterns.vue   # SVG hatch <pattern> definitions
│   ├── ParameterPanel.vue    # Inputs + Full/Demo toggle
│   ├── ResultsChart.vue      # Temperature and ice charts
│   └── VerdictCard.vue       # Verdict, key numbers, advice
├── composables/         # Shared Vue logic
│   └── usePipeGeometry.ts    # Normalised radii + ice state for all pipe views
├── stores/              # Pinia stores
│   └── analysisStore.ts
├── visuals/             # Framework-agnostic drawing code
│   ├── materialStyles.ts     # Colours, hatch patterns, 3D surface looks per layer
│   ├── textures.ts           # Canvas textures (hatching, brushed/fibrous/cell detail)
│   └── pipeScene.ts          # three.js scene, camera, controls, geometry
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
