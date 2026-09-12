<template>
  <div v-loading="loading">
    <template v-if="detail.event">
      <div class="page-card" style="margin-bottom:16px">
        <div class="toolbar">
          <h3 class="page-title" style="margin:0;flex:1">
            {{ detail.event.title }}
            <el-tag size="small" style="margin-left:8px">{{ detail.event.code }}</el-tag>
          </h3>
          <el-tag :type="statusType(detail.event.status)">{{ detail.event.status_label }}</el-tag>
          <el-button v-if="isManager && detail.event.status === 'open'" type="warning" @click="startProcess">
            开始处理
          </el-button>
          <el-button v-if="isManager && detail.event.status !== 'closed'" type="success" @click="closeVisible = true">
            关闭事件
          </el-button>
        </div>
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="事件类型">{{ detail.event.event_type_label }}</el-descriptions-item>
          <el-descriptions-item label="优先级">{{ detail.event.priority_label }}</el-descriptions-item>
          <el-descriptions-item label="所在分区">{{ detail.event.zone_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="涉事宠物">{{ detail.event.pet_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="宠物主人">{{ detail.event.owner_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建人">{{ detail.event.creator_name }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ detail.event.created_at }}</el-descriptions-item>
          <el-descriptions-item label="关闭时间">{{ detail.event.closed_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="描述" :span="1">{{ detail.event.description || '-' }}</el-descriptions-item>
        </el-descriptions>
        <el-alert v-if="detail.event.resolution_summary" type="success" :closable="false" style="margin-top:12px"
                  :title="`处置结论：${detail.event.resolution_summary}`" />
        <div style="margin-top:12px">
          <span class="muted" style="margin-right:8px">协同方：</span>
          <el-tag v-for="p in detail.participants" :key="p.id" size="small" style="margin-right:6px" effect="plain">
            {{ p.user?.name }}（{{ p.user?.role_label }}）
          </el-tag>
        </div>
      </div>

      <el-row :gutter="16">
        <el-col :span="10">
          <div class="page-card">
            <h4 class="page-title">处置时间线</h4>
            <el-timeline style="max-height:520px;overflow-y:auto;padding-left:4px">
              <el-timeline-item v-for="u in detail.updates" :key="u.id" :timestamp="`${u.created_at} ${u.actor?.name}（${u.actor?.role_label}）`" placement="top">
                <b>{{ u.action }}</b>
                <div class="muted" style="white-space:pre-wrap">{{ u.content }}</div>
              </el-timeline-item>
            </el-timeline>
            <template v-if="detail.event.status !== 'closed'">
              <el-divider />
              <el-input v-model="updateForm.action" placeholder="动作（如：现场取证）" size="small" style="margin-bottom:8px" />
              <el-input v-model="updateForm.content" type="textarea" :rows="2" placeholder="进展说明" size="small" />
              <el-button type="primary" size="small" style="margin-top:8px" @click="postUpdate">发布进展</el-button>
            </template>
          </div>
        </el-col>

        <el-col :span="14">
          <div class="page-card">
            <el-tabs>
              <el-tab-pane :label="`医疗处置(${detail.medical_records.length})`">
                <el-table :data="detail.medical_records" size="small">
                  <el-table-column prop="patient_name" label="伤者" width="90" />
                  <el-table-column prop="injury_desc" label="伤情" min-width="140" show-overflow-tooltip />
                  <el-table-column prop="treatment" label="处置" min-width="140" show-overflow-tooltip />
                  <el-table-column prop="cost" label="费用(元)" width="90" />
                  <el-table-column prop="hospital" label="登记方" width="130" />
                </el-table>
                <el-empty v-if="!detail.medical_records.length" description="暂无" :image-size="50" />
                <template v-if="canMedical && detail.event.status !== 'closed'">
                  <el-divider>合作医院登记伤情</el-divider>
                  <el-form inline>
                    <el-form-item><el-input v-model="medicalForm.patient_name" placeholder="伤者名称" style="width:110px" /></el-form-item>
                    <el-form-item><el-input v-model="medicalForm.injury_desc" placeholder="伤情" style="width:160px" /></el-form-item>
                    <el-form-item><el-input v-model="medicalForm.treatment" placeholder="处置措施" style="width:160px" /></el-form-item>
                    <el-form-item><el-input-number v-model="medicalForm.cost" :min="0" placeholder="费用" style="width:110px" /></el-form-item>
                    <el-button type="primary" size="small" @click="addMedical">登记</el-button>
                  </el-form>
                </template>
              </el-tab-pane>

              <el-tab-pane :label="`赔付(${detail.compensations.length})`">
                <el-table :data="detail.compensations" size="small">
                  <el-table-column prop="payer_name" label="赔付方" width="90" />
                  <el-table-column prop="payee_name" label="收款方" width="90" />
                  <el-table-column prop="amount" label="金额(元)" width="90" />
                  <el-table-column prop="reason" label="事由" min-width="140" show-overflow-tooltip />
                  <el-table-column label="状态" width="110">
                    <template #default="{ row }">
                      <el-tag :type="{ pending: 'warning', paid: 'success', rejected: 'info' }[row.status]" size="small">
                        {{ row.status_label }}
                      </el-tag>
                      <el-button v-if="canCompensate && row.status === 'pending'" link type="success" size="small"
                                 @click="setCompensation(row, 'paid')">核销</el-button>
                    </template>
                  </el-table-column>
                </el-table>
                <el-empty v-if="!detail.compensations.length" description="暂无" :image-size="50" />
                <template v-if="canCompensate && detail.event.status !== 'closed'">
                  <el-divider>客服登记赔付</el-divider>
                  <el-form inline>
                    <el-form-item>
                      <el-select v-model="compForm.payer_owner_id" placeholder="赔付方(主人)" style="width:130px">
                        <el-option v-for="o in ownerParticipants" :key="o.user.id" :label="o.user.name" :value="o.user.id" />
                      </el-select>
                    </el-form-item>
                    <el-form-item><el-input v-model="compForm.payee_name" placeholder="收款方" style="width:110px" /></el-form-item>
                    <el-form-item><el-input-number v-model="compForm.amount" :min="0" placeholder="金额" style="width:110px" /></el-form-item>
                    <el-form-item><el-input v-model="compForm.reason" placeholder="事由" style="width:150px" /></el-form-item>
                    <el-button type="primary" size="small" @click="addCompensation">登记</el-button>
                  </el-form>
                </template>
              </el-tab-pane>

              <el-tab-pane :label="`黑名单与资格(${detail.blacklist.length + detail.restrictions.length})`">
                <h5 style="margin:4px 0">黑名单</h5>
                <el-table :data="detail.blacklist" size="small">
                  <el-table-column prop="pet_name" label="宠物" width="80" />
                  <el-table-column prop="level_label" label="级别" width="90" />
                  <el-table-column prop="reason" label="原因" min-width="150" show-overflow-tooltip />
                  <el-table-column label="状态" width="80">
                    <template #default="{ row }">
                      <el-tag :type="row.active ? 'danger' : 'info'" size="small">{{ row.active ? '生效' : '解除' }}</el-tag>
                    </template>
                  </el-table-column>
                </el-table>
                <h5 style="margin:12px 0 4px">活动资格限制</h5>
                <el-table :data="detail.restrictions" size="small">
                  <el-table-column prop="pet_name" label="宠物" width="80" />
                  <el-table-column prop="restriction_label" label="限制" width="150" />
                  <el-table-column prop="reason" label="原因" min-width="150" show-overflow-tooltip />
                </el-table>
                <template v-if="isManager && detail.event.status !== 'closed'">
                  <el-divider>园区管理处置</el-divider>
                  <el-form inline>
                    <el-form-item>
                      <el-select v-model="blForm.level" style="width:120px">
                        <el-option label="警告" value="warning" /><el-option label="限制入园" value="restricted" />
                        <el-option label="永久拉黑" value="banned" />
                      </el-select>
                    </el-form-item>
                    <el-form-item><el-input v-model="blForm.reason" placeholder="原因" style="width:180px" /></el-form-item>
                    <el-button type="danger" size="small" @click="addBlacklist">对涉事宠物加黑名单</el-button>
                  </el-form>
                  <el-form inline>
                    <el-form-item>
                      <el-select v-model="restrForm.restriction_type" style="width:180px">
                        <el-option label="仅限牵引区域" value="leash_only" />
                        <el-option label="需佩戴嘴套" value="muzzle_required" />
                        <el-option label="禁止进入活动区" value="no_activity_zone" />
                        <el-option label="禁止进入社交区" value="no_social_zone" />
                        <el-option label="暂停一切入园活动资格" value="activity_ban" />
                      </el-select>
                    </el-form-item>
                    <el-form-item><el-input v-model="restrForm.reason" placeholder="原因" style="width:180px" /></el-form-item>
                    <el-button type="warning" size="small" @click="addRestriction">对涉事宠物加限制</el-button>
                  </el-form>
                </template>
              </el-tab-pane>

              <el-tab-pane :label="`设施整改(${detail.rectifications.length})`">
                <el-table :data="detail.rectifications" size="small">
                  <el-table-column prop="zone_name" label="分区" width="90" />
                  <el-table-column prop="issue" label="问题" min-width="150" show-overflow-tooltip />
                  <el-table-column prop="action" label="整改措施" min-width="150" show-overflow-tooltip />
                  <el-table-column label="状态" width="130">
                    <template #default="{ row }">
                      <el-tag :type="{ pending: 'danger', in_progress: 'warning', done: 'success' }[row.status]" size="small">
                        {{ row.status_label }}
                      </el-tag>
                      <el-button v-if="isManager && row.status !== 'done' && detail.event.status !== 'closed'"
                                 link type="primary" size="small"
                                 @click="advanceRectification(row)">推进</el-button>
                    </template>
                  </el-table-column>
                </el-table>
                <el-empty v-if="!detail.rectifications.length" description="暂无" :image-size="50" />
                <template v-if="isManager && detail.event.status !== 'closed'">
                  <el-divider>登记设施整改</el-divider>
                  <el-form inline>
                    <el-form-item>
                      <el-select v-model="rectForm.zone_id" placeholder="分区" style="width:120px">
                        <el-option v-for="z in zones" :key="z.id" :label="z.name" :value="z.id" />
                      </el-select>
                    </el-form-item>
                    <el-form-item><el-input v-model="rectForm.issue" placeholder="设施问题" style="width:180px" /></el-form-item>
                    <el-form-item><el-input v-model="rectForm.action" placeholder="整改措施" style="width:180px" /></el-form-item>
                    <el-button type="primary" size="small" @click="addRectification">登记</el-button>
                  </el-form>
                </template>
              </el-tab-pane>

              <el-tab-pane :label="`巡场记录(${detail.incidents.length})`">
                <el-table :data="detail.incidents" size="small">
                  <el-table-column prop="code" label="编号" width="110" />
                  <el-table-column prop="incident_type_label" label="行为" width="90" />
                  <el-table-column prop="severity_label" label="严重度" width="80" />
                  <el-table-column prop="description" label="描述" min-width="160" show-overflow-tooltip />
                </el-table>
                <el-empty v-if="!detail.incidents.length" description="暂无" :image-size="50" />
              </el-tab-pane>
            </el-tabs>
          </div>
        </el-col>
      </el-row>
    </template>

    <el-dialog v-model="closeVisible" title="关闭事件" width="520px">
      <el-alert type="warning" :closable="false" style="margin-bottom:12px"
                title="关闭后，伤情、赔付、黑名单、活动资格与设施整改将归档进宠物档案与园区运营记录" />
      <el-input v-model="closeSummary" type="textarea" :rows="4" placeholder="处置结论（必填）" />
      <template #footer>
        <el-button @click="closeVisible = false">取消</el-button>
        <el-button type="success" @click="closeEvent">确认关闭并归档</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api'
import { useAuthStore } from '../store'

const route = useRoute()
const auth = useAuthStore()
const eventId = route.params.id

const detail = ref({})
const zones = ref([])
const loading = ref(false)
const closeVisible = ref(false)
const closeSummary = ref('')

const updateForm = reactive({ action: '', content: '' })
const medicalForm = reactive({ patient_name: '', injury_desc: '', treatment: '', cost: 0 })
const compForm = reactive({ payer_owner_id: null, payee_name: '', amount: 0, reason: '' })
const blForm = reactive({ level: 'warning', reason: '' })
const restrForm = reactive({ restriction_type: 'muzzle_required', reason: '' })
const rectForm = reactive({ zone_id: null, issue: '', action: '' })

const isManager = computed(() => ['manager', 'admin'].includes(auth.role))
const canMedical = computed(() => ['hospital', 'manager', 'admin'].includes(auth.role))
const canCompensate = computed(() => ['service', 'manager', 'admin'].includes(auth.role))
const ownerParticipants = computed(() =>
  (detail.value.participants || []).filter((p) => p.user?.role === 'owner'))

function statusType(s) {
  return { open: 'danger', processing: 'warning', closed: 'success' }[s]
}

async function load() {
  loading.value = true
  try {
    detail.value = await api.get(`/events/${eventId}`)
  } finally {
    loading.value = false
  }
}

async function postUpdate() {
  if (!updateForm.action) {
    ElMessage.warning('请填写动作')
    return
  }
  await api.post(`/events/${eventId}/updates`, updateForm)
  updateForm.action = ''
  updateForm.content = ''
  load()
}

async function startProcess() {
  await api.post(`/events/${eventId}/status`)
  load()
}

async function addMedical() {
  if (!medicalForm.patient_name || !medicalForm.injury_desc) {
    ElMessage.warning('请填写伤者与伤情')
    return
  }
  await api.post(`/events/${eventId}/medical`, {
    ...medicalForm, pet_id: detail.value.event.pet_id, patient_type: 'pet',
  })
  Object.assign(medicalForm, { patient_name: '', injury_desc: '', treatment: '', cost: 0 })
  ElMessage.success('医疗处置已登记')
  load()
}

async function addCompensation() {
  if (!compForm.payee_name || !compForm.amount) {
    ElMessage.warning('请填写收款方与金额')
    return
  }
  await api.post(`/events/${eventId}/compensations`, compForm)
  Object.assign(compForm, { payer_owner_id: null, payee_name: '', amount: 0, reason: '' })
  ElMessage.success('赔付已登记')
  load()
}

async function setCompensation(row, status) {
  await api.put(`/events/compensations/${row.id}`, { status })
  ElMessage.success('赔付状态已更新')
  load()
}

async function addBlacklist() {
  if (!detail.value.event.pet_id) {
    ElMessage.warning('该事件无涉事宠物')
    return
  }
  await api.post(`/events/${eventId}/blacklist`, {
    pet_id: detail.value.event.pet_id, ...blForm,
  })
  blForm.reason = ''
  ElMessage.success('黑名单已生效，将影响后续预约与活动报名')
  load()
}

async function addRestriction() {
  if (!detail.value.event.pet_id) {
    ElMessage.warning('该事件无涉事宠物')
    return
  }
  await api.post(`/events/${eventId}/restrictions`, {
    pet_id: detail.value.event.pet_id, ...restrForm,
  })
  restrForm.reason = ''
  ElMessage.success('活动资格限制已生效')
  load()
}

async function addRectification() {
  if (!rectForm.issue) {
    ElMessage.warning('请填写设施问题')
    return
  }
  await api.post(`/events/${eventId}/rectifications`, rectForm)
  Object.assign(rectForm, { zone_id: null, issue: '', action: '' })
  ElMessage.success('整改已登记')
  load()
}

async function advanceRectification(row) {
  const next = row.status === 'pending' ? 'in_progress' : 'done'
  await api.put(`/events/rectifications/${row.id}`, { status: next })
  load()
}

async function closeEvent() {
  if (!closeSummary.value.trim()) {
    ElMessage.warning('请填写处置结论')
    return
  }
  await api.post(`/events/${eventId}/close`, { resolution_summary: closeSummary.value })
  closeVisible.value = false
  ElMessage.success('事件已关闭并归档')
  load()
}

onMounted(async () => {
  load()
  if (isManager.value) zones.value = await api.get('/zones')
})
</script>
