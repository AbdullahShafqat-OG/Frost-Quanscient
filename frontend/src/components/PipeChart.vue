<script setup lang="ts">
import { computed } from 'vue'
import { Line } from 'vue-chartjs'
import { Chart as ChartJS, LinearScale, PointElement, LineElement, Tooltip, Legend } from 'chart.js'
import type { PipeResult } from '@/types/pipe'
ChartJS.register(LinearScale, PointElement, LineElement, Tooltip, Legend)
const props = defineProps<{ result: PipeResult }>()
const timeScale = computed(() => props.result.end_hours < 1 ? 60 : 1)
const chartEnd = computed(() => Math.max(props.result.end_hours * timeScale.value, 0.001))
const data = computed(() => ({ datasets: [
  { label: 'Bulk water', data: props.result.history.map(p => ({ x: p.hours * timeScale.value, y: p.temperature_c })), borderColor: '#0d9488', backgroundColor: '#0d9488', pointRadius: 0, borderWidth: 3 },
  { label: 'Inner-wall interface', data: props.result.history.map(p => ({ x: p.hours * timeScale.value, y: p.interface_temperature_c })), borderColor: '#428bb8', backgroundColor: '#428bb8', pointRadius: 0, borderWidth: 2 },
  { label: 'Freezing threshold', data: [{ x: 0, y: 0 }, { x: chartEnd.value, y: 0 }], borderColor: '#ea7657', borderDash: [5, 5], pointRadius: 0, borderWidth: 1.5 },
] }))
const options = computed(() => ({ responsive: true, maintainAspectRatio: false, animation: false as const,
  plugins: { legend: { position: 'bottom' as const, labels: { usePointStyle: true, boxWidth: 8, padding: 20 } } },
  scales: { x: { type: 'linear' as const, min: 0, max: chartEnd.value, title: { display: true, text: timeScale.value === 60 ? 'Cold exposure (minutes)' : 'Cold exposure (hours)' }, grid: { display: false } },
    y: { title: { display: true, text: 'Water temperature (°C)' }, suggestedMin: -1, grid: { color: '#edf1f3' } } },
}))
</script>
<template><div class="chart-wrap"><Line :data="data" :options="options" /></div></template>
