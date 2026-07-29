<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'

import {
  ApiRequestError,
  login,
} from '../api/auth'
import { redirectAuthenticatedStudent } from '../composables/useStudentAuthRedirect'
import type { LoginInput } from '../types/user'


const emit = defineEmits<{
  navigate: [path: string]
}>()

const formRef = ref<FormInstance>()
const isSubmitting = ref(false)
const errorMessage = ref('')
const form = reactive<LoginInput>({
  username: '',
  password: '',
})
const rules: FormRules<LoginInput> = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
  ],
}

const query = new URLSearchParams(window.location.search)
const statusMessage = computed(() => {
  if (query.get('registered') === '1') {
    return '注册成功，请使用新账号登录。'
  }
  if (query.get('reason') === 'disabled') {
    return '账号已停用，暂时无法访问个人中心。'
  }
  if (query.get('reason') === 'session') {
    return '登录状态已失效，请重新登录。'
  }
  return ''
})


async function submit() {
  if (!formRef.value) {
    return
  }

  try {
    await formRef.value.validate()
  } catch {
    return
  }

  isSubmitting.value = true
  errorMessage.value = ''
  try {
    await login(form)
    emit('navigate', '/student')
  } catch (error) {
    errorMessage.value = error instanceof ApiRequestError
      ? error.message
      : '暂时无法登录，请稍后重试'
  } finally {
    isSubmitting.value = false
  }
}


onMounted(() => {
  void redirectAuthenticatedStudent(
    (path) => emit('navigate', path),
    (message) => {
      errorMessage.value = message
    },
  )
})
</script>

<template>
  <main class="auth-page">
    <section class="auth-context" aria-labelledby="system-title">
      <p class="eyebrow">校园社团智能管理系统</p>
      <h1 id="system-title">从个人中心开始你的社团旅程</h1>
      <p>
        使用学生账号登录，查看本人资料，并进入后续开放的社团服务。
      </p>
      <ul class="context-list" aria-label="账号安全说明">
        <li>登录状态由服务端安全会话保存</li>
        <li>系统不会在浏览器中保存认证令牌</li>
      </ul>
    </section>

    <section class="auth-form-panel" aria-labelledby="login-title">
      <div class="auth-form-wrap">
        <p class="section-kicker">学生入口</p>
        <h2 id="login-title">欢迎回来</h2>
        <p class="form-intro">请输入用户名和密码登录。</p>

        <el-alert
          v-if="statusMessage"
          class="form-alert"
          :title="statusMessage"
          type="success"
          :closable="false"
          show-icon
        />
        <el-alert
          v-if="errorMessage"
          class="form-alert"
          :title="errorMessage"
          type="error"
          :closable="false"
          show-icon
        />

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          size="large"
          @submit.prevent="submit"
        >
          <el-form-item label="用户名" prop="username">
            <el-input
              v-model="form.username"
              name="username"
              autocomplete="username"
              maxlength="150"
              placeholder="请输入用户名"
            />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              name="password"
              type="password"
              autocomplete="current-password"
              placeholder="请输入密码"
              show-password
              @keyup.enter="submit"
            />
          </el-form-item>
          <el-button
            class="submit-button"
            type="primary"
            native-type="submit"
            :loading="isSubmitting"
          >
            登录
          </el-button>
        </el-form>

        <p class="auth-switch">
          还没有账号？
          <a href="/register" @click.prevent="emit('navigate', '/register')">
            注册学生账号
          </a>
        </p>
      </div>
    </section>
  </main>
</template>
