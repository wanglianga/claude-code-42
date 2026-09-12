<template>
  <div class="page-card">
    <div class="toolbar">
      <h3 class="page-title" style="margin:0;flex:1">入园核验工作台</h3>
      <el-date-picker v-model="date" type="date" value-format="YYYY-MM-DD" style="width:160px"
                      :clearable="false" @change="load" />
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>
    <el-alert type="info" :closable="false" style="margin-bottom:12px"
              title="核验四项：疫苗有效、犬证有效、牵引绳合规、主人身份一致。任一不通过则禁止进入自由活动区；疫苗问题可一键升级为协同事件。" />

    <el-table :data="board" v-loading="loading">
      <el-table-column prop="code" label="预约号" width="130" />
      <el-table-column prop="pet_name" label="宠物" width="90" />
      <el-table-column prop="owner_name" label="主人" width="90" />
      <el-table-column prop="zone_name" label="分区" width="100" />
      <el-table-column prop="time_slot_label" label="时段" width="140" />
      <el-table-column label="档案预警" min-width="200">
        <template #default="{ row }">
          <el-tag v-if="row.pet.vaccine_status !== 'valid'" type="danger" size="small">疫苗{{ row.pet.vaccine_status === 'expired' ? '过期' : '缺失' }}</el-tag>
          <el-tag v-if="row.pet.attack_history" type="danger" size="small" style="margin-left:4px">有攻击史</el-tag>
          <el-tag v-if="row.pet.leash_required" type="warning" size="small" style="margin-left:4px">需牵引</el-tag>
          <span v-if="row.pet.vaccine_status === 'valid' && !row.pet.attack_history && !row.pet.leash_required" class="muted">无</span>
        </template>
      </el-table-column>
      <el-table-column label="核验结果" width="150">
        <template #default="{ row }">
          <template v-if="row.check">
            <el-tag :type="row.check.result === 'passed' ? 'success' : 'danger'" size="small">
              {{ row.check.result_label }}
            </el-tag>
            <div class="muted">{{ row.check.allowed_area_label }}</div>
          </template>
          <span v-else class="muted">待核验</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button v-if="!row.check && row.status === 'confirmed'" type="primary" size="small"
                     @click="openCheck(row)">核验</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!board.length && !loading" description="当日暂无待核验预约" />

    <el-dialog v-model="checkVisible" :title="`入园核验：${current?.pet_name || ''}`" width="560px">
      <template v-if="current">
        <el-descriptions :column="2" border size="small" style="margin-bottom:16px">
          <el-descriptions-item label="预约号">{{ current.code }}</el-descriptions-item>
          <el-descriptions-item label="主人">{{ current.owner_name }}</el-descriptions-item>
          <el-descriptions-item label="疫苗有效期">{{ current.pet.vaccine_expiry || '-' }}</el-descriptions-item>
          <el-descriptions-item label="犬证号">{{ current.pet.dog_license_no || '-' }}</el-descriptions-item>
        </el-descriptions>
        <el-form label-width="110px">
          <el-form-item v-for="item in checkItems" :key="item.field" :label="item.label">
            <el-switch v-model="checkForm[item.field]" active-text="通过" inactive-text="不通过" />
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="checkForm.notes" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item v-if="!allPassed" label="升级为事件">
            <el-switch v-model="checkForm.escalate" />
            <span class="muted" style="margin-left:8px">
              核验未通过，升级后将自动串联巡场、园区管理、主人、医院与客服
            </span>
          </el-form-item>
        </el-form>
        <el-alert v-if="!allPassed" type="error" :closable="false"
                  :title="`未通过项：${failedLabels}，该宠物将被禁止入园`" />
      </template>
      <template #footer>
        <el-button @click="checkVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitCheck">提交核验结果</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'

const date = ref(new Date().toISOString().slice(0, 10))
const board = ref([])
const loading = ref(false)
const checkVisible = ref(false)
const submitting = ref(false)
const current = ref(null)

const checkItems = [
  { field: 'vaccine_ok', label: '疫苗有效', failLabel: '疫苗过期/核验未通过' },
  { field: 'license_ok', label: '犬证有效', failLabel: '犬证无效' },
  { field: 'leash_ok', label: '牵引绳合规', failLabel: '牵引绳不合规' },
  { field: 'identity_ok', label: '主人身份一致', failLabel: '主人身份不符' },
]
const checkForm = reactive({
  vaccine_ok: true, license_ok: true, leash_ok: true, identity_ok: true,
  notes: '', escalate: true,
})

const allPassed = computed(() =>
  checkForm.vaccine_ok && checkForm.license_ok && checkForm.leash_ok && checkForm.identity_ok)
const failedLabels = computed(() =>
  checkItems.filter((i) => !checkForm[i.field]).map((i) => i.failLabel).join('、'))

async function load() {
  loading.value = true
  try {
    board.value = await api.get('/entry-checks/board', { params: { visit_date: date.value } })
  } finally {
    loading.value = false
  }
}

function openCheck(row) {
  current.value = row
  Object.assign(checkForm, {
    vaccine_ok: row.pet.vaccine_status === 'valid',
    license_ok: true, leash_ok: true, identity_ok: true,
    notes: '', escalate: row.pet.vaccine_status !== 'valid',
  })
  checkVisible.value = true
}

async function submitCheck() {
  submitting.value = true
  try {
    const res = await api.post('/entry-checks', {
      reservation_id: current.value.id, ...checkForm,
    })
    checkVisible.value = false
    if (res.result === 'passed') {
      ElMessage.success(`核验通过，允许进入：${res.allowed_area_label}`)
    } else {
      await ElMessageBox.alert(
        res.event_id
          ? `核验未通过（${res.fail_reasons}），已禁止入园，并升级为协同事件 #${res.event_id}`
          : `核验未通过（${res.fail_reasons}），已禁止入园`,
        '核验结果', { type: 'error' },
      )
    }
    load()
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>
