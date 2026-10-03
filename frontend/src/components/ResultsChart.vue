<script setup lang="ts">
import { computed } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  Filler,
  type ChartOptions,
  type ChartData,
  type Plugin,
} from 'chart.js'
import { useAnalysisStore } from '@/stores/analysisStore'
import { formatHours } from '@/types'

ChartJS.register(LinearScale, PointElement, LineElement, Tooltip, Legend, Filler)

const store = useAnalysisStore()

const COLOR_MIN = '#0369A1'
const COLOR_AVG = '#6644D8'
const INK_MUTED = '#757575'
const GRID = 'rgba(224, 224, 224, 0.6)'

// Vertical event markers (first ice, blockage, end of cold snap), drawn on both charts
const markers = computed(() => {
  const r = store.results
  if (!r) return []
  const list = [{ x: r.parameters.cold_snap_hours, label: 'End of cold snap', color: '#9E9E9E' }]
  if (r.t_onset_hours !== null) list.push({ x: r.t_onset_hours, label: 'First ice', color: '#0284C7' })
  if (r.t_blockage_hours !== null) list.push({ x: r.t_blockage_hours, label: 'Blocked', color: '#DC2626' })
  return list
})

const markerPlugin: Plugin<'line'> = {
  id: 'eventMarkers',
  afterDatasetsDraw(chart) {
    const { ctx, chartArea, scales } = chart
    const showLabels = (chart.options.plugins as { eventLabels?: boolean } | undefined)?.eventLabels
    markers.value.forEach((m, i) => {
      const x = scales.x.getPixelForValue(m.x)
      if (x < chartArea.left || x > chartArea.right) return
      ctx.save()
      ctx.strokeStyle = m.color
      ctx.lineWidth = 1.5
      ctx.setLineDash([4, 3])
      ctx.beginPath()
      ctx.moveTo(x, chartArea.top)
      ctx.lineTo(x, chartArea.bottom)
      ctx.stroke()
      if (showLabels) {
        ctx.setLineDash([])
        ctx.fillStyle = '#424242'
        ctx.font = '10px Inter, sans-serif'
        const text = `${m.label} ${formatHours(m.x)}`
        const width = ctx.measureText(text).width
        const tx = Math.min(x + 4, chartArea.right - width)
        ctx.fillText(text, tx, chartArea.top + 12 + i * 12)
      }
      ctx.restore()
    })
  },
}

// 0 °C reference line on the temperature chart
const freezeLinePlugin: Plugin<'line'> = {
  id: 'freezeLine',
  beforeDatasetsDraw(chart) {
    const { ctx, chartArea, scales } = chart
    const y = scales.y.getPixelForValue(0)
    if (y < chartArea.top || y > chartArea.bottom) return
    ctx.save()
    ctx.strokeStyle = '#BDBDBD'
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.moveTo(chartArea.left, y)
    ctx.lineTo(chartArea.right, y)
    ctx.stroke()
    ctx.fillStyle = INK_MUTED
    ctx.font = '10px Inter, sans-serif'
    ctx.fillText('0°C', chartArea.left + 4, y - 4)
    ctx.restore()
  },
}

const xMax = computed(() => store.results?.window_hours ?? 1)

const tempData = computed<ChartData<'line'>>(() => ({
  datasets: [
    {
      label: 'Coldest water',
      data: store.series.map(p => ({ x: p.time_hours, y: p.t_min_water_c })),
      borderColor: COLOR_MIN,
      backgroundColor: COLOR_MIN,
      borderWidth: 2,
      pointRadius: 0,
      pointHoverRadius: 4,
    },
    {
      label: 'Average water',
      data: store.series.map(p => ({ x: p.time_hours, y: p.t_avg_water_c })),
      borderColor: COLOR_AVG,
      backgroundColor: COLOR_AVG,
      borderWidth: 2,
      borderDash: [6, 4],
      pointRadius: 0,
      pointHoverRadius: 4,
    },
  ],
}))

const iceData = computed<ChartData<'line'>>(() => ({
  datasets: [
    {
      label: 'Ice fraction',
      data: store.series.map(p => ({ x: p.time_hours, y: p.ice_fraction * 100 })),
      borderColor: COLOR_MIN,
      backgroundColor: 'rgba(3, 105, 161, 0.12)',
      borderWidth: 2,
      fill: 'origin',
      pointRadius: 0,
      pointHoverRadius: 4,
    },
  ],
}))

function baseOptions(yTitle: string, showXTitle: boolean): ChartOptions<'line'> {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 0 },
    interaction: { mode: 'index', intersect: false },
    plugins: {
      tooltip: {
        backgroundColor: 'rgba(33, 33, 33, 0.9)',
        padding: 10,
        titleFont: { family: 'Inter' },
        bodyFont: { family: 'Inter' },
        callbacks: {
          title: items => `t = ${formatHours(items[0].parsed.x)}`,
        },
      },
    },
    scales: {
      x: {
        type: 'linear',
        min: 0,
        max: xMax.value,
        title: { display: showXTitle, text: 'Time (hours)', color: INK_MUTED, font: { family: 'Inter', size: 11 } },
        grid: { color: GRID },
        ticks: { color: INK_MUTED, font: { family: 'Inter', size: 10 } },
      },
      y: {
        title: { display: true, text: yTitle, color: INK_MUTED, font: { family: 'Inter', size: 11 } },
        grid: { color: GRID },
        ticks: { color: INK_MUTED, font: { family: 'Inter', size: 10 } },
      },
    },
  }
}

const tempOptions = computed<ChartOptions<'line'>>(() => {
  const opts = baseOptions('Water temperature (°C)', false)
  opts.plugins!.legend = {
    display: true,
    position: 'bottom',
    labels: { color: '#424242', boxWidth: 18, boxHeight: 2, font: { family: 'Inter', size: 11 } },
  }
  opts.plugins!.tooltip!.callbacks!.label = item =>
    `${item.dataset.label}: ${(item.parsed.y as number).toFixed(1)}°C`
  ;(opts.plugins as Record<string, unknown>).eventLabels = true
  return opts
})

const iceOptions = computed<ChartOptions<'line'>>(() => {
  const opts = baseOptions('Ice (%)', true)
  opts.plugins!.legend = { display: false }
  opts.plugins!.tooltip!.callbacks!.label = item => `Ice: ${(item.parsed.y as number).toFixed(0)}%`
  opts.scales!.y!.min = 0
  opts.scales!.y!.max = 100
  return opts
})

const tempPlugins = [freezeLinePlugin, markerPlugin]
const icePlugins = [markerPlugin]
</script>

<template>
  <div class="space-y-3">
    <div class="h-[280px]">
      <Line :data="tempData" :options="tempOptions" :plugins="tempPlugins" />
    </div>
    <div class="h-[150px]">
      <Line :data="iceData" :options="iceOptions" :plugins="icePlugins" />
    </div>
    <p class="text-xs text-grey-500">
      At {{ store.results?.parameters.outside_temp_c }}°C outside ({{ store.results?.parameters.location }}).
      <template v-if="store.results?.mode === 'demo'">
        Demo estimate: lumped model, so coldest and average water coincide.
      </template>
    </p>
  </div>
</template>
