<template>
  <div>
    <!-- 主人：新建预约 -->
    <div v-if="isOwner" class="page-card" style="margin-bottom:16px">
      <h3 class="page-title">新建入园预约（活动区预约即活动报名）</h3>
      <el-form inline>
        <el-form-item label="宠物">
          <el-select v-model="booking.pet_id" placeholder="选择宠物" style="width:160px">
            <el-option v-for="p in pets" :key="p.id" :label="`${p.name}（${p.breed}）`" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期">
          <el-date-picker v-model="booking.visit_date" type="date" value-format="YYYY-MM-DD"
                          :disabled-date="(d) => d < new Date(new Date().toDateString())"
                          style="width:150px" @change="loadAvailability" />
        </el-form-item>
        <el-form-item label="时段">
          <el-select v-model="booking.time_slot" style="width:170px" @change="loadAvailability">
            <el-option label="上午 09:00-12:00" value="morning" />
            <el-option label="下午 13:00-17:00" value="afternoon" />
            <el-option label="晚间 18:00-21:00" value="evening" />
          </el-select>
        </el-form-item>
      </el-form>

      <div class="zone-grid">
        <div v-for="z in availability" :key="z.id" class="zone-card"
             :class="{ active: booking.zone_id === z.id, disabled: !z.active }"
             @click="z.active && (booking.zone_id = z.id)">
          <div class="zone-name">{{ z.name }}</div>
          <div class="zone-cap">
            <el-progress type="circle" :width="56" :percentage="z.capacity ? Math.round(z.used / z.capacity * 100) : 0"
                         :status="z.remaining === 0 ? 'exception' : undefined" />
          </div>
          <div class="muted">剩余 {{ z.remaining }}/{{ z.capacity }}</div>
          <div class="muted">允许体型：{{ z.allowed_size_labels.join('、') }}</div>
          <el-tag v-if="z.requires_no_attack_history" type="warning" size="small">禁攻击史</el-tag>
          <el-tag v-if="z.code === 'activity'" type="success" size="small">活动报名</el-tag>
        </div>
      </div>
      <el-button type="primary" :disabled="!booking.zone_id || !booking.pet_id || !booking.visit_date"
                 :loading="submitting" @click="submitBooking">
        提交预约
      </el-button>
      <el-alert v-if="bookingResult" :type="bookingResult.ok ? 'success' : 'error'" :closable="false"
                style="margin-top:12px" :title="bookingResult.text" />
    </div>

    <!-- 预约列表 -->
    <div class="page-card">
      <div class="toolbar">
        <h3 class="page-title" style="margin:0;flex:1">{{ isOwner ? '我的预约' : '预约管理' }}</h3>
        <template v-if="!isOwner">
          <el-date-picker v-model="filterDate" type="date" value-format="YYYY-MM-DD" placeholder="按日期筛选"
                          style="width:160px" clearable @change="load" />
          <el-select v-model="filterStatus" placeholder="状态" clearable style="width:130px" @change="load">
            <el-option v-for="(l, v) in statusLabels" :key="v" :label="l" :value="v" />
          </el-select>
        </template>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </div>
      <el-table :data="reservations" v-loading="loading">
        <el-table-column prop="code" label="预约号" width="130" />
        <el-table-column prop="pet_name" label="宠物" width="90" />
        <el-table-column prop="pet_breed" label="品种" width="110" />
        <el-table-column v-if="!isOwner" prop="owner_name" label="主人" width="90" />
        <el-table-column v-if="!isOwner" prop="owner_phone" label="联系电话" width="120" />
        <el-table-column label="疫苗" width="80">
          <template #default="{ row }">
            <el-tag :type="row.vaccine_status === 'valid' ? 'success' : 'danger'" size="small">
              {{ row.vaccine_label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="牵引" width="80">
          <template #default="{ row }">{{ row.leash_required ? '需牵引' : '不强制' }}</template>
        </el-table-column>
        <el-table-column prop="zone_name" label="分区" width="100" />
        <el-table-column prop="visit_date" label="日期" width="110" />
        <el-table-column prop="time_slot_label" label="时段" width="140" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status_label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="result_reason" label="预约结果说明" min-width="220" show-overflow-tooltip />
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button v-if="['confirmed','waitlisted'].includes(row.status)" link type="danger"
                       @click="cancel(row)">取消</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'
import { useAuthStore } from '../store'

const auth = useAuthStore()
const isOwner = computed(() => auth.role === 'owner')

const pets = ref([])
const availability = ref([])
const reservations = ref([])
const loading = ref(false)
const submitting = ref(false)
const bookingResult = ref(null)
const filterDate = ref(null)
const filterStatus = ref('')

const statusLabels = {
  confirmed: '已确认', waitlisted: '候补', rejected: '已拒绝',
  cancelled: '已取消', completed: '已完成',
}

const today = new Date().toISOString().slice(0, 10)
const booking = reactive({ pet_id: null, zone_id: null, visit_date: today, time_slot: 'morning' })

function statusType(s) {
  return { confirmed: 'success', waitlisted: 'warning', rejected: 'danger', cancelled: 'info', completed: '' }[s]
}

async function loadPets() {
  if (isOwner.value) pets.value = await api.get('/pets')
}

async function loadAvailability() {
  if (!booking.visit_date || !booking.time_slot) return
  availability.value = await api.get('/zones/availability', {
    params: { visit_date: booking.visit_date, time_slot: booking.time_slot },
  })
}

async function load() {
  loading.value = true
  try {
    const params = {}
    if (filterDate.value) params.visit_date = filterDate.value
    if (filterStatus.value) params.status = filterStatus.value
    reservations.value = await api.get('/reservations', { params })
  } finally {
    loading.value = false
  }
}

async function submitBooking() {
  submitting.value = true
  bookingResult.value = null
  try {
    const res = await api.post('/reservations', booking)
    const r = res.reservation
    bookingResult.value = {
      ok: res.ok,
      text: `${r.status_label}：${r.result_reason}（预约号 ${r.code}）`,
    }
    if (res.ok) ElMessage.success('预约提交成功')
    load()
    loadAvailability()
  } finally {
    submitting.value = false
  }
}

async function cancel(row) {
  await ElMessageBox.confirm(`确认取消预约 ${row.code}？`, '提示', { type: 'warning' })
  await api.post(`/reservations/${row.id}/cancel`)
  ElMessage.success('已取消')
  load()
  loadAvailability()
}

onMounted(() => {
  loadPets()
  loadAvailability()
  load()
})
</script>

<style scoped>
.zone-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin: 8px 0 16px; }
.zone-card {
  border: 2px solid #e4e7ed; border-radius: 8px; padding: 14px; text-align: center;
  cursor: pointer; transition: all .15s; display: flex; flex-direction: column; gap: 6px; align-items: center;
}
.zone-card:hover { border-color: #409eff; }
.zone-card.active { border-color: #409eff; background: #ecf5ff; }
.zone-card.disabled { opacity: .5; cursor: not-allowed; }
.zone-name { font-weight: 600; }
</style>
