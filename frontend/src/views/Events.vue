<template>
  <div class="page-card">
    <div class="toolbar">
      <h3 class="page-title" style="margin:0;flex:1">事件协同</h3>
      <el-select v-model="filterStatus" placeholder="状态" clearable style="width:120px" @change="load">
        <el-option label="待处理" value="open" /><el-option label="处理中" value="processing" />
        <el-option label="已关闭" value="closed" />
      </el-select>
      <el-select v-model="filterType" placeholder="类型" clearable style="width:140px" @change="load">
        <el-option v-for="(l, v) in eventTypes" :key="v" :label="l" :value="v" />
      </el-select>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
      <el-button v-if="canCreate" type="primary" :icon="Plus" @click="openCreate">手动建事件</el-button>
    </div>

    <el-table :data="events" v-loading="loading" @row-click="(r) => $router.push(`/events/${r.id}`)" style="cursor:pointer">
      <el-table-column prop="code" label="编号" width="110" />
      <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip />
      <el-table-column prop="event_type_label" label="类型" width="110" />
      <el-table-column label="优先级" width="80">
        <template #default="{ row }">
          <el-tag :type="priorityType(row.priority)" size="small">{{ row.priority_label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ row.status_label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="zone_name" label="分区" width="100" />
      <el-table-column prop="pet_name" label="涉事宠物" width="100" />
      <el-table-column prop="creator_name" label="创建人" width="130" />
      <el-table-column prop="created_at" label="创建时间" width="140" />
    </el-table>
    <el-empty v-if="!events.length && !loading" description="暂无事件" />

    <el-dialog v-model="createVisible" title="手动创建事件（如活动区超员）" width="560px">
      <el-form label-width="90px">
        <el-form-item label="标题" required><el-input v-model="createForm.title" /></el-form-item>
        <el-form-item label="事件类型">
          <el-select v-model="createForm.event_type" style="width:100%">
            <el-option v-for="(l, v) in eventTypes" :key="v" :label="l" :value="v" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="createForm.priority" style="width:100%">
            <el-option label="低" value="low" /><el-option label="中" value="medium" />
            <el-option label="高" value="high" /><el-option label="紧急" value="critical" />
          </el-select>
        </el-form-item>
        <el-form-item label="所在分区">
          <el-select v-model="createForm.zone_id" clearable style="width:100%">
            <el-option v-for="z in zones" :key="z.id" :label="z.name" :value="z.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="涉事宠物">
          <el-select v-model="createForm.pet_id" clearable filterable style="width:100%">
            <el-option v-for="p in pets" :key="p.id" :label="`${p.name}（${p.breed}·${p.owner_name}）`" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="情况描述">
          <el-input v-model="createForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="doCreate">创建并串联五方</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import { useAuthStore } from '../store'

const auth = useAuthStore()
const router = useRouter()
const events = ref([])
const zones = ref([])
const pets = ref([])
const loading = ref(false)
const filterStatus = ref('')
const filterType = ref('')
const createVisible = ref(false)
const creating = ref(false)

const eventTypes = {
  pet_conflict: '宠物冲突', injury: '人员受伤', vaccine_expired: '疫苗过期',
  uncooperative: '主人拒不配合', overcrowding: '活动区超员', other: '其他',
}
const canCreate = computed(() => ['patrol', 'gate', 'manager', 'admin'].includes(auth.role))

const createForm = reactive({
  title: '', event_type: 'overcrowding', priority: 'high',
  zone_id: null, pet_id: null, description: '',
})

function statusType(s) {
  return { open: 'danger', processing: 'warning', closed: 'success' }[s]
}
function priorityType(p) {
  return { low: 'info', medium: '', high: 'warning', critical: 'danger' }[p]
}

async function load() {
  loading.value = true
  try {
    const params = {}
    if (filterStatus.value) params.status = filterStatus.value
    if (filterType.value) params.event_type = filterType.value
    events.value = await api.get('/events', { params })
  } finally {
    loading.value = false
  }
}

async function openCreate() {
  if (!zones.value.length) zones.value = await api.get('/zones')
  if (!pets.value.length) pets.value = await api.get('/pets')
  createVisible.value = true
}

async function doCreate() {
  if (!createForm.title) {
    ElMessage.warning('请填写标题')
    return
  }
  creating.value = true
  try {
    const ev = await api.post('/events', createForm)
    ElMessage.success(`事件 ${ev.code} 已创建`)
    createVisible.value = false
    router.push(`/events/${ev.id}`)
  } finally {
    creating.value = false
  }
}

onMounted(load)
</script>
