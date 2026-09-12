<template>
  <div>
    <div class="page-card" style="margin-bottom:16px">
      <h3 class="page-title">巡场记录上报</h3>
      <el-form :model="form" label-width="100px">
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="涉事宠物" required>
              <el-select v-model="form.pet_id" filterable style="width:100%">
                <el-option v-for="p in pets" :key="p.id" :label="`${p.name}（${p.breed}·${p.owner_name}）`" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="所在分区" required>
              <el-select v-model="form.zone_id" style="width:100%">
                <el-option v-for="z in zones" :key="z.id" :label="z.name" :value="z.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="行为类型" required>
              <el-select v-model="form.incident_type" style="width:100%">
                <el-option v-for="(l, v) in incidentTypes" :key="v" :label="l" :value="v" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="严重程度">
              <el-select v-model="form.severity" style="width:100%">
                <el-option label="轻微" value="low" />
                <el-option label="一般" value="medium" />
                <el-option label="严重" value="high" />
                <el-option label="紧急" value="critical" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="有人/宠受伤">
              <el-switch v-model="form.has_injury" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="主人配合">
              <el-switch v-model="form.owner_cooperative" active-text="配合" inactive-text="拒不配合" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="情况描述">
              <el-input v-model="form.description" type="textarea" :rows="2"
                        placeholder="追逐、吠叫、争抢玩具、咬伤、未清理粪便、设备损坏等情况" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-button type="primary" :loading="submitting" @click="submit">提交巡场记录</el-button>
      </el-form>
    </div>

    <div class="page-card">
      <div class="toolbar">
        <h3 class="page-title" style="margin:0;flex:1">巡场记录</h3>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </div>
      <el-table :data="incidents" v-loading="loading">
        <el-table-column prop="code" label="编号" width="110" />
        <el-table-column prop="pet_name" label="宠物" width="90" />
        <el-table-column prop="incident_type_label" label="行为" width="100" />
        <el-table-column prop="zone_name" label="分区" width="100" />
        <el-table-column label="严重度" width="90">
          <template #default="{ row }">
            <el-tag :type="severityType(row.severity)" size="small">{{ row.severity_label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="受伤" width="70">
          <template #default="{ row }">
            <el-tag v-if="row.has_injury" type="danger" size="small">有</el-tag><span v-else>无</span>
          </template>
        </el-table-column>
        <el-table-column label="主人配合" width="90">
          <template #default="{ row }">
            <el-tag :type="row.owner_cooperative ? 'success' : 'danger'" size="small">
              {{ row.owner_cooperative ? '配合' : '拒不配合' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip />
        <el-table-column prop="occurred_at" label="时间" width="140" />
        <el-table-column label="事件" width="110">
          <template #default="{ row }">
            <el-link v-if="row.event_id" type="primary" @click="$router.push(`/events/${row.event_id}`)">
              事件#{{ row.event_id }}
            </el-link>
            <el-button v-else link type="danger" @click="openEscalate(row)">升级事件</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="escalateVisible" title="升级为协同事件" width="520px">
      <el-form label-width="90px">
        <el-form-item label="事件标题" required><el-input v-model="escalateForm.title" /></el-form-item>
        <el-form-item label="事件类型">
          <el-select v-model="escalateForm.event_type" style="width:100%">
            <el-option v-for="(l, v) in eventTypes" :key="v" :label="l" :value="v" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="escalateForm.priority" style="width:100%">
            <el-option label="低" value="low" /><el-option label="中" value="medium" />
            <el-option label="高" value="high" /><el-option label="紧急" value="critical" />
          </el-select>
        </el-form-item>
        <el-form-item label="补充说明">
          <el-input v-model="escalateForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <el-alert type="warning" :closable="false"
                title="升级后平台将自动把巡场员、园区管理、宠物主人、合作医院、客服串到同一事件协同处置" />
      <template #footer>
        <el-button @click="escalateVisible = false">取消</el-button>
        <el-button type="danger" :loading="escalating" @click="doEscalate">确认升级</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const router = useRouter()
const pets = ref([])
const zones = ref([])
const incidents = ref([])
const loading = ref(false)
const submitting = ref(false)
const escalateVisible = ref(false)
const escalating = ref(false)
const currentIncident = ref(null)

const incidentTypes = {
  chasing: '追逐', barking: '吠叫', toy_fight: '争抢玩具', bite: '咬伤',
  waste: '未清理粪便', equipment_damage: '设备损坏', other: '其他',
}
const eventTypes = {
  pet_conflict: '宠物冲突', injury: '人员受伤', vaccine_expired: '疫苗过期',
  uncooperative: '主人拒不配合', overcrowding: '活动区超员', other: '其他',
}

const form = reactive({
  pet_id: null, zone_id: null, incident_type: 'chasing', severity: 'low',
  description: '', has_injury: false, owner_cooperative: true,
})
const escalateForm = reactive({ title: '', event_type: 'pet_conflict', priority: 'high', description: '' })

function severityType(s) {
  return { low: 'info', medium: 'warning', high: 'danger', critical: 'danger' }[s]
}

async function load() {
  loading.value = true
  try {
    incidents.value = await api.get('/incidents')
  } finally {
    loading.value = false
  }
}

async function submit() {
  if (!form.pet_id || !form.zone_id) {
    ElMessage.warning('请选择宠物和分区')
    return
  }
  submitting.value = true
  try {
    await api.post('/incidents', form)
    ElMessage.success('巡场记录已提交')
    Object.assign(form, { pet_id: null, zone_id: null, description: '', has_injury: false, owner_cooperative: true })
    load()
  } finally {
    submitting.value = false
  }
}

function openEscalate(row) {
  currentIncident.value = row
  escalateForm.title = `${row.zone_name}${row.incident_type_label}事件：${row.pet_name}`
  escalateForm.event_type = row.has_injury ? 'injury'
    : row.incident_type === 'bite' ? 'pet_conflict'
    : !row.owner_cooperative ? 'uncooperative' : 'pet_conflict'
  escalateForm.priority = { low: 'medium', medium: 'high', high: 'high', critical: 'critical' }[row.severity]
  escalateForm.description = row.description
  escalateVisible.value = true
}

async function doEscalate() {
  escalating.value = true
  try {
    const res = await api.post(`/incidents/${currentIncident.value.id}/escalate`, escalateForm)
    ElMessage.success(`已升级为事件 ${res.event_code}`)
    escalateVisible.value = false
    router.push(`/events/${res.event_id}`)
  } finally {
    escalating.value = false
  }
}

onMounted(async () => {
  pets.value = await api.get('/pets')
  zones.value = await api.get('/zones')
  load()
})
</script>
