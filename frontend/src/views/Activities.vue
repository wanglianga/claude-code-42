<template>
  <div>
    <!-- 管理端：创建活动 -->
    <div v-if="isManager" class="page-card" style="margin-bottom:16px">
      <div class="toolbar">
        <h3 class="page-title" style="margin:0;flex:1">活动管理</h3>
        <el-button type="primary" :icon="Plus" @click="createVisible = true">创建活动</el-button>
      </div>
    </div>

    <!-- 主人：我的报名 -->
    <div v-if="isOwner" class="page-card" style="margin-bottom:16px">
      <h3 class="page-title">我的活动报名</h3>
      <el-table :data="myRegs" size="small">
        <el-table-column prop="activity_title" label="活动" min-width="160" />
        <el-table-column prop="pet_name" label="宠物" width="90" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="regStatusType(row.status)" size="small">{{ row.status_label }}</el-tag>
            <span v-if="row.status === 'waitlisted'" class="muted"> 第{{ row.queue_position }}位</span>
          </template>
        </el-table-column>
        <el-table-column prop="reject_reason" label="说明" min-width="140" show-overflow-tooltip />
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button v-if="['registered','waitlisted'].includes(row.status)" link type="danger"
                       @click="cancelReg(row)">取消</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!myRegs.length" description="暂无报名" :image-size="50" />
    </div>

    <!-- 活动卡片 -->
    <div class="act-grid">
      <div v-for="a in activities" :key="a.id" class="page-card act-card">
        <div class="toolbar" style="margin-bottom:8px">
          <b style="flex:1">{{ a.title }}</b>
          <el-tag size="small" :type="a.intensity === 'high' ? 'danger' : a.intensity === 'medium' ? 'warning' : 'success'">
            {{ a.intensity_label }}
          </el-tag>
        </div>
        <div class="muted">{{ a.activity_type_label }} · {{ a.activity_date }} {{ a.time_slot_label }}</div>
        <div class="muted">允许体型：{{ a.allowed_size_labels.join('、') }}</div>
        <el-progress :percentage="a.effective_capacity ? Math.round((a.registered_count + a.admitted_count) / a.effective_capacity * 100) : 0"
                     :status="(a.registered_count + a.admitted_count) >= a.effective_capacity ? 'exception' : undefined"
                     style="margin:10px 0 4px" />
        <div class="muted">
          有效容量 {{ a.effective_capacity }}（场地 {{ a.capacity }} / 教练 {{ a.coach_count }}×{{ a.pets_per_coach }}）·
          已报名 {{ a.registered_count + a.admitted_count }} · 候补 {{ a.waitlist_count }}
        </div>
        <div class="muted">教练：{{ a.coach_names.join('、') || '-' }} · 保险 {{ a.insurance_policy_no || '-' }}（已保 {{ a.insured_count }}）</div>
        <div style="margin-top:10px;display:flex;gap:8px">
          <el-button v-if="isOwner" type="primary" size="small" @click="openRegister(a)">报名</el-button>
          <el-button size="small" @click="openDetail(a)">
            {{ isCoach || isManager ? '检录台' : '详情' }}
          </el-button>
        </div>
      </div>
    </div>
    <el-empty v-if="!activities.length" description="暂无活动" />

    <!-- 创建活动 -->
    <el-dialog v-model="createVisible" title="创建活动" width="560px">
      <el-form :model="createForm" label-width="110px">
        <el-form-item label="活动名称" required><el-input v-model="createForm.title" /></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="createForm.activity_type" style="width:100%">
            <el-option label="飞盘" value="frisbee" /><el-option label="训练课" value="training_course" />
            <el-option label="社交活动" value="social_event" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期" required>
          <el-date-picker v-model="createForm.activity_date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
        </el-form-item>
        <el-form-item label="时段">
          <el-select v-model="createForm.time_slot" style="width:100%">
            <el-option label="上午 09:00-12:00" value="morning" />
            <el-option label="下午 13:00-17:00" value="afternoon" />
            <el-option label="晚间 18:00-21:00" value="evening" />
          </el-select>
        </el-form-item>
        <el-form-item label="活动强度">
          <el-select v-model="createForm.intensity" style="width:100%">
            <el-option label="低强度" value="low" /><el-option label="中强度" value="medium" />
            <el-option label="高强度" value="high" />
          </el-select>
        </el-form-item>
        <el-form-item label="允许体型">
          <el-checkbox-group v-model="createForm.allowed_sizes">
            <el-checkbox value="small">小型</el-checkbox><el-checkbox value="medium">中型</el-checkbox>
            <el-checkbox value="large">大型</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="场地容量"><el-input-number v-model="createForm.capacity" :min="1" :max="200" /></el-form-item>
        <el-form-item label="教练数量"><el-input-number v-model="createForm.coach_count" :min="1" :max="20" /></el-form-item>
        <el-form-item label="每教练可带">
          <el-input-number v-model="createForm.pets_per_coach" :min="1" :max="50" />
          <div class="muted">有效容量 = min(场地容量, 教练数量 × 每教练可带)</div>
        </el-form-item>
        <el-form-item label="教练名单"><el-input v-model="createForm.coach_names" placeholder="逗号分隔，如：刘教练,王助教" /></el-form-item>
        <el-form-item label="保险单号"><el-input v-model="createForm.insurance_policy_no" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="createActivity">创建</el-button>
      </template>
    </el-dialog>

    <!-- 主人报名 -->
    <el-dialog v-model="registerVisible" :title="`报名：${current?.title || ''}`" width="420px">
      <el-select v-model="registerPetId" placeholder="选择宠物" style="width:100%">
        <el-option v-for="p in myPets" :key="p.id" :label="`${p.name}（${p.breed}·${p.size_label}）`" :value="p.id" />
      </el-select>
      <el-alert type="info" :closable="false" style="margin-top:10px"
                title="平台将按体型、活动强度、疫苗、黑名单与活动资格限制校验；满员自动进入候补队列" />
      <template #footer>
        <el-button @click="registerVisible = false">取消</el-button>
        <el-button type="primary" :loading="registering" @click="doRegister">提交报名</el-button>
      </template>
    </el-dialog>

    <!-- 详情/检录台抽屉 -->
    <el-drawer v-model="detailVisible" :title="`${current?.title || ''} · 检录台`" size="660px">
      <template v-if="current">
        <el-descriptions :column="2" border size="small" style="margin-bottom:12px">
          <el-descriptions-item label="日期时段">{{ current.activity_date }} {{ current.time_slot_label }}</el-descriptions-item>
          <el-descriptions-item label="有效容量">{{ current.effective_capacity }}（场地 {{ current.capacity }} / 教练 {{ current.coach_count }}×{{ current.pets_per_coach }}）</el-descriptions-item>
          <el-descriptions-item label="保险单号">{{ current.insurance_policy_no || '-' }}</el-descriptions-item>
          <el-descriptions-item label="已投保">{{ current.insured_count }} 只：{{ current.insured_pets || '-' }}</el-descriptions-item>
        </el-descriptions>

        <el-alert v-if="!isToday" type="info" :closable="false" style="margin-bottom:10px"
                  title="非活动当天，仅可查看；检录（入场/拒绝）需活动当天操作" />

        <el-tabs>
          <el-tab-pane v-for="grp in rosterGroups" :key="grp.key" :label="`${grp.label}(${grp.rows.length})`">
            <el-table :data="grp.rows" size="small">
              <el-table-column label="宠物" min-width="130">
                <template #default="{ row }">{{ row.pet_name }}（{{ row.breed }}·{{ row.size_label }}）</template>
              </el-table-column>
              <el-table-column label="主人/电话" width="150">
                <template #default="{ row }">{{ row.owner_name }} {{ row.owner_phone }}</template>
              </el-table-column>
              <el-table-column v-if="grp.key === 'waitlisted'" label="排队" width="80">
                <template #default="{ row }">第{{ row.queue_position }}位</template>
              </el-table-column>
              <el-table-column v-if="grp.key === 'rejected'" prop="reject_reason" label="原因" min-width="120" />
              <el-table-column v-if="canCheckin && ['registered','waitlisted'].includes(grp.key)" label="检录" width="140">
                <template #default="{ row }">
                  <el-button size="small" type="success" @click="checkin(row, 'admit')">入场</el-button>
                  <el-button size="small" type="danger" @click="checkin(row, 'reject')">拒绝</el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-if="!grp.rows.length" description="暂无" :image-size="50" />
          </el-tab-pane>

          <el-tab-pane v-if="isCoach || isManager" label="现场登记">
            <el-alert type="warning" :closable="false" style="margin-bottom:10px"
                      title="临时报到：满员时自动进入候补队列；候补被拒绝后，名额保留给下一位排队用户" />
            <el-select v-model="walkinPetId" filterable placeholder="选择到场宠物" style="width:260px">
              <el-option v-for="p in allPets" :key="p.id" :label="`${p.name}（${p.breed}·${p.owner_name}）`" :value="p.id" />
            </el-select>
            <el-button type="primary" size="small" style="margin-left:8px" :disabled="!walkinPetId || !isToday" @click="walkin">
              登记报到
            </el-button>
          </el-tab-pane>

          <el-tab-pane label="保险与教练分组">
            <h5 style="margin:4px 0">活动保险（{{ current.insurance_policy_no || '-' }}）</h5>
            <p class="muted">已投保 {{ current.insured_count }} 只：{{ current.insured_pets || '-' }}</p>
            <h5 style="margin:12px 0 4px">教练分组</h5>
            <el-tag v-for="(pets, coach) in current.coach_assignments" :key="coach" style="margin:0 8px 8px 0">
              {{ coach }}：{{ (pets || []).join('、') || '（暂无）' }}
            </el-tag>
            <el-empty v-if="!Object.keys(current.coach_assignments || {}).length" description="入场后自动分组" :image-size="50" />
          </el-tab-pane>
        </el-tabs>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'
