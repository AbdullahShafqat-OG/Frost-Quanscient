<script setup lang="ts">
import { computed } from 'vue'
import { useAnalysisStore } from '@/stores/analysisStore'
import ParameterPanel from '@/components/ParameterPanel.vue'
import GeometryViewer from '@/components/GeometryViewer.vue'
import ResultsChart from '@/components/ResultsChart.vue'
import VerdictCard from '@/components/VerdictCard.vue'

const store = useAnalysisStore()

const showResults = computed(() => store.hasResults)
</script>

<template>
  <div class="min-h-screen text-grey-900">
    <!-- Header -->
    <header class="bg-white border-b border-grey-200 sticky top-0 z-50">
      <div class="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <img src="/pipe.svg" alt="" class="w-8 h-8" />
          <div>
            <h1 class="text-xl font-semibold text-grey-900">
              Pipe Freeze-Risk Analyser
            </h1>
            <p class="text-xs text-grey-500 tracking-wide">Powered by Quanscient Allsolve</p>
          </div>
        </div>

        <a
          href="https://quanscient.com"
          target="_blank"
          class="text-sm text-primary-500 hover:text-primary-700 font-medium transition-colors"
        >
          quanscient.com →
        </a>
      </div>
    </header>

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto px-6 py-6">
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Left Panel: Inputs -->
        <div class="lg:col-span-1">
          <ParameterPanel />
        </div>

        <!-- Center Panel: Cross-section & Verdict -->
        <div class="lg:col-span-1 space-y-6">
          <div class="card p-4 h-[380px]">
            <GeometryViewer />
          </div>
          <VerdictCard />
        </div>

        <!-- Right Panel: Results Chart -->
        <div class="lg:col-span-1">
          <div class="card p-6 h-full min-h-[500px]">
            <h2 class="text-base font-semibold text-grey-900 mb-4 flex items-center gap-2">
              <svg class="w-5 h-5 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
              </svg>
              Water Temperature &amp; Ice
            </h2>

            <div v-if="showResults">
              <ResultsChart />
            </div>

            <div v-else class="h-[400px] flex items-center justify-center text-grey-400">
              <div class="text-center">
                <svg class="w-12 h-12 mx-auto mb-3 text-grey-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"/>
                </svg>
                <p class="text-sm font-medium text-grey-500">Run an analysis to see results</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Info Section -->
      <section class="mt-8 card p-8">
        <h2 class="text-lg font-semibold text-grey-900 mb-6">The Physics</h2>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-8 text-sm">
          <div>
            <h3 class="font-semibold text-primary-600 mb-2">Heat conduction with freezing</h3>
            <div class="font-mono bg-grey-50 border border-grey-200 p-3 rounded-lg text-grey-800 text-xs">
              ρCₚ,eff ∂T/∂t = ∇·(k∇T)<br />
              ρCₚ,eff = ρCₚ + ρL·e^(−((T−0°C)/ΔT)²)/(ΔT√π)
            </div>
            <p class="mt-2 text-grey-600">
              Water, pipe wall and insulation solved in 3D. The latent heat of freezing (334 kJ/kg) is
              added as an apparent heat capacity around 0°C.
            </p>
          </div>

          <div>
            <h3 class="font-semibold text-primary-600 mb-2">Heat loss to the surroundings</h3>
            <div class="font-mono bg-grey-50 border border-grey-200 p-3 rounded-lg text-grey-800 text-xs">
              q = h (T_surface − T_surroundings)
            </div>
            <p class="mt-2 text-grey-600">
              The surroundings and h depend on where the pipe is: outside air with a 3 m/s wind, a wall
              cavity between indoor and outside temperature, or soil that cools slowly from the surface.
              h is estimated from convection and radiation at the outside temperature. A drip adds warm
              water, modelled as a heat source.
            </p>
          </div>

          <div>
            <h3 class="font-semibold text-primary-600 mb-2">What the numbers mean</h3>
            <ul class="space-y-1 text-grey-600">
              <li><span class="text-grey-900 font-medium">First ice:</span> coldest water reaches 0°C</li>
              <li><span class="text-grey-900 font-medium">Blocked:</span> 90% of the water is frozen</li>
              <li><span class="text-grey-900 font-medium">Critical outside temperature:</span> the outside temperature at which the pipe is blocked by the end of the cold snap</li>
            </ul>
          </div>
        </div>
      </section>
    </main>

    <!-- Footer -->
    <footer class="border-t border-grey-200 mt-8 py-5 bg-white">
      <div class="max-w-7xl mx-auto px-6 text-center text-xs text-grey-500">
        <p>Built with Vue 3, Chart.js and the Quanscient Allsolve SDK</p>
      </div>
    </footer>
  </div>
</template>
