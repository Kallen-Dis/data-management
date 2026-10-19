import axios from 'axios'

// 统一请求封装：自动携带 JWT；401 时（非填写页）跳转登录
const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((cfg) => {
  const token = localStorage.getItem('token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const status = err.response?.status
    const onFillPage = location.hash.includes('#/s/')
    if (status === 401 && !onFillPage) {
      localStorage.removeItem('token')
      localStorage.removeItem('username')
      location.hash = '#/login'
    }
    return Promise.reject(err)
  }
)

export default api
