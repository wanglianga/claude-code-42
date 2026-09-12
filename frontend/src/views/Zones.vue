<template>
  <div class="page-card">
    <div class="toolbar">
      <h3 class="page-title" style="margin:0;flex:1">分区管理</h3>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>
    <el-table :data="zones" v-loading="loading">
      <el-table-column prop="name" label="分区" width="110" />
      <el-table-column prop="capacity" label="容量/时段" width="90" />
      <el-table-column label="允许体型" width="160">
        <template #default="{ row }">{{ row.allowed_size_labels.join('、') }}</template>
      </el-table-column>
      <el-table-column label="禁攻击史" width="90">
        <template #default="{ row }">{{ row.requires_no_attack_history ? '是' : '否' }}</template>
      </el-table-column>
      <el-table-column label="开放" width="80">
        <template #default="{ row }">
          <el-tag :type="row.active ? 'success' : 'info'" size="small">{{ row.active ? '开放' : '关闭' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="说明" min-width="220" show-overflow-tooltip />
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">调整</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="editVisible" :title="`调整分区：${form.name}`" width="480px">
      <el-form label-width="110px">
        <el-form-item label="每时段容量">
          <el-input-number v-model="form.capacity" :min="1" :max="500" />
        </el-form-item>
        <el-form-item label="是否开放">
          <el-switch v-model="form.active" />
        </el-form-item>
        <el-form-item label="允许体型">
          <el-checkbox-group v-model="form.allowed_sizes">
            <el-checkbox value="small">小型</el-checkbox>
            <el-checkbox value="medium">中型</el-checkbox>
            <el-checkbox value="large">大型</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="禁止攻击史">
          <el-switch v-model="form.requires_no_attack_history" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="save">保存（记入运营记录）</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const zones = ref([])
const loading = ref(false)
const editVisible = ref(false)
const form = reactive({
  id: null, name: '', capacity: 10, active: true,
  allowed_sizes: [], requires_no_attack_history: false, description: '',
})

async function load() {
  loading.value = true
  try {
    zones.value = await api.get('/zones')
  } finally {
    loading.value = false
  }
}

function openEdit(row) {
  Object.assign(form, {
    id: row.id, name: row.name, capacity: row.capacity, active: row.active,
    allowed_sizes: [...row.allowed_sizes],
    requires_no_attack_history: row.requires_no_attack_history,
    description: row.description,
  })
  editVisible.value = true
}

async function save() {
  await api.put(`/zones/${form.id}`, {
    capacity: form.capacity, active: form.active, allowed_sizes: form.allowed_sizes,
    requires_no_attack_history: form.requires_no_attack_history, description: form.description,
  })
  ElMessage.success('分区已调整')
  editVisible.value = false
  load()
}

onMounted(load)
</script>
