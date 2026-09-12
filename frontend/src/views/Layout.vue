<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="logo">🐾 宠物公园平台</div>
      <el-menu :default-active="$route.path" router background-color="#001529"
               text-color="#a6adb4" active-text-color="#fff">
        <el-menu-item v-for="m in visibleMenus" :key="m.path" :index="m.path">
          <el-icon><component :is="m.icon" /></el-icon>
          <span>{{ m.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <div class="crumb">{{ $route.meta.title || '' }}</div>
        <div class="user">
          <el-tag size="small" effect="plain">{{ auth.user?.role_label }}</el-tag>
          <span class="name">{{ auth.user?.name }}</span>
          <el-button link type="danger" @click="logout">
            <el-icon><SwitchButton /></el-icon> 退出
          </el-button>
        </div>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../store'

const auth = useAuthStore()
const router = useRouter()

const menus = [
  { path: '/dashboard', title: '仪表盘', icon: 'Odometer' },
  { path: '/pets', title: '我的宠物', icon: 'Avatar', roles: ['owner'] },
  { path: '/reservations', title: '预约入园', icon: 'Calendar', roles: ['owner', 'manager', 'admin'] },
  { path: '/entry-check', title: '入园核验', icon: 'Checked', roles: ['gate', 'manager', 'admin'] },
  { path: '/incidents', title: '巡场上报', icon: 'Warning', roles: ['patrol', 'manager', 'admin'] },
  { path: '/events', title: '事件协同', icon: 'ChatDotRound' },
  { path: '/blacklist', title: '黑名单与限制', icon: 'CircleClose' },
  { path: '/analytics', title: '复盘分析', icon: 'DataAnalysis', roles: ['manager', 'admin'] },
  { path: '/zones', title: '分区管理', icon: 'Grid', roles: ['manager', 'admin'] },
  { path: '/records', title: '运营记录', icon: 'Document', roles: ['manager', 'admin'] },
]

const visibleMenus = computed(() =>
  menus.filter((m) => !m.roles || m.roles.includes(auth.role)),
)

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.layout { height: 100%; }
.aside { background: #001529; }
.logo {
  color: #fff; font-weight: 700; font-size: 16px; padding: 18px 16px;
  border-bottom: 1px solid rgba(255,255,255,.08);
}
.aside :deep(.el-menu) { border-right: none; }
.header {
  background: #fff; display: flex; align-items: center; justify-content: space-between;
  box-shadow: 0 1px 4px rgba(0,0,0,.08); z-index: 1;
}
.crumb { font-weight: 600; color: #303133; }
.user { display: flex; align-items: center; gap: 10px; }
.user .name { font-weight: 500; }
.main { background: #f5f7fa; padding: 20px; overflow-y: auto; }
</style>
