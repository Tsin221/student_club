<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { ApiRequestError } from '../api/auth'
import { getClubDetail } from '../api/clubs'
import type { Club } from '../types/club'


const emit = defineEmits<{
  navigate: [path: string]
}>()

//从 URL 路径解析 clubId
function parseClubId(): number {
  const parts = window.location.pathname.split('/')
  // /student/clubs/123 → parts = ['', 'student', 'clubs', '123']
  const id = Number(parts[parts.length - 1])
  return Number.isFinite(id) && id > 0 ? id : NaN
}

// ── 状态 ──────────────────────────────────────────────────

const isLoading = ref(true)
const errorMessage = ref('')
const club = ref<Club | null>(null)
const clubId = parseClubId()

// ── 数据加载 ──────────────────────────────────────────────

async function loadDetail() {
  if (Number.isNaN(clubId)) {
    errorMessage.value = '无效的社团 ID'
    isLoading.value = false
    return
  }

  isLoading.value = true
  errorMessage.value = ''
  try {
    club.value = await getClubDetail(clubId)
  } catch (error) {
    if (error instanceof ApiRequestError) {
      if (error.code === 'UNAUTHENTICATED') {
        emit('navigate', '/login?reason=session')
        return
      }
      errorMessage.value = error.message
    } else {
      errorMessage.value = '社团详情加载失败，请稍后重试'
    }
  } finally {
    isLoading.value = false
  }
}


function goBack() {
  emit('navigate', '/student/clubs')
}


function formatDate(isoString: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'long',
    timeZone: 'Asia/Shanghai',
  }).format(new Date(isoString))
}


onMounted(() => {
  loadDetail()
})
</script>

<template>
  <main class="student-page">
    <header class="student-header">
      <div class="brand-mark" aria-hidden="true">社</div>
      <div>
        <p class="eyebrow">校园社团智能管理系统</p>
        <p class="header-title">社团详情</p>
      </div>
    </header>

    <div class="student-content">
      <el-button
        text
        type="primary"
        style="margin-bottom: 24px"
        @click="goBack"
      >
        ← 返回社团列表
      </el-button>

      <!-- 错误状态 -->
      <el-alert
        v-if="errorMessage"
        type="error"
        :title="errorMessage"
        :closable="false"
        show-icon
        class="form-alert"
      />

      <!-- 加载 -->
      <el-card
        v-if="isLoading"
        v-loading="true"
        class="profile-card"
        shadow="never"
        style="min-height: 240px"
      />

      <!-- 详情 -->
      <template v-else-if="club">
        <el-card class="profile-card" shadow="never">
          <div class="profile-summary">
            <div
              v-if="club.logo"
              class="club-detail-logo"
            >
              <img
                :src="club.logo"
                :alt="`${club.name} Logo`"
                class="club-detail-logo-img"
              >
            </div>
            <div class="profile-summary-body">
              <div class="profile-name-row">
                <h2>{{ club.name }}</h2>
                <el-tag
                  :type="club.status === 'normal' ? 'success' : 'info'"
                  effect="light"
                  size="small"
                >
                  {{ club.status === 'normal' ? '正常' : '已注销' }}
                </el-tag>
              </div>
              <p>
                <strong>类别：</strong>{{ club.category }}
                &nbsp;|&nbsp;
                <strong>创建于：</strong>{{ formatDate(club.created_at) }}
              </p>
            </div>
          </div>
        </el-card>

        <el-card
          class="profile-card"
          shadow="never"
          style="margin-top: 20px"
        >
          <h3 style="margin: 0 0 12px">社团简介</h3>
          <p style="color: var(--muted); line-height: 1.8; white-space: pre-wrap">
            {{ club.introduction }}
          </p>
        </el-card>
      </template>
    </div>
  </main>
</template>

<style scoped>
.club-detail-logo {
  width: 80px;
  height: 80px;
  border-radius: 16px;
  overflow: hidden;
  background: var(--brand-100);
}

.club-detail-logo-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>
