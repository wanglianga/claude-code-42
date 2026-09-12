<template>
  <div>
    <div class="stat-grid">
      <div v-for="c in cards" :key="c.label" class="stat-card">
        <div class="label">{{ c.label }}</div>
        <div class="num" :style="{ color: c.color || '#409eff' }">{{ c.value }}</div>
      </div>
    </div>

    <div class="page-card">
      <h3 class="page-title">最近事件</h3>
      <el-table :data="events" size="default" @row-click="(r) => $router.push(`/events/${r.id}`)" style="cursor:pointer">
        <el-table-column prop="code" label="事件编号" width="120" />
        <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip />
        <el-table-column prop="event_type_label" label="类型" width="110" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status_label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="zone_name" label="分区" width="100" />
        <el-table-column prop="created_at" label="创建时间" width="140" />
      </el-table>
      <el-empty v-if="!events.length" description="暂无事件" :image-size="60" />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../api'

const cards = ref([])
const events = ref([])

const CARD_META = {
  pets: ['我的宠物', '#409eff'],
  upcoming: ['待入园预约', '#67c23a'],
  open_events: ['进行中事件', '#e6a23c'],
  blacklist: ['黑名单记录', '#f56c6c'],
  today_confirmed: ['今日待核验', '#409eff'],
  today_checked: ['今日已核验', '#67c23a'],
  today_failed: ['今日核验未过', '#f56c6c'],
  my_incidents: ['我的巡场记录', '#409eff'],
  today_reservations: ['今日入园预约', '#409eff'],
  active_blacklist: ['生效黑名单', '#f56c6c'],
  pending_rectifications: ['待整改设施', '#e6a23c'],
  total_pets: ['在册宠物', '#409eff'],
  total_incidents: ['累计巡场记录', '#909399'],
}

function statusType(s) {
  return { open: 'danger', processing: 'warning', closed: 'success' }[s] || 'info'
}

onMounted(async () => {
  const data = await api.get('/analytics/dashboard')
  cards.value = Object.entries(CARD_META)
    .filter(([k]) => k in data)
    .map(([k, [label, color]]) => ({ label, color, value: data[k] }))
  events.value = data.recent_events || []
})
</script>
