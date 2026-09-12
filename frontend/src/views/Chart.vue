<template>
  <div ref="el" :style="{ height: height + 'px', width: '100%' }"></div>
</template>

<script setup>
import * as echarts from 'echarts'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  option: { type: Object, required: true },
  height: { type: Number, default: 300 },
})
const el = ref()
let chart = null
const resize = () => chart && chart.resize()

onMounted(() => {
  chart = echarts.init(el.value)
  chart.setOption(props.option)
  window.addEventListener('resize', resize)
})
watch(() => props.option, (o) => chart && chart.setOption(o), { deep: true })
onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart && chart.dispose()
})
</script>
