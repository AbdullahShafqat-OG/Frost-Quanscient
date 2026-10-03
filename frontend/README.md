# Frost frontend

Vue 3 interface for the water-pipe freezing simulator.

Run npm install, then npm run dev. The Vite server at http://localhost:5173
proxies /api to the FastAPI backend at http://localhost:8000.

Run npm run build for TypeScript checking and the production bundle.
See the root README for physics, Allsolve credentials and backend setup.

The active interface is src/App.vue, with PipeChart.vue and types/pipe.ts.
The former beer components and store are retained as inactive reference code.

