<template>
  <div class="page-card">
    <div class="toolbar">
      <h3 class="page-title" style="margin:0;flex:1">黑名单与活动资格限制</h3>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>
    <el-alert v-if="isOwner" type="warning" :closable="false" style="margin-bottom:12px"
              title="黑名单（限制入园/永久拉黑）将导致预约与活动报名被拒绝；警告级仅作提示。" />

    <el-tabs>
      <el-tab-pane :label="`黑名单(${blacklist.length})`">
        <el-table :data="blacklist" v-loading="loading">
          <el-table-column prop="pet_name" label="宠物" width="100">
            <template #default="{ row }">{{ row.pet_name || '-' }}</template>
          </el-table-column>
          <el-table-column prop="owner_name" label="主人" width="100" />
          <el-table-column label="级别" width="100">
            <template #default="{ row }">
              <el-tag :type="{ warning: 'warning', restricted: 'danger', banned: 'danger' }[row.level]" size="small">
                {{ row.level_label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="reason" label="原因" min-width="200" show-overflow-tooltip />
          <el-table-column label="关联事件" width="100">
            <template #default="{ row }">
              <el-link v-if="row.event_id" type="primary" @click="$router.push(`/events/${row.event_id}`)">
                #{{ row.event_id }}
              </el-link>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.active ? 'danger' : 'info'" size="small">
                {{ row.active ? '生效中' : '已解除' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="140" />
          <el-table-column v-if="isManager" label="操作" width="90" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.active" link type="primary" @click="lift(row)">解除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!blacklist.length" description="暂无黑名单" :image-size="60" />
      </el-tab-pane>

      <el-tab-pane :label="`活动资格限制(${restrictions.length})`">
        <el-table :data="restrictions">
          <el-table-column prop="pet_name" label="宠物" width="100" />
          <el-table-column prop="restriction_label" label="限制类型" width="170" />
          <el-table-column prop="reason" label="原因" min-width="200" show-overflow-tooltip />
          <el-table-column label="关联事件" width="100">
            <template #default="{ row }">
              <el-link v-if="row.event_id" type="primary" @click="$router.push(`/events/${row.event_id}`)">
                #{{ row.event_id }}
              </el-link>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.active ? 'warning' : 'info'" size="small">
                {{ row.active ? '生效中' : '已解除' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="140" />
          <el-table-column v-if="isManager" label="操作" width="90" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.active" link type="primary" @click="liftRestriction(row)">解除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!restrictions.length" description="暂无限制" :image-size="60" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'
import { useAuthStore } from '../store'

const auth = useAuthStore()
const blacklist = ref([])
const restrictions = ref([])
const loading = ref(false)

const isManager = computed(() => ['manager', 'admin'].includes(auth.role))
const isOwner = computed(() => auth.role === 'owner')

async function load() {
  loading.value = true
  try {
    blacklist.value = await api.get('/blacklist')
    restrictions.value = await api.get('/blacklist/restrictions')
  } finally {
    loading.value = false
  }
}

async function lift(row) {
  await ElMessageBox.confirm(`确认解除该黑名单（${row.level_label}）？解除后预约限制同步失效。`, '提示', { type: 'warning' })
  await api.post(`/blacklist/${row.id}/lift`)
  ElMessage.success('已解除')
  load()
}

async function liftRestriction(row) {
  await ElMessageBox.confirm(`确认解除限制「${row.restriction_label}」？`, '提示', { type: 'warning' })
  await api.post(`/blacklist/restrictions/${row.id}/lift`)
  ElMessage.success('已解除')
  load()
}

onMounted(load)
</script>
