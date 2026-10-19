<template>
  <div v-if="plainPage" class="plain-page">
    <router-view />
  </div>
  <div v-else class="app-shell">
    <aside class="sidebar">
      <router-link to="/" class="brand" aria-label="问卷星球工作台">
        <span class="brand-mark">S</span>
        <span class="brand-copy">
          <strong>问卷星球</strong>
          <small>SURVEYGO STUDIO</small>
        </span>
      </router-link>

      <div class="nav-caption">工作空间</div>
      <nav class="main-nav" aria-label="主导航">
        <router-link to="/" class="nav-item">
          <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="4" width="6" height="7" rx="1.5"/><rect x="14" y="4" width="6" height="4" rx="1.5"/><rect x="14" y="11" width="6" height="9" rx="1.5"/><rect x="4" y="14" width="6" height="6" rx="1.5"/></svg>
          <span>问卷工作台</span>
        </router-link>
      </nav>

      <div class="sidebar-spacer"></div>
      <div class="sidebar-note">
        <span class="note-orb">✦</span>
        <strong>让每个问题<br>都找到答案</strong>
        <span>创建、分享、洞察，一站完成。</span>
      </div>

      <div class="user-box">
        <div class="avatar">{{ username.slice(0, 1).toUpperCase() }}</div>
        <div class="user-info">
          <div class="name">{{ username }}</div>
          <div class="user-caption">问卷创建者</div>
        </div>
        <button class="logout" aria-label="退出登录" title="退出登录" @click="onLogout">↗</button>
      </div>
    </aside>

    <div class="main-shell">
      <header class="app-topbar">
        <div class="breadcrumbs"><span>工作空间</span><span class="crumb-separator">/</span><strong>{{ pageContext }}</strong></div>
        <div class="topbar-right"><span class="online-dot"></span><span>数据实时保存</span></div>
      </header>
      <main class="content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from './store'

const route = useRoute()
const router = useRouter()
const auth = useAuth()
const username = computed(() => auth.username || '用户')
const plainPage = computed(() => route.path === '/login' || route.path.startsWith('/s/'))
const pageContext = computed(() => {
  if (route.path.startsWith('/editor/')) return '问卷编辑器'
  if (route.path.startsWith('/stats/')) return '数据分析'
  return '我的问卷'
})

function onLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.app-shell { display: flex; min-height: 100%; }
.sidebar {
  width: 252px;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  padding: 27px 18px 18px;
  color: #d7deef;
  background: #111a2e;
  flex-shrink: 0;
}
.brand { display: flex; align-items: center; gap: 11px; padding: 2px 8px 34px; color: #fff; }
.brand-mark {
  width: 38px; height: 38px; display: grid; place-items: center;
  border-radius: 13px; color: #fff; font-size: 19px; font-weight: 800;
  background: linear-gradient(145deg, #7b7bff, #5453dc); box-shadow: 0 7px 20px #5959df55;
}
.brand-copy { display: flex; flex-direction: column; gap: 3px; }
.brand-copy strong { font-size: 16px; letter-spacing: .04em; }
.brand-copy small { color: #7785a5; font-size: 9px; letter-spacing: .16em; }
.nav-caption { padding: 0 12px 10px; color: #72809f; font-size: 11px; letter-spacing: .12em; }
.main-nav { display: flex; flex-direction: column; gap: 5px; }
.nav-item {
  display: flex; align-items: center; gap: 12px; padding: 12px 13px;
  color: #aeb9d0; font-size: 13px; font-weight: 550; border-radius: 10px;
  transition: background .18s ease, color .18s ease;
}
.nav-item svg { width: 18px; height: 18px; fill: none; stroke: currentColor; stroke-width: 1.7; }
.nav-item:hover, .nav-item.router-link-active { color: #fff; background: #283455; }
.nav-item.router-link-active svg { color: #9c9cff; }
.sidebar-spacer { flex: 1; min-height: 30px; }
.sidebar-note {
  position: relative; overflow: hidden; display: flex; flex-direction: column; gap: 9px;
  margin: 18px 2px; padding: 18px 16px; border: 1px solid #293653; border-radius: 14px;
  background: linear-gradient(145deg, #1b2844, #18223a);
}
.sidebar-note::after { content: ''; position: absolute; width: 90px; height: 90px; right: -42px; top: -44px; border: 1px solid #5363a044; border-radius: 50%; box-shadow: 0 0 0 13px #5363a018, 0 0 0 26px #5363a010; }
.note-orb { color: #a6a4ff; font-size: 17px; }
.sidebar-note strong { color: #f2f4fc; font-size: 14px; line-height: 1.55; }
.sidebar-note > span:last-child { color: #8d9ab4; font-size: 11px; line-height: 1.55; }
.user-box { display: flex; align-items: center; gap: 10px; padding: 14px 4px 2px; border-top: 1px solid #29334b; }
.avatar { width: 36px; height: 36px; display: grid; place-items: center; border-radius: 12px; color: #242559; background: #c7c8ff; font-size: 14px; font-weight: 750; }
.user-info { min-width: 0; flex: 1; }
.name { overflow: hidden; color: #f3f5fc; font-size: 12px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.user-caption { margin-top: 3px; color: #8491ab; font-size: 10px; }
.logout { width: 29px; height: 29px; border: 0; border-radius: 8px; color: #9aa8c2; background: transparent; cursor: pointer; font-size: 17px; }
.logout:hover { color: #fff; background: #293653; }
.main-shell { min-width: 0; min-height: 100vh; flex: 1; }
.app-topbar { height: 67px; display: flex; align-items: center; justify-content: space-between; padding: 0 38px; border-bottom: 1px solid #e9edf5; background: #ffffffb8; }
.breadcrumbs { display: flex; align-items: center; gap: 10px; color: #8892a8; font-size: 12px; }
.breadcrumbs strong { color: #36415b; font-weight: 650; }
.crumb-separator { color: #c2c8d5; }
.topbar-right { display: flex; align-items: center; gap: 8px; color: #8290a5; font-size: 11px; }
.online-dot { width: 7px; height: 7px; border-radius: 50%; background: #36bd8b; box-shadow: 0 0 0 4px #36bd8b1f; }
.content { max-width: 1560px; margin: 0 auto; padding: 32px 38px 48px; }
.plain-page { min-height: 100%; }
@media (max-width: 900px) {
  .sidebar { width: 208px; padding-right: 14px; padding-left: 14px; }
  .app-topbar { padding: 0 24px; }
  .content { padding: 26px 24px 40px; }
}
@media (max-width: 680px) {
  .app-shell { flex-direction: column; }
  .sidebar { width: 100%; min-height: 0; height: auto; flex-direction: row; align-items: center; gap: 14px; padding: 10px 16px; }
  .brand { padding: 0; }
  .brand-mark { width: 34px; height: 34px; }
  .brand-copy small, .nav-caption, .sidebar-spacer, .sidebar-note, .user-caption { display: none; }
  .main-nav { flex: 1; }
  .nav-item { padding: 9px 11px; }
  .user-box { margin-left: auto; padding: 0; border: 0; }
  .avatar { width: 32px; height: 32px; border-radius: 10px; }
  .user-info { display: none; }
  .main-shell { min-height: auto; }
  .app-topbar { height: 50px; padding: 0 17px; }
  .content { padding: 23px 16px 32px; }
}
</style>
