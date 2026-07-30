<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { ApiRequestError, getProfile, updateProfile } from '../api/auth'
import type { SelfUser } from '../types/user'


const emit = defineEmits<{
  navigate: [path: string]
}>()

const isLoading = ref(true)
const isSaving = ref(false)
const loadError = ref('')
const saveError = ref('')
const saveSuccess = ref('')

const form = reactive({
  name: '',
  phone: '',
  major_class: '',
  grade: '',
})

const fieldMaxLengths: Record<string, number> = {
  name: 50,
  phone: 20,
  major_class: 100,
  grade: 20,
}


function fillForm(profile: SelfUser) {
  form.name = profile.name
  form.phone = profile.phone
  form.major_class = profile.major_class
  form.grade = profile.grade
}


const currentProfile = ref<SelfUser | null>(null)


async function loadProfile() {
  isLoading.value = true
  loadError.value = ''
  try {
    const profile = await getProfile()
    currentProfile.value = profile
    fillForm(profile)
  } catch (error) {
    if (error instanceof ApiRequestError) {
      if (error.code === 'UNAUTHENTICATED') {
        emit('navigate', '/login?reason=session')
        return
      }
      if (error.code === 'ACCOUNT_DISABLED') {
        emit('navigate', '/login?reason=disabled')
        return
      }
      loadError.value = error.message
    } else {
      loadError.value = '资料加载失败，请稍后重试'
    }
  } finally {
    isLoading.value = false
  }
}


async function handleSave() {
  saveError.value = ''
  saveSuccess.value = ''

  // 前端校验：至少一个字段有变化
  const trimmedName = form.name.trim()
  const trimmedPhone = form.phone.trim()
  const trimmedMajor = form.major_class.trim()
  const trimmedGrade = form.grade.trim()

  const payload: Record<string, string> = {}
  if (trimmedName !== currentProfile.value?.name) payload.name = trimmedName
  if (trimmedPhone !== currentProfile.value?.phone) payload.phone = trimmedPhone
  if (trimmedMajor !== currentProfile.value?.major_class) payload.major_class = trimmedMajor
  if (trimmedGrade !== currentProfile.value?.grade) payload.grade = trimmedGrade

  if (Object.keys(payload).length === 0) {
    saveError.value = '请至少修改一个字段'
    return
  }

  // 非空校验
  for (const [field, value] of Object.entries(payload)) {
    if (!value) {
      saveError.value = '修改字段不能为空'
      return
    }
  }

  // 长度校验
  for (const [field, value] of Object.entries(payload)) {
    const max = fieldMaxLengths[field]
    if (max && value.length > max) {
      saveError.value = `${getFieldLabel(field)} 超过允许长度`
      return
    }
  }

  isSaving.value = true
  try {
    await updateProfile(payload)
    saveSuccess.value = '资料修改成功'
    // 短暂延迟后跳转，让用户看到成功反馈
    setTimeout(() => {
      emit('navigate', '/student?updated=1')
    }, 800)
  } catch (error) {
    if (error instanceof ApiRequestError) {
      saveError.value = error.message
    } else {
      saveError.value = '保存失败，请稍后重试'
    }
  } finally {
    isSaving.value = false
  }
}


function getFieldLabel(field: string): string {
  const labels: Record<string, string> = {
    name: '姓名',
    phone: '手机号',
    major_class: '专业班级',
    grade: '年级',
  }
  return labels[field] || field
}


function goBack() {
  emit('navigate', '/student')
}


onMounted(loadProfile)
</script>

<template>
  <main class="student-page">
    <header class="student-header">
      <div class="brand-mark" aria-hidden="true">社</div>
      <div>
        <p class="eyebrow">校园社团智能管理系统</p>
        <p class="header-title">学生个人中心</p>
      </div>
    </header>

    <div class="student-content">
      <section class="page-heading" aria-labelledby="edit-title">
        <p class="section-kicker">个人中心</p>
        <h1 id="edit-title">编辑资料</h1>
        <p>你可以修改自己的姓名、手机号、专业班级和年级。</p>
      </section>

      <el-card
        v-loading="isLoading"
        class="profile-card"
        shadow="never"
        aria-live="polite"
      >
        <!-- 加载失败 -->
        <template v-if="loadError">
          <el-result
            icon="error"
            title="资料加载失败"
            :sub-title="loadError"
          >
            <template #extra>
              <el-button type="primary" @click="loadProfile">
                重新加载
              </el-button>
            </template>
          </el-result>
        </template>

        <!-- 编辑表单 -->
        <template v-else-if="currentProfile">
          <el-form
            label-position="top"
            :disabled="isSaving"
            @submit.prevent="handleSave"
          >
            <el-row :gutter="24">
              <el-col :span="12">
                <el-form-item label="姓名">
                  <el-input
                    v-model="form.name"
                    maxlength="50"
                    show-word-limit
                    autocomplete="name"
                    placeholder="请输入姓名"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="手机号">
                  <el-input
                    v-model="form.phone"
                    maxlength="20"
                    show-word-limit
                    autocomplete="tel"
                    placeholder="请输入手机号"
                  />
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="24">
              <el-col :span="12">
                <el-form-item label="专业班级">
                  <el-input
                    v-model="form.major_class"
                    maxlength="100"
                    show-word-limit
                    autocomplete="organization"
                    placeholder="请输入专业班级"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="年级">
                  <el-input
                    v-model="form.grade"
                    maxlength="20"
                    show-word-limit
                    placeholder="请输入年级"
                  />
                </el-form-item>
              </el-col>
            </el-row>

            <!-- 保存成功提示 -->
            <el-alert
              v-if="saveSuccess"
              type="success"
              :title="saveSuccess"
              :closable="false"
              show-icon
              class="form-alert"
            />

            <!-- 保存失败提示 -->
            <el-alert
              v-if="saveError"
              type="error"
              :title="saveError"
              :closable="false"
              show-icon
              class="form-alert"
            />

            <div class="edit-actions">
              <el-button @click="goBack" :disabled="isSaving">
                ← 返回个人中心
              </el-button>
              <el-button
                type="primary"
                :loading="isSaving"
                @click="handleSave"
                class="submit-button"
              >
                {{ isSaving ? '保存中…' : '保存修改' }}
              </el-button>
            </div>
          </el-form>
        </template>
      </el-card>
    </div>
  </main>
</template>

<style scoped>
.edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 28px;
  padding-top: 24px;
  border-top: 1px solid var(--border);
}

.submit-button {
  min-width: 120px;
  font-weight: 700;
}
</style>
