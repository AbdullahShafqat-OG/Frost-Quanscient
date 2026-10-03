<script setup lang="ts">
const props = defineProps<{
  modelValue: number; label: string; min: number; max: number; step: number; unit: string
}>()
const emit = defineEmits<{ (event: 'update:modelValue', value: number): void }>()
const id = props.label.toLowerCase().replace(/[^a-z0-9]+/g, '-')
function update(event: Event) {
  emit('update:modelValue', (event.target as HTMLInputElement).valueAsNumber)
}
</script>
<template>
  <div class="slider-control">
    <label :for="id">{{ label }}</label>
    <div class="slider-value-row">
      <input :id="id" type="range" :value="modelValue" :min="min" :max="max" :step="step" @input="update" />
      <div class="number-input"><input :id="id + '-number'" :aria-label="label + ' numeric value'" type="number" :value="modelValue" :min="min" :max="max" :step="step" required @input="update" /><span>{{ unit }}</span></div>
    </div>
    <div class="slider-bounds"><span>{{ min }} {{ unit }}</span><span>{{ max }} {{ unit }}</span></div>
  </div>
</template>
<style scoped>
.slider-control { margin-top:12px; }
.slider-value-row { display:flex; align-items:center; gap:13px; }
.slider-value-row > input { flex:1; min-width:0; accent-color:#087f79; }
.slider-value-row > .number-input { width:98px; flex-shrink:0; }
.slider-bounds { display:flex; justify-content:space-between; margin-top:4px; padding-right:111px; color:#8a9ca6; font-size:12px; }
</style>
