<template>
  <div class="login-wrap">
    <section class="login-visual">
      <div class="visual-brand"><span class="visual-mark">S</span><div><strong>问卷星球</strong><small>SURVEYGO STUDIO</small></div></div>
      <div class="visual-copy">
        <div class="visual-kicker"><span></span> LISTEN TO EVERY VOICE</div>
        <h1>让好问题，<br>带来新发现。</h1>
        <p>从灵感到洞察，轻松完成每一次调研。</p>
      </div>
      <div class="visual-art" aria-hidden="true">
        <div class="visual-ring ring-a"></div>
        <div class="visual-ring ring-b"></div>
        <div class="visual-orbit-dot"></div>
        <div class="visual-survey-card">
          <div class="mini-card-head"><span>Q</span><i></i><i></i></div>
          <div class="mini-choice"><b>✓</b><span></span></div>
          <div class="mini-choice"><b></b><span></span></div>
          <div class="mini-choice"><b></b><span></span></div>
        </div>
        <div class="visual-stat-card"><span>回答已收集</span><strong>1,284 <i>↗</i></strong><div><b></b><b></b><b></b><b></b><b></b><b></b><b></b><b></b></div></div>
        <span class="visual-spark spark-a">✦</span><span class="visual-spark spark-b">✧</span>
      </div>
      <div class="visual-footer"><span>✳</span> 简单创建 · 智能分析 · 安心分享</div>
    </section>

    <section class="login-panel">
      <div class="login-card">
        <div class="welcome-kicker">WELCOME TO SURVEYGO</div>
        <h2>{{ mode === 'login' ? '欢迎回来' : '创建你的账号' }}</h2>
        <p class="welcome-copy">{{ mode === 'login' ? '登录后继续管理问卷与查看调研结果。' : '注册后即可开始创建你的第一份问卷。' }}</p>

        <div class="tabs" role="tablist" aria-label="登录或注册">
          <button :class="{ active: mode === 'login' }" role="tab" :aria-selected="mode === 'login'" @click="mode = 'login'">登录</button>
          <button :class="{ active: mode === 'register' }" role="tab" :aria-selected="mode === 'register'" @click="mode = 'register'">注册</button>
        </div>

        <el-form class="auth-form" @submit.prevent="submit">
          <el-form-item>
            <label class="input-label" for="username">用户名</label>
            <el-input id="username" v-model="username" placeholder="请输入用户名" size="large" autocomplete="username" />
          </el-form-item>
          <el-form-item>
            <label class="input-label" for="password">密码</label>
            <el-input
              id="password"
              v-model="password"
              type="password"
              :placeholder="mode === 'register' ? '至少 6 位字符' : '请输入密码'"
              size="large"
              autocomplete="current-password"
              show-password
              @keyup.enter="submit"
            />
          </el-form-item>
          <el-button type="primary" size="large" class="submit" :loading="loading" native-type="submit">
            {{ mode === 'login' ? '登录工作台' : '创建账号' }} <span v-if="!loading" aria-hidden="true">→</span>
          </el-button>
        </el-form>
        <div class="security-note"><span>▣</span> 你的问卷和数据仅对你可见</div>
      </div>
      <div class="panel-footer">© SurveyGo <span>·</span> 让数据收集更轻松</div>
    </section>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api'
import { useAuth } from '../store'

const router = useRouter()
const auth = useAuth()
const mode = ref('login')
const username = ref('')
const password = ref('')
const loading = ref(false)

