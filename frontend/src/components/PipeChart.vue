<script setup lang="ts">
import { computed } from 'vue'
import { Line } from 'vue-chartjs'
import { Chart as ChartJS, LinearScale, PointElement, LineElement, Tooltip, Legend } from 'chart.js'
import type { PipeResult } from '@/types/pipe'
ChartJS.register(LinearScale, PointElement, LineElement, Tooltip, Legend)

const props = defineProps<{ result: PipeResult }>()

const timeScale = computed(() => props.result.end_hours < 1 ? 60 : 1)
const chartEnd = computed(() => Math.max(props.result.end_hours * timeScale.value, 0.001))

const hasIce = computed(() =>
  (props.result.rawSeries ?? []).some(s => s.ice_fraction > 0)
)

const data = computed(() => {
  const raw = props.result.rawSeries ?? []
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const datasets: any[] = [
    {
      label: 'Water temperature',
      data: props.result.history.map(p => ({ x: p.hours * timeScale.value, y: p.temperature_c })),
      borderColor: '#0d9488',
      backgroundColor: '#0d9488',
      pointRadius: 0,
      borderWidth: 2.5,
      yAxisID: 'yTemp',
    },
    {
      label: 'Freezing threshold',
      data: [{ x: 0, y: 0 }, { x: chartEnd.value, y: 0 }],
      borderColor: '#ea7657',
      borderDash: [5, 5],
      pointRadius: 0,
      borderWidth: 1.5,
      yAxisID: 'yTemp',
    },
  ]

  if (raw.length) {
    datasets.push({
      label: 'Ice fraction',
      data: raw.map(s => ({ x: s.time_hours * timeScale.value, y: s.ice_fraction * 100 })),
      borderColor: '#93c5fd',
      backgroundColor: 'rgba(147,197,253,0.12)',
      fill: true,
      pointRadius: 0,
      borderWidth: 2,
      yAxisID: 'yIce',
    })
  }

  return { datasets }
})

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const options = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  animation: false as const,
  interaction: { mode: 'index' as const, intersect: false },
  plugins: {
    legend: {
      position: 'bottom' as const,
      labels: { usePointStyle: true, boxWidth: 8, padding: 20, font: { size: 11 } },
    },
    tooltip: {
      callbacks: {
        label: (ctx: { dataset: { label?: string }; parsed: { y: number } }) => {
          if (ctx.dataset.label === 'Ice fraction') return `Ice fraction: ${ctx.parsed.y.toFixed(1)}%`
          if (ctx.dataset.label === 'Freezing threshold') return null as unknown as string
          return `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(2)} °C`
        },
      },
    },
  },
  scales: {
    x: {
      type: 'linear' as const,
      min: 0,
      max: chartEnd.value,
      title: { display: true, text: timeScale.value === 60 ? 'Cold exposure (minutes)' : 'Cold exposure (hours)', font: { size: 10 } },
      grid: { display: false },
    },
    yTemp: {
      type: 'linear' as const,
      position: 'left' as const,
      title: { display: true, text: 'Water temperature (°C)', font: { size: 10 } },
      suggestedMin: -1,
      grid: { color: '#edf1f3' },
    },
    yIce: {
      type: 'linear' as const,
      position: 'right' as const,
      min: 0,
      max: 100,
      display: hasIce.value,
      title: { display: hasIce.value, text: 'Ice fraction (%)', font: { size: 10 } },
      grid: { drawOnChartArea: false },
    },
  },
}))
</script>
<template><div class="chart-wrap"><Line :data="(data as any)" :options="(options as any)" /></div></template>
