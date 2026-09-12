<template>
  <div>
    <div class="page-card" style="margin-bottom:16px">
      <h3 class="page-title">冲突复盘分析（按体型 / 品种 / 活动类型）</h3>
      <el-row :gutter="16">
        <el-col :span="8"><Chart :option="sizeOption" /></el-col>
        <el-col :span="8"><Chart :option="typeOption" /></el-col>
        <el-col :span="8"><Chart :option="severityOption" /></el-col>
        <el-col :span="12"><Chart :option="breedOption" /></el-col>
        <el-col :span="12"><Chart :option="zoneOption" /></el-col>
        <el-col :span="12"><Chart :option="monthlyOption" /></el-col>
        <el-col :span="12"><Chart :option="eventTypeOption" /></el-col>
      </el-row>
    </div>

    <el-row :gutter="16">
      <el-col :span="10">
        <div class="page-card">
          <h3 class="page-title">高冲突品种明细</h3>
          <el-table :data="data.breed_detail || []" size="small">
            <el-table-column prop="breed" label="品种" />
            <el-table-column prop="size" label="体型" width="80" />
            <el-table-column prop="count" label="冲突次数" width="90" sortable />
          </el-table>
          <el-alert type="info" :closable="false" style="margin-top:12px"
                    title="复盘结论可用于：重新划分分区、增加巡场员、限制某些宠物活动" />
        </div>
      </el-col>
      <el-col :span="14">
        <div class="page-card">
          <h3 class="page-title">复盘决策</h3>
          <el-form inline>
            <el-form-item>
              <el-input v-model="decisionForm.title" placeholder="决策标题" style="width:180px" />
            </el-form-item>
            <el-form-item>
              <el-select v-model="decisionForm.decision_type" style="width:170px">
                <el-option label="重新划分分区" value="rezone" />
                <el-option label="增加巡场员" value="add_patrol" />
                <el-option label="限制特定宠物活动" value="restrict_pets" />
                <el-option label="制度调整" value="policy" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-input v-model="decisionForm.content" placeholder="决策内容" style="width:240px" />
            </el-form-item>
            <el-button type="primary" @click="addDecision">发布决策</el-button>
          </el-form>
          <el-table :data="decisions" size="small" style="margin-top:8px">
            <el-table-column prop="title" label="标题" min-width="140" show-overflow-tooltip />
            <el-table-column prop="decision_type_label" label="类型" width="130" />
            <el-table-column prop="content" label="内容" min-width="180" show-overflow-tooltip />
            <el-table-column prop="creator" label="发布人" width="90" />
            <el-table-column prop="created_at" label="时间" width="140" />
          </el-table>
          <el-empty v-if="!decisions.length" description="暂无决策" :image-size="60" />
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import Chart from './Chart.vue'

const data = ref({})
const decisions = ref([])
const decisionForm = reactive({ title: '', decision_type: 'rezone', content: '' })

const pie = (title, rows) => ({
  title: { text: title, left: 'center', textStyle: { fontSize: 14 } },
  tooltip: { trigger: 'item' },
  series: [{
    type: 'pie', radius: ['35%', '65%'],
    label: { formatter: '{b}: {c}' },
    data: (rows || []).map((r) => ({ name: r.label, value: r.value })),
  }],
})
const bar = (title, rows) => ({
  title: { text: title, left: 'center', textStyle: { fontSize: 14 } },
  tooltip: {},
  grid: { left: 40, right: 20, top: 40, bottom: 60 },
  xAxis: { type: 'category', data: (rows || []).map((r) => r.label), axisLabel: { rotate: 30 } },
  yAxis: { type: 'value', minInterval: 1 },
  series: [{ type: 'bar', data: (rows || []).map((r) => r.value), itemStyle: { color: '#409eff' } }],
})

const sizeOption = computed(() => pie('按宠物体型', data.value.by_size))
const typeOption = computed(() => pie('按行为类型', data.value.by_type))
const severityOption = computed(() => pie('按严重程度', data.value.by_severity))
const breedOption = computed(() => bar('按品种（Top10）', data.value.by_breed))
const zoneOption = computed(() => bar('按活动分区', data.value.by_zone))
const eventTypeOption = computed(() => pie('事件类型分布', data.value.events_by_type))
const monthlyOption = computed(() => ({
  title: { text: '冲突月度趋势', left: 'center', textStyle: { fontSize: 14 } },
  tooltip: { trigger: 'axis' },
  grid: { left: 40, right: 20, top: 40, bottom: 40 },
  xAxis: { type: 'category', data: (data.value.monthly || []).map((r) => r.label) },
  yAxis: { type: 'value', minInterval: 1 },
  series: [{ type: 'line', smooth: true, areaStyle: {}, data: (data.value.monthly || []).map((r) => r.value) }],
}))

async function load() {
  data.value = await api.get('/analytics/conflicts')
  decisions.value = await api.get('/analytics/decisions')
}

async function addDecision() {
  if (!decisionForm.title) {
    ElMessage.warning('请填写决策标题')
    return
  }
  await api.post('/analytics/decisions', decisionForm)
  Object.assign(decisionForm, { title: '', content: '' })
  ElMessage.success('决策已发布并记入运营记录')
  decisions.value = await api.get('/analytics/decisions')
}

onMounted(load)
</script>
