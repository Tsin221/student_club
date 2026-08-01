<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { ApiRequestError, getProfile } from '../api/auth'
import type { SelfUser } from '../types/user'


const emit = defineEmits<{
  navigate: [path: string]
}>()

const isLoading = ref(true)
const errorMessage = ref('')
const profile = ref<SelfUser | null>(null)
const showUpdateSuccess = ref(false)

const initials = computed(() => profile.value?.name.slice(0, 1) || '同')
const registeredAt = computed(() => {
  if (!profile.value) {
    return ''
  }
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'long',
    timeStyle: 'short',
    timeZone: 'Asia/Shanghai',
  }).format(new Date(profile.value.registered_at))
})


function dismissUpdateSuccess() {
  showUpdateSuccess.value = false
}


async function loadProfile() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    profile.value = await getProfile()
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
      errorMessage.value = error.message
    } else {
      errorMessage.value = '本人资料加载失败，请稍后重试'
    }
  } finally {
    isLoading.value = false
  }
}


onMounted(() => {
  if (window.location.search.includes('updated=1')) {
    showUpdateSuccess.value = true
  }
  loadProfile()
})
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
      <section class="page-heading" aria-labelledby="profile-title">
        <p class="section-kicker">个人中心</p>
        <h1 id="profile-title">本人资料</h1>
        <p>这里的信息来自当前服务端登录会话，刷新页面后会重新读取。</p>
      </section>

      <el-alert
        v-if="showUpdateSuccess"
        type="success"
        title="资料修改成功"
        :closable="true"
        show-icon
        class="form-alert"
        @close="dismissUpdateSuccess"
      />

      <el-card
        v-loading="isLoading"
        class="profile-card"
        shadow="never"
        aria-live="polite"
      >
        <template v-if="errorMessage">
          <el-result
            icon="error"
            title="资料加载失败"
            :sub-title="errorMessage"
          >
            <template #extra>
              <el-button type="primary" @click="loadProfile">
                重新加载
              </el-button>
            </template>
          </el-result>
        </template>

        <template v-else-if="profile">
          <div class="profile-summary">
            <div class="profile-avatar" aria-label="默认头像">
              {{ initials }}
            </div>
            <div class="profile-summary-body">
              <div class="profile-name-row">
                <h2>{{ profile.name }}</h2>
                <el-tag type="primary" effect="light">学生用户</el-tag>
                <el-tag type="success" effect="light">账号正常</el-tag>
              </div>
              <p>@{{ profile.username }}</p>
            </div>
            <div class="profile-actions">
              <el-button
                type="primary"
                plain
                @click="emit('navigate', '/student/clubs')"
              >
                社团广场
              </el-button>
              <el-button
                type="primary"
                plain
                @click="emit('navigate', '/student/memberships')"
              >
                我的社团
              </el-button>
              <el-button
                type="primary"
                plain
                @click="emit('navigate', '/student/applications')"
              >
                我的申请
              </el-button>
              <el-button
                type="primary"
                plain
                @click="emit('navigate', '/student/notifications')"
              >
                我的通知
              </el-button>
              <el-button
                type="primary"
                plain
                @click="emit('navigate', '/student/evaluations')"
              >
                我的评价
              </el-button>
              <el-button
                type="primary"
                plain
                @click="emit('navigate', '/student/feedbacks')"
              >
                我的反馈
              </el-button>
              <el-button
                type="primary"
                @click="emit('navigate', '/student/profile/edit')"
              >
                编辑资料
              </el-button>
            </div>
          </div>

          <el-divider />

          <el-descriptions :column="2" border>
            <el-descriptions-item label="用户名">
              {{ profile.username }}
            </el-descriptions-item>
            <el-descriptions-item label="姓名">
              {{ profile.name }}
            </el-descriptions-item>
            <el-descriptions-item label="手机号">
              {{ profile.phone }}
            </el-descriptions-item>
            <el-descriptions-item label="年级">
              {{ profile.grade }}
            </el-descriptions-item>
            <el-descriptions-item label="专业班级" :span="2">
              {{ profile.major_class }}
            </el-descriptions-item>
            <el-descriptions-item label="注册时间" :span="2">
              {{ registeredAt }}
            </el-descriptions-item>
          </el-descriptions>
        </template>
      </el-card>
    </div>
  </main>
</template>
