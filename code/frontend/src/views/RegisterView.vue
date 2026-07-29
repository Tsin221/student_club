<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'

import {
  ApiRequestError,
  registerStudent,
} from '../api/auth'
import { redirectAuthenticatedStudent } from '../composables/useStudentAuthRedirect'
import type { RegistrationInput } from '../types/user'


const emit = defineEmits<{
  navigate: [path: string]
}>()

const formRef = ref<FormInstance>()
const isSubmitting = ref(false)
const errorMessage = ref('')
const form = reactive<RegistrationInput>({
  username: '',
  password: '',
  name: '',
  phone: '',
  major_class: '',
  grade: '',
})
const rules: FormRules<RegistrationInput> = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { max: 150, message: '用户名不能超过 150 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码至少需要 8 个字符', trigger: 'blur' },
  ],
  name: [
    { required: true, message: '请输入姓名', trigger: 'blur' },
    { max: 50, message: '姓名不能超过 50 个字符', trigger: 'blur' },
  ],
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { max: 20, message: '手机号不能超过 20 个字符', trigger: 'blur' },
  ],
  major_class: [
    { required: true, message: '请输入专业班级', trigger: 'blur' },
    { max: 100, message: '专业班级不能超过 100 个字符', trigger: 'blur' },
  ],
  grade: [
    { required: true, message: '请输入年级', trigger: 'blur' },
    { max: 20, message: '年级不能超过 20 个字符', trigger: 'blur' },
  ],
}


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
    await registerStudent(form)
    emit('navigate', '/login?registered=1')
  } catch (error) {
    errorMessage.value = error instanceof ApiRequestError
      ? error.message
      : '暂时无法注册，请稍后重试'
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
  <main class="auth-page auth-page--register">
    <section class="auth-context" aria-labelledby="system-title">
      <p class="eyebrow">校园社团智能管理系统</p>
      <h1 id="system-title">创建你的学生账号</h1>
      <p>
        完整填写基础资料即可注册，无需管理员审核。注册成功后再返回登录页。
      </p>
      <ul class="context-list" aria-label="注册说明">
        <li>用户名在系统内唯一</li>
        <li>密码使用 Django 安全哈希保存</li>
        <li>平台角色与账号状态由服务端确定</li>
      </ul>
    </section>

    <section class="auth-form-panel" aria-labelledby="register-title">
      <div class="auth-form-wrap auth-form-wrap--wide">
        <p class="section-kicker">学生注册</p>
        <h2 id="register-title">填写账号资料</h2>
        <p class="form-intro">所有字段均为必填项。</p>

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
          <div class="form-grid">
            <el-form-item label="用户名" prop="username">
              <el-input
                v-model="form.username"
                name="username"
                autocomplete="username"
                maxlength="150"
                placeholder="设置唯一用户名"
              />
            </el-form-item>
            <el-form-item label="姓名" prop="name">
              <el-input
                v-model="form.name"
                name="name"
                autocomplete="name"
                maxlength="50"
                placeholder="请输入姓名"
              />
            </el-form-item>
            <el-form-item label="密码" prop="password">
              <el-input
                v-model="form.password"
                name="password"
                type="password"
                autocomplete="new-password"
                placeholder="至少 8 个字符"
                show-password
              />
            </el-form-item>
            <el-form-item label="手机号" prop="phone">
              <el-input
                v-model="form.phone"
                name="phone"
                autocomplete="tel"
                maxlength="20"
                placeholder="请输入手机号"
              />
            </el-form-item>
            <el-form-item label="专业班级" prop="major_class">
              <el-input
                v-model="form.major_class"
                name="major_class"
                maxlength="100"
                placeholder="例如：计算机科学与技术1班"
              />
            </el-form-item>
            <el-form-item label="年级" prop="grade">
              <el-input
                v-model="form.grade"
                name="grade"
                maxlength="20"
                placeholder="例如：2026"
                @keyup.enter="submit"
              />
            </el-form-item>
          </div>
          <el-button
            class="submit-button"
            type="primary"
            native-type="submit"
            :loading="isSubmitting"
          >
            创建账号
          </el-button>
        </el-form>

        <p class="auth-switch">
          已有账号？
          <a href="/login" @click.prevent="emit('navigate', '/login')">
            返回登录
          </a>
        </p>
      </div>
    </section>
  </main>
</template>
