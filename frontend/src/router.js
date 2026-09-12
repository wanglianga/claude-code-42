import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from './store'

const routes = [
  { path: '/login', component: () => import('./views/Login.vue') },
  {
    path: '/',
    component: () => import('./views/Layout.vue'),
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', component: () => import('./views/Dashboard.vue'), meta: { title: '仪表盘' } },
      { path: 'pets', component: () => import('./views/Pets.vue'), meta: { title: '我的宠物', roles: ['owner'] } },
      { path: 'reservations', component: () => import('./views/Reservations.vue'), meta: { title: '预约入园', roles: ['owner', 'manager', 'admin'] } },
      { path: 'entry-check', component: () => import('./views/EntryCheck.vue'), meta: { title: '入园核验', roles: ['gate', 'manager', 'admin'] } },
      { path: 'incidents', component: () => import('./views/Incidents.vue'), meta: { title: '巡场上报', roles: ['patrol', 'manager', 'admin'] } },
      { path: 'events', component: () => import('./views/Events.vue'), meta: { title: '事件协同' } },
      { path: 'events/:id', component: () => import('./views/EventDetail.vue'), meta: { title: '事件详情' } },
      { path: 'blacklist', component: () => import('./views/Blacklist.vue'), meta: { title: '黑名单与限制' } },
      { path: 'analytics', component: () => import('./views/Analytics.vue'), meta: { title: '复盘分析', roles: ['manager', 'admin'] } },
      { path: 'zones', component: () => import('./views/Zones.vue'), meta: { title: '分区管理', roles: ['manager', 'admin'] } },
      { path: 'records', component: () => import('./views/Records.vue'), meta: { title: '运营记录', roles: ['manager', 'admin'] } },
    ],
  },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.path !== '/login' && !auth.isLoggedIn) return '/login'
  if (to.path === '/login' && auth.isLoggedIn) return '/dashboard'
  if (to.meta?.roles && !to.meta.roles.includes(auth.role)) return '/dashboard'
  return true
})

export default router