import { useAuthStore } from '../store'

const auth = useAuthStore()
const isOwner = computed(() => auth.role === 'owner')
const isCoach = computed(() => auth.role === 'coach')
const isManager = computed(() => ['manager', 'admin'].includes(auth.role))

const activities = ref([])
const myRegs = ref([])
const myPets = ref([])
const allPets = ref([])
const current = ref(null)
const detailVisible = ref(false)
const createVisible = ref(false)
const registerVisible = ref(false)
const registerPetId = ref(null)
const walkinPetId = ref(null)
const creating = ref(false)
const registering = ref(false)

const createForm = reactive({
  title: '', activity_type: 'frisbee', activity_date: '', time_slot: 'evening',
  intensity: 'high', allowed_sizes: ['medium', 'large'], capacity: 10,
  coach_count: 2, pets_per_coach: 5, coach_names: '', insurance_policy_no: '',
})

const today = new Date().toISOString().slice(0, 10)
const isToday = computed(() => current.value?.activity_date === today)
const canCheckin = computed(() => (isCoach.value || isManager.value) && isToday.value)

const rosterGroups = computed(() => {
  const regs = current.value?.registrations || []
  return [
    { key: 'registered', label: '已报名', rows: regs.filter((r) => r.status === 'registered') },
    { key: 'waitlisted', label: '候补', rows: regs.filter((r) => r.status === 'waitlisted').sort((a, b) => a.queue_position - b.queue_position) },
    { key: 'admitted', label: '已入场', rows: regs.filter((r) => r.status === 'admitted') },
    { key: 'rejected', label: '已拒绝', rows: regs.filter((r) => r.status === 'rejected') },
  ]
})

