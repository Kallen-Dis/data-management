import { createRouter, createWebHashHistory } from 'vue-router'
import Login from './views/Login.vue'
import Dashboard from './views/Dashboard.vue'
import Editor from './views/Editor.vue'
import Fill from './views/Fill.vue'
import Stats from './views/Stats.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/login', component: Login },
    { path: '/', component: Dashboard, meta: { auth: true } },
    { path: '/editor/:id', component: Editor, meta: { auth: true } },
    { path: '/stats/:id', component: Stats, meta: { auth: true } },
    { path: '/s/:token', component: Fill },
  ],
})

router.beforeEach((to) => {
  if (to.meta.auth && !localStorage.getItem('token')) return '/login'
  if (to.path === '/login' && localStorage.getItem('token')) return '/'
})

export default router
