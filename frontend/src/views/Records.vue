<template>
  <div class="page-card">
    <div class="toolbar">
      <h3 class="page-title" style="margin:0;flex:1">园区运营记录</h3>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>
    <el-table :data="records" v-loading="loading">
      <el-table-column label="类型" width="110">
        <template #default="{ row }">
          <el-tag size="small" effect="plain">{{ row.record_type_label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
      <el-table-column prop="content" label="内容" min-width="320" show-overflow-tooltip />
      <el-table-column label="关联事件" width="90">
        <template #default="{ row }">
          <el-link v-if="row.related_event_id" type="primary" @click="$router.push(`/events/${row.related_event_id}`)">
            #{{ row.related_event_id }}
          </el-link>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="creator" label="操作人" width="90" />
      <el-table-column prop="created_at" label="时间" width="140" />
    </el-table>
    <el-empty v-if="!records.length && !loading" description="暂无运营记录" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import api from '../api'

const records = ref([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    records.value = await api.get('/analytics/records')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