async function submit() {
  if (!username.value.trim() || !password.value) return ElMessage.warning('请输入用户名和密码')
  loading.value = true
  try {
    const path = mode.value === 'login' ? '/auth/login' : '/auth/register'
    const { data } = await api.post(path, {
      username: username.value.trim(),
      password: password.value,
    })
    auth.setAuth(data.access_token, data.username)
    ElMessage.success(mode.value === 'login' ? '欢迎回来！' : '注册成功！')
    const after = sessionStorage.getItem('after_login')
    sessionStorage.removeItem('after_login')
    router.push((after || '').replace(/^#/, '') || '/')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败，请重试')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap { min-height: 100vh; display: grid; grid-template-columns: minmax(380px, 1fr) minmax(430px, .82fr); background: #fff; }
.login-visual { position: relative; min-height: 100vh; overflow: hidden; padding: 32px clamp(28px, 6vw, 82px); color: #fff; background: radial-gradient(circle at 75% 38%, #303d69 0, transparent 37%), linear-gradient(145deg, #121a30, #20294c 70%, #262f59); }
.visual-brand { display: flex; align-items: center; gap: 11px; }
.visual-mark { width: 39px; height: 39px; display: grid; place-items: center; border-radius: 13px; color: #fff; background: linear-gradient(145deg, #8886ff, #5a59d6); box-shadow: 0 8px 20px #5552d755; font-size: 19px; font-weight: 800; }
.visual-brand > div { display: flex; flex-direction: column; gap: 3px; }
.visual-brand strong { font-size: 15px; letter-spacing: .04em; }
.visual-brand small { color: #8691b4; font-size: 8px; letter-spacing: .15em; }
.visual-copy { position: relative; z-index: 2; margin-top: clamp(70px, 13vh, 130px); }
.visual-kicker { display: flex; align-items: center; gap: 8px; color: #a8add1; font-size: 9px; font-weight: 700; letter-spacing: .16em; }
.visual-kicker span { width: 6px; height: 6px; border-radius: 50%; background: #58d0ad; box-shadow: 0 0 0 4px #58d0ad20; }
.visual-copy h1 { margin: 18px 0 11px; color: #fff; font-size: clamp(37px, 5vw, 58px); font-weight: 750; letter-spacing: -.055em; line-height: 1.23; }
.visual-copy p { margin: 0; color: #aab3cd; font-size: 13px; }
.visual-art { position: absolute; right: 2%; bottom: 8%; width: min(54%, 420px); height: 340px; }
.visual-ring { position: absolute; border: 1px solid #9e9ced33; border-radius: 50%; }
.ring-a { top: 1px; right: 13px; width: 300px; height: 300px; }
.ring-b { top: 36px; right: 48px; width: 230px; height: 230px; border-style: dashed; border-color: #8ab6d633; }
.visual-orbit-dot { position: absolute; top: 43px; right: 38px; width: 13px; height: 13px; border: 3px solid #252f55; border-radius: 50%; background: #8e8bf1; }
.visual-survey-card { position: absolute; top: 53px; right: 129px; width: 153px; padding: 18px 15px; border: 1px solid #ffffff50; border-radius: 15px; background: #ffffffed; box-shadow: 0 20px 45px #090d2050; transform: rotate(-7deg); }
.mini-card-head > span { display: inline-grid; width: 25px; height: 25px; place-items: center; margin-bottom: 12px; border-radius: 8px; color: #fff; background: #6967dc; font-size: 12px; font-weight: 800; }
.mini-card-head i { display: block; width: 67%; height: 5px; margin: 4px 0; border-radius: 4px; background: #e5e7f1; }
.mini-card-head i:last-child { width: 42%; margin-bottom: 13px; }
.mini-choice { display: flex; align-items: center; gap: 8px; margin: 8px 0; }
.mini-choice b { width: 12px; height: 12px; display: grid; place-items: center; border: 1px solid #cdd2e1; border-radius: 50%; color: #fff; font-size: 8px; }
.mini-choice:first-of-type b { border-color: #6967dc; background: #6967dc; }
.mini-choice span { width: 58%; height: 4px; border-radius: 4px; background: #e7e9f2; }
.visual-stat-card { position: absolute; right: 0; bottom: 30px; width: 154px; padding: 13px; border: 1px solid #ffffff36; border-radius: 13px; color: #c4cbe0; background: #29365ee8; box-shadow: 0 15px 35px #090d2040; transform: rotate(6deg); }
.visual-stat-card > span { color: #aeb8d1; font-size: 8px; }
.visual-stat-card strong { display: block; margin: 4px 0 10px; color: #fff; font-size: 19px; }
.visual-stat-card strong i { color: #5bd0ac; font-size: 11px; font-style: normal; }
.visual-stat-card > div { height: 22px; display: flex; align-items: flex-end; gap: 5px; }
.visual-stat-card b { width: 10px; height: 40%; border-radius: 3px 3px 0 0; background: #7376d8; }
.visual-stat-card b:nth-child(2n) { height: 75%; background: #4baf9a; }
.visual-stat-card b:nth-child(3n) { height: 57%; }
.visual-stat-card b:nth-child(5) { height: 95%; background: #8582eb; }
.visual-spark { position: absolute; color: #a7a4ff; }
.spark-a { top: 24px; right: 111px; font-size: 23px; }
.spark-b { right: 305px; bottom: 74px; color: #59bdac; font-size: 27px; }
.visual-footer { position: absolute; bottom: 28px; left: clamp(28px, 6vw, 82px); color: #8994b2; font-size: 9px; }
.visual-footer span { margin-right: 6px; color: #5bd0ac; }
.login-panel { min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 55px 38px 25px; background: #fff; }
.login-card { width: 100%; max-width: 390px; }
.welcome-kicker { margin-bottom: 9px; color: #8886c7; font-size: 9px; font-weight: 750; letter-spacing: .16em; }
.login-card h2 { margin: 0; color: #29334b; font-size: 27px; font-weight: 750; letter-spacing: -.04em; }
.welcome-copy { margin: 8px 0 26px; color: #8892a5; font-size: 11px; line-height: 1.6; }
.tabs { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; margin-bottom: 22px; padding: 4px; border-radius: 10px; background: #f2f3f8; }
.tabs button { min-height: 34px; border: 0; border-radius: 7px; color: #8992a5; background: transparent; cursor: pointer; font-size: 11px; font-weight: 600; }
.tabs button.active { color: #5452bb; background: #fff; box-shadow: 0 1px 5px #28365314; }
.auth-form :deep(.el-form-item) { display: block; margin-bottom: 15px; }
.input-label { display: block; margin-bottom: 7px; color: #556078; font-size: 10px; font-weight: 650; }
.auth-form :deep(.el-input__wrapper) { min-height: 43px; border-radius: 9px; padding: 1px 13px; }
.submit { width: 100%; height: 43px; display: flex; justify-content: center; gap: 9px; margin-top: 7px; border-radius: 9px; font-size: 11px; font-weight: 650; }
.security-note { display: flex; align-items: center; justify-content: center; gap: 7px; margin-top: 21px; color: #99a2b2; font-size: 9px; }
.security-note span { color: #41ab88; font-size: 12px; }
.panel-footer { margin-top: auto; padding-top: 45px; color: #a5adbb; font-size: 9px; }
.panel-footer span { padding: 0 5px; color: #c4cad3; }
@media (max-width: 850px) {
  .login-wrap { grid-template-columns: minmax(290px, .85fr) minmax(390px, 1fr); }
  .login-visual { padding-right: 28px; padding-left: 28px; }
  .visual-art { right: -80px; transform: scale(.8); transform-origin: right bottom; }
  .visual-footer { left: 28px; }
  .login-panel { padding-right: 26px; padding-left: 26px; }
}
@media (max-width: 650px) {
  .login-wrap { min-height: 100vh; display: block; background: #f4f6fb; }
  .login-visual { min-height: 205px; height: 205px; padding: 18px 20px; }
  .visual-mark { width: 32px; height: 32px; border-radius: 10px; font-size: 15px; }
  .visual-brand strong { font-size: 13px; }
  .visual-brand small { font-size: 7px; }
  .visual-copy { margin-top: 23px; }
  .visual-kicker { font-size: 7px; }
  .visual-copy h1 { margin: 8px 0 5px; font-size: 24px; }
  .visual-copy p { font-size: 9px; }
  .visual-art { right: -154px; bottom: -164px; transform: scale(.52); }
  .visual-footer { display: none; }
  .login-panel { min-height: calc(100vh - 205px); justify-content: flex-start; padding: 31px 22px 18px; }
  .login-card { max-width: 440px; }
  .login-card h2 { font-size: 23px; }
  .welcome-copy { margin-bottom: 20px; }
  .panel-footer { padding-top: 30px; }
}
</style>
