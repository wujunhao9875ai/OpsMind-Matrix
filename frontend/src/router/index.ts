import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView.vue'

const routes = [
  { path: '/', redirect: '/login' },
  { path: '/login', name: 'login', component: LoginView },
  { path: '/chat', name: 'chat', component: () => import('../views/ChatView.vue') },
  { path: '/admin', name: 'admin', component: () => import('../views/AdminDashboard.vue') },
  { path: '/engineer', name: 'engineer', component: () => import('../views/EngineerWorkbench.vue') },
  { path: '/storekeeper', name: 'storekeeper', component: () => import('../views/StorekeeperDashboard.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('token')
  if (to.path !== '/login' && !token) {
    next('/login')
    return
  }
  if (to.path === '/admin') {
    const role = localStorage.getItem('role') || 'user'
    if (role !== 'admin') {
      next('/chat')
      return
    }
  }
  if (to.path === '/engineer') {
    const role = localStorage.getItem('role') || 'user'
    if (role !== 'engineer') {
      next('/chat')
      return
    }
  }
  if (to.path === '/storekeeper') {
    const role = localStorage.getItem('role') || 'user'
    if (role !== 'storekeeper') {
      next('/chat')
      return
    }
  }
  next()
})

export default router