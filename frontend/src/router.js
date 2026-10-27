import { createRouter, createWebHashHistory } from 'vue-router'
const Login = () => import('./views/Login.vue')
const Dashboard = () => import('./views/Dashboard.vue')
const Editor = () => import('./views/Editor.vue')
const Fill = () => import('./views/Fill.vue')
const Stats = () => import('./views/Stats.vue')
const Questions = () => import('./views/Questions.vue')
const QuestionDetail = () => import('./views/QuestionDetail.vue')
const QuestionBanks = () => import('./views/QuestionBanks.vue')
const QuestionStats = () => import('./views/QuestionStats.vue')

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/login', component: Login },
    { path: '/', component: Dashboard, meta: { auth: true } },
    { path: '/editor/:id', component: Editor, meta: { auth: true } },
    { path: '/stats/:id', component: Stats, meta: { auth: true } },
    { path: '/questions', component: Questions, meta: { auth: true } },
    { path: '/questions/:id', component: QuestionDetail, meta: { auth: true } },
    { path: '/question-banks', component: QuestionBanks, meta: { auth: true } },
    { path: '/question-stats/:id', component: QuestionStats, meta: { auth: true } },
    { path: '/s/:token', component: Fill },
  ],
})

router.beforeEach((to) => {
  if (to.meta.auth && !localStorage.getItem('token')) return '/login'
  if (to.path === '/login' && localStorage.getItem('token')) return '/'
})

export default router
