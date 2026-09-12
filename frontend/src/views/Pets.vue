<template>
  <div class="page-card">
    <div class="toolbar">
      <h3 class="page-title" style="margin:0;flex:1">我的宠物档案</h3>
      <el-button type="primary" :icon="Plus" @click="openForm()">新增宠物</el-button>
    </div>

    <el-table :data="pets" v-loading="loading">
      <el-table-column prop="name" label="名字" width="100" />
      <el-table-column prop="breed" label="品种" width="130" />
      <el-table-column label="体重/体型" width="120">
        <template #default="{ row }">{{ row.weight_kg }}kg（{{ row.size_label }}）</template>
      </el-table-column>
      <el-table-column label="疫苗" width="150">
        <template #default="{ row }">
          <el-tag :type="row.vaccine_status === 'valid' ? 'success' : 'danger'" size="small">
            {{ row.vaccine_label }}
          </el-tag>
          <span class="muted" style="margin-left:4px">{{ row.vaccine_expiry || '' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="绝育" width="70">
        <template #default="{ row }">{{ row.sterilized ? '是' : '否' }}</template>
      </el-table-column>
      <el-table-column label="攻击史" width="80">
        <template #default="{ row }">
          <el-tag v-if="row.attack_history" type="danger" size="small">有</el-tag>
          <span v-else>无</span>
        </template>
      </el-table-column>
      <el-table-column prop="dog_license_no" label="犬证号" width="130" />
      <el-table-column label="风险标记" min-width="140">
        <template #default="{ row }">
          <el-tag v-if="row.active_blacklist" type="danger" size="small" style="margin-right:4px">
            黑名单 {{ row.active_blacklist }}
          </el-tag>
          <el-tag v-if="row.active_restrictions" type="warning" size="small">
            限制 {{ row.active_restrictions }}
          </el-tag>
          <span v-if="!row.active_blacklist && !row.active_restrictions" class="muted">无</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openProfile(row)">档案</el-button>
          <el-button link type="primary" @click="openForm(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新增/编辑 -->
    <el-dialog v-model="formVisible" :title="form.id ? '编辑宠物' : '新增宠物'" width="640px">
      <el-form :model="form" label-width="100px">
        <el-row :gutter="12">
          <el-col :span="12"><el-form-item label="名字" required><el-input v-model="form.name" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="品种" required><el-input v-model="form.breed" /></el-form-item></el-col>
          <el-col :span="12">
            <el-form-item label="体重(kg)" required>
              <el-input-number v-model="form.weight_kg" :min="0.5" :max="100" :step="0.5" style="width:100%" />
              <div class="muted">体型自动判定：&lt;10kg 小型，10-25kg 中型，&gt;25kg 大型</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="疫苗状态">
              <el-select v-model="form.vaccine_status" style="width:100%">
                <el-option label="有效" value="valid" />
                <el-option label="已过期" value="expired" />
                <el-option label="缺失" value="missing" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="疫苗有效期">
              <el-date-picker v-model="form.vaccine_expiry" type="date" value-format="YYYY-MM-DD" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12"><el-form-item label="狂犬疫苗号"><el-input v-model="form.rabies_vaccine_no" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="犬证号"><el-input v-model="form.dog_license_no" /></el-form-item></el-col>
          <el-col :span="12">
            <el-form-item label="犬证有效期">
              <el-date-picker v-model="form.license_expiry" type="date" value-format="YYYY-MM-DD" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8"><el-form-item label="已绝育"><el-switch v-model="form.sterilized" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="需牵引"><el-switch v-model="form.leash_required" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="有攻击史"><el-switch v-model="form.attack_history" /></el-form-item></el-col>
          <el-col :span="24" v-if="form.attack_history">
            <el-form-item label="攻击史说明"><el-input v-model="form.attack_history_desc" type="textarea" :rows="2" /></el-form-item>
          </el-col>
          <el-col :span="24"><el-form-item label="备注"><el-input v-model="form.notes" type="textarea" :rows="2" /></el-form-item></el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <!-- 宠物档案抽屉 -->
    <el-drawer v-model="profileVisible" :title="`宠物档案：${profile.pet?.name || ''}`" size="620px">
      <template v-if="profile.pet">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="品种">{{ profile.pet.breed }}</el-descriptions-item>
          <el-descriptions-item label="体型">{{ profile.pet.weight_kg }}kg（{{ profile.pet.size_label }}）</el-descriptions-item>
          <el-descriptions-item label="疫苗">
            <el-tag :type="profile.pet.vaccine_status === 'valid' ? 'success' : 'danger'" size="small">
              {{ profile.pet.vaccine_label }}
            </el-tag>
            {{ profile.pet.vaccine_expiry }}
          </el-descriptions-item>
          <el-descriptions-item label="狂犬疫苗号">{{ profile.pet.rabies_vaccine_no || '-' }}</el-descriptions-item>
          <el-descriptions-item label="绝育">{{ profile.pet.sterilized ? '是' : '否' }}</el-descriptions-item>
          <el-descriptions-item label="攻击史">{{ profile.pet.attack_history ? profile.pet.attack_history_desc || '有' : '无' }}</el-descriptions-item>
          <el-descriptions-item label="犬证">{{ profile.pet.dog_license_no || '-' }}</el-descriptions-item>
          <el-descriptions-item label="犬证有效期">{{ profile.pet.license_expiry || '-' }}</el-descriptions-item>
        </el-descriptions>

        <el-tabs style="margin-top:16px">
          <el-tab-pane :label="`黑名单(${profile.blacklist.length})`">
            <el-table :data="profile.blacklist" size="small">
              <el-table-column prop="level_label" label="级别" width="90" />
              <el-table-column prop="reason" label="原因" min-width="180" show-overflow-tooltip />
              <el-table-column label="状态" width="80">
                <template #default="{ row }">
                  <el-tag :type="row.active ? 'danger' : 'info'" size="small">{{ row.active ? '生效中' : '已解除' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="created_at" label="时间" width="140" />
            </el-table>
            <el-empty v-if="!profile.blacklist.length" description="无" :image-size="50" />
          </el-tab-pane>
          <el-tab-pane :label="`活动资格限制(${profile.restrictions.length})`">
            <el-table :data="profile.restrictions" size="small">
              <el-table-column prop="restriction_label" label="限制" width="150" />
              <el-table-column prop="reason" label="原因" min-width="160" show-overflow-tooltip />
              <el-table-column label="状态" width="80">
                <template #default="{ row }">
                  <el-tag :type="row.active ? 'warning' : 'info'" size="small">{{ row.active ? '生效中' : '已解除' }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-if="!profile.restrictions.length" description="无" :image-size="50" />
          </el-tab-pane>
          <el-tab-pane :label="`巡场记录(${profile.incidents.length})`">
            <el-table :data="profile.incidents" size="small">
              <el-table-column prop="incident_type_label" label="行为" width="90" />
              <el-table-column prop="zone_name" label="分区" width="90" />
              <el-table-column prop="severity_label" label="严重度" width="80" />
              <el-table-column prop="occurred_at" label="时间" width="140" />
            </el-table>
            <el-empty v-if="!profile.incidents.length" description="无" :image-size="50" />
          </el-tab-pane>
          <el-tab-pane :label="`医疗记录(${profile.medical_records.length})`">
            <el-table :data="profile.medical_records" size="small">
              <el-table-column prop="injury_desc" label="伤情" min-width="140" show-overflow-tooltip />
              <el-table-column prop="treatment" label="处置" min-width="140" show-overflow-tooltip />
              <el-table-column prop="cost" label="费用" width="80" />
              <el-table-column prop="treated_at" label="时间" width="140" />
            </el-table>
            <el-empty v-if="!profile.medical_records.length" description="无" :image-size="50" />
          </el-tab-pane>
          <el-tab-pane :label="`相关事件(${profile.events.length})`">
            <el-table :data="profile.events" size="small">
              <el-table-column prop="code" label="编号" width="110" />
              <el-table-column prop="title" label="事件" min-width="160" show-overflow-tooltip />
              <el-table-column prop="status_label" label="状态" width="80" />
            </el-table>
            <el-empty v-if="!profile.events.length" description="无" :image-size="50" />
          </el-tab-pane>
        </el-tabs>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const pets = ref([])
const loading = ref(false)
const saving = ref(false)
const formVisible = ref(false)
const profileVisible = ref(false)
const profile = ref({})

const emptyForm = {
  id: null, name: '', breed: '', weight_kg: 10, vaccine_status: 'valid',
  vaccine_expiry: null, rabies_vaccine_no: '', sterilized: false,
  attack_history: false, attack_history_desc: '', leash_required: true,
  dog_license_no: '', license_expiry: null, notes: '',
}
const form = reactive({ ...emptyForm })

async function load() {
  loading.value = true
  try {
    pets.value = await api.get('/pets')
  } finally {
    loading.value = false
  }
}

function openForm(row) {
  Object.assign(form, emptyForm, row ? {
    id: row.id, name: row.name, breed: row.breed, weight_kg: row.weight_kg,
    vaccine_status: row.vaccine_status, vaccine_expiry: row.vaccine_expiry,
    rabies_vaccine_no: row.rabies_vaccine_no, sterilized: row.sterilized,
    attack_history: row.attack_history, attack_history_desc: row.attack_history_desc,
    leash_required: row.leash_required, dog_license_no: row.dog_license_no,
    license_expiry: row.license_expiry, notes: row.notes,
  } : {})
  formVisible.value = true
}

async function save() {
  if (!form.name || !form.breed) {
    ElMessage.warning('请填写名字和品种')
    return
  }
  saving.value = true
  try {
    const payload = { ...form }
    delete payload.id
    if (form.id) await api.put(`/pets/${form.id}`, payload)
    else await api.post('/pets', payload)
    ElMessage.success('已保存')
    formVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function openProfile(row) {
  profile.value = await api.get(`/pets/${row.id}`)
  profileVisible.value = true
}

onMounted(load)
</script>