function regStatusType(s) {
  return { registered: 'primary', waitlisted: 'warning', admitted: 'success', rejected: 'danger', cancelled: 'info' }[s]
}

async function load() {
  activities.value = await api.get('/activities')
  if (isOwner.value) {
    myPets.value = await api.get('/pets')
    const mine = []
    for (const a of activities.value) {
      const d = await api.get(`/activities/${a.id}`)
      for (const r of d.my_registrations || []) mine.push({ ...r, activity_title: a.title })
    }
    myRegs.value = mine
  }
}

async function openDetail(a) {
  current.value = await api.get(`/activities/${a.id}`)
  if ((isCoach.value || isManager.value) && !allPets.value.length) {
    allPets.value = await api.get('/pets')
  }
  detailVisible.value = true
}

async function refreshCurrent() {
  current.value = await api.get(`/activities/${current.value.id}`)
  load()
}

async function createActivity() {
  if (!createForm.title || !createForm.activity_date) {
    ElMessage.warning('请填写活动名称与日期')
    return
  }
  creating.value = true
  try {
    await api.post('/activities', createForm)
    ElMessage.success('活动已创建')
    createVisible.value = false
    load()
  } finally {
    creating.value = false
  }
}

function openRegister(a) {
  current.value = a
  registerPetId.value = null
  registerVisible.value = true
}

async function doRegister() {
  if (!registerPetId.value) {
    ElMessage.warning('请选择宠物')
    return
  }
  registering.value = true
  try {
    const reg = await api.post(`/activities/${current.value.id}/register`, { pet_id: registerPetId.value })
    ElMessage.success(reg.status === 'waitlisted' ? `已满员，进入候补第 ${reg.queue_position} 位` : '报名成功')
    registerVisible.value = false
    load()
  } finally {
    registering.value = false
  }
}

async function cancelReg(row) {
  await ElMessageBox.confirm('确认取消该报名？', '提示', { type: 'warning' })
  await api.post(`/activities/registrations/${row.id}/cancel`)
  ElMessage.success('已取消')
  load()
}

async function checkin(row, decision) {
  let reason = ''
  if (decision === 'reject') {
    const { value } = await ElMessageBox.prompt('请输入拒绝原因', '拒绝入场', {
      inputValue: '现场状态不适合入场', inputValidator: (v) => !!v || '请填写原因',
    })
    reason = value
  }
  await api.post(`/activities/${current.value.id}/checkin`, {
    registration_id: row.id, decision, reason,
  })
  ElMessage.success(decision === 'admit' ? `已放行：${row.pet_name}（保险与教练分组已同步）` : '已拒绝，名额保留给下一位排队用户')
  refreshCurrent()
}

async function walkin() {
  const reg = await api.post(`/activities/${current.value.id}/walkin`, { pet_id: walkinPetId.value })
  ElMessage.success(reg.status === 'waitlisted' ? `已登记，候补第 ${reg.queue_position} 位` : '已登记为已报名')
  walkinPetId.value = null
  refreshCurrent()
}

onMounted(load)
</script>

<style scoped>
.act-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
.act-card { display: flex; flex-direction: column; }
</style>
