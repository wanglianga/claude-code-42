<template>
  <div class="login-wrap">
    <div class="login-box">
      <div class="brand">
        <div class="logo">🐾</div>
        <h1>城市宠物公园</h1>
        <p>入园预约与冲突处置平台</p>
      </div>
      <el-form @submit.prevent="doLogin">
        <el-form-item>
          <el-input v-model="username" placeholder="用户名" size="large" :prefix-icon="User" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="password" type="password" placeholder="密码" size="large"
                    :prefix-icon="Lock" show-password @keyup.enter="doLogin" />
        </el-form-item>
        <el-button type="primary" size="large" style="width:100%" :loading="loading" @click="doLogin">
          登 录
        </el-button>
      </el-form>
      <el-divider content-position="center">演示账号（点击填充）</el-divider>
      <div class="demo-accounts">
        <el-tag v-for="a in accounts" :key="a.u" class="acct" @click="fill(a)">
          {{ a.label }} {{ a.u }}
        </el-tag>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import { useAuthStore } from '../store'

const router = useRouter()
const auth = useAuthStore()
const username = ref('')
const password = ref('')
const loading = ref(false)

const accounts = [
  { u: 'owner1', p: 'owner123', label: '宠物主人' },
  { u: 'owner2', p: 'owner123', label: '宠物主人' },
  { u: 'gate1', p: 'gate123', label: '核验员' },
  { u: 'patrol1', p: 'patrol123', label: '巡场员' },
  { u: 'manager1', p: 'manager123', label: '园区管理' },
  { u: 'hospital1', p: 'hospital123', label: '合作医院' },
  { u: 'service1', p: 'service123', label: '客服' },
  { u: 'admin', p: 'admin123', label: '管理员' },
]

function fill(a) {
  username.value = a.u
  password.value = a.p
}

async function doLogin() {
  if (!username.value || !password.value) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    const res = await api.post('/auth/login', { username: username.value, password: password.value })
    auth.setAuth(res.token, res.user)
    ElMessage.success(`欢迎，${res.user.name}`)
    router.push('/dashboard')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.login-box {
  width: 420px;
  background: #fff;
  border-radius: 12px;
  padding: 36px 36px 28px;
  box-shadow: 0 12px 40px rgba(0,0,0,.2);
}
.brand { text-align: center; margin-bottom: 24px; }
.brand .logo { font-size: 44px; }
.brand h1 { margin: 8px 0 4px; font-size: 22px; color: #303133; }
.brand p { margin: 0; color: #909399; font-size: 13px; }
.demo-accounts { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
.acct { cursor: pointer; }
</style>
