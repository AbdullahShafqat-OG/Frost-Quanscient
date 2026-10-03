<script setup lang="ts">
import { computed } from 'vue'
import { useAnalysisStore } from '@/stores/analysisStore'
import { formatHours, formatTemperature, type VerdictLevel } from '@/types'

const store = useAnalysisStore()

const results = computed(() => store.results)

const LEVEL_STYLE: Record<VerdictLevel, { label: string; icon: string; classes: string }> = {
  safe: { label: 'Safe', icon: '✓', classes: 'bg-green-50 text-green-800 border-green-200' },
  at_risk: { label: 'At risk', icon: '!', classes: 'bg-amber-50 text-amber-800 border-amber-200' },
  freezes: { label: 'Freezes', icon: '✕', classes: 'bg-red-50 text-red-800 border-red-200' },
}

const level = computed(() => (results.value ? LEVEL_STYLE[results.value.verdict.level] : null))

const sweepRows = computed(() =>
  [...(results.value?.sweep ?? [])].sort((a, b) => b.ambient_c - a.ambient_c)
)
</script>

<template>
  <div class="card p-6">
    <!-- Empty state -->
    <div v-if="!results" class="text-center text-sm text-grey-500 py-6">
      <p class="font-medium text-grey-700 mb-1">How cold, for how long, before the pipe freezes?</p>
      <p>Set the pipe and the cold snap, then run the analysis to get the critical temperature and advice.</p>
    </div>

    <div v-else class="space-y-4">
      <div class="flex items-center justify-between">
        <span class="text-xs uppercase tracking-wider text-grey-500">Verdict</span>
        <span
          class="text-xs px-2 py-0.5 rounded-full border"
          :class="results.mode === 'demo' ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-green-50 text-green-700 border-green-200'"
        >
          {{ results.mode === 'demo' ? 'Demo (local estimate)' : 'Full simulation (Allsolve)' }}
        </span>
      </div>

      <!-- Headline -->
      <div v-if="level" class="flex gap-3 p-3 rounded-lg border" :class="level.classes">
        <span class="flex-shrink-0 w-6 h-6 rounded-full border border-current flex items-center justify-center text-sm font-bold">
          {{ level.icon }}
        </span>
        <div>
          <div class="text-xs font-semibold uppercase tracking-wide">{{ level.label }}</div>
          <div class="text-sm font-medium">{{ results.verdict.headline }}</div>
        </div>
      </div>

      <!-- Key numbers -->
      <div class="grid grid-cols-3 gap-3 text-center">
        <div>
          <div class="text-xs text-grey-500">Critical outside</div>
          <div class="font-mono text-lg text-primary-600">{{ formatTemperature(results.critical_ambient_c) }}</div>
          <div class="text-[10px] text-grey-400">for {{ results.parameters.cold_snap_hours }} h</div>
        </div>
        <div>
          <div class="text-xs text-grey-500">First ice</div>
          <div class="font-mono text-lg text-grey-800">{{ formatHours(results.t_onset_hours) }}</div>
          <div class="text-[10px] text-grey-400">at {{ results.parameters.outside_temp_c }}°C</div>
        </div>
        <div>
          <div class="text-xs text-grey-500">Blocked</div>
          <div class="font-mono text-lg" :class="results.t_blockage_hours !== null ? 'text-red-600' : 'text-grey-400'">
            {{ formatHours(results.t_blockage_hours) }}
          </div>
          <div class="text-[10px] text-grey-400">90% ice</div>
        </div>
      </div>

      <!-- Details -->
      <ul class="text-sm text-grey-700 space-y-1 list-disc pl-5">
        <li v-for="line in results.verdict.details" :key="line">{{ line }}</li>
      </ul>

      <!-- Actions -->
      <div>
        <div class="text-xs font-semibold uppercase tracking-wide text-grey-500 mb-1">What to do</div>
        <ul class="text-sm text-grey-800 space-y-1 list-disc pl-5">
          <li v-for="line in results.verdict.actions" :key="line">{{ line }}</li>
        </ul>
      </div>

      <!-- Sweep table -->
      <div v-if="sweepRows.length">
        <div class="text-xs font-semibold uppercase tracking-wide text-grey-500 mb-1">By outside temperature</div>
        <table class="w-full text-xs">
          <thead>
            <tr class="text-grey-500 border-b border-grey-200">
              <th class="text-left font-medium py-1">Outside</th>
              <th class="text-right font-medium py-1">First ice</th>
              <th class="text-right font-medium py-1">Blocked</th>
            </tr>
          </thead>
          <tbody class="font-mono text-grey-800">
            <tr
              v-for="row in sweepRows"
              :key="row.ambient_c"
              class="border-b border-grey-100"
              :class="row.ambient_c === results.parameters.outside_temp_c ? 'bg-primary-50' : ''"
            >
              <td class="py-1">{{ row.ambient_c }}°C</td>
              <td class="text-right py-1">{{ formatHours(row.t_onset_hours) }}</td>
              <td class="text-right py-1">{{ formatHours(row.t_blockage_hours) }}</td>
            </tr>
          </tbody>
        </table>
        <p class="text-[10px] text-grey-400 mt-1">— = not within the {{ results.window_hours }} h analysed</p>
      </div>

      <!-- Assumed conditions -->
      <div>
        <div class="text-xs font-semibold uppercase tracking-wide text-grey-500 mb-1">Assumed conditions</div>
        <ul class="text-xs text-grey-600 space-y-1 list-disc pl-5">
          <li v-for="line in results.assumptions" :key="line">{{ line }}</li>
        </ul>
      </div>

      <!-- Caveats -->
      <details class="text-xs text-grey-500">
        <summary class="cursor-pointer select-none">Model limits</summary>
        <ul class="mt-2 space-y-1 list-disc pl-5">
          <li v-for="line in results.verdict.caveats" :key="line">{{ line }}</li>
        </ul>
        <p class="mt-2">
          Estimated external heat transfer coefficient: {{ results.h_out.toFixed(1) }} W/(m²·K).
          Pipe surroundings at the end of the cold snap: {{ formatTemperature(results.surroundings_c) }}.
        </p>
      </details>
    </div>
  </div>
</template>
