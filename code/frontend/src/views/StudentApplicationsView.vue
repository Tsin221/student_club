<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { ApiRequestError } from '../api/auth'
import { getMyApplications } from '../api/applications'
import type { JoinApplication } from '../types/club'


const emit = defineEmits<{
  navigate: [path: string]
}>()

const isLoading = ref(true)
const errorMessage = ref('')
const applications = ref<JoinApplication[]>([])


async function loadApplications() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const data = await getMyApplications()
    applications.value = data.items
  } catch (error) {
    if (error instanceof ApiRequestError) {
      if (error.code === 'UNAUTHENTICATED') {
        emit('navigate', '/login?reason=session')
        return
      }
      errorMessage.value = error.message
    } else {
      errorMessage.value = '申请列表加载失败，请稍后重试'
    }
  } finally {
    isLoading.value = false
  }
}


function statusTagType(status: string): 'warning' | 'success' | 'danger' | 'info' {
  switch (status) {
    case '待审核': return 'warning'
    case '已通过': return 'success'
    case '已拒绝': return 'danger'
    default: return 'info'
  }
}


function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN')
}


function goBack() {
  emit('navigate', '/student')
}


onMounted(() => {
  loadApplications()
})
</script>

<template>
  <div class="applications-view">
    <el-page-header @back="goBack">
      <template #content>
        <span>我的入社申请</span>
      </template>
    </el-page-header>

    <div v-if="isLoading" class="loading-container">
      <el-skeleton :rows="4" animated />
    </div>

    <div v-else-if="errorMessage" class="error-container">
      <el-result icon="error" :title="errorMessage">
        <template #extra>
          <el-button type="primary" @click="loadApplications">重新加载</el-button>
          <el-button @click="goBack">返回个人中心</el-button>
        </template>
      </el-result>
    </div>

    <div v-else-if="applications.length === 0" class="empty-container">
      <el-empty description="暂无入社申请记录" />
      <el-button type="primary" @click="emit('navigate', '/student/clubs')">
        浏览社团
      </el-button>
    </div>

    <div v-else class="application-list">
      <el-card
        v-for="app in applications"
        :key="app.id"
        class="application-card"
        shadow="hover"
      >
        <template #header>
          <div class="card-header">
            <span class="card-title">{{ app.recruitment.title }}</span>
            <el-tag :type="statusTagType(app.status)" size="small">
              {{ app.status }}
            </el-tag>
          </div>
        </template>

        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="目标社团">
            {{ app.club.name }}
          </el-descriptions-item>
          <el-descriptions-item label="申请理由">
            {{ app.reason }}
          </el-descriptions-item>
          <el-descriptions-item label="申请时间">
            {{ formatTime(app.applied_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="提交时姓名">
            {{ app.applicant_name_snapshot }}
          </el-descriptions-item>
          <el-descriptions-item label="提交时专业班级">
            {{ app.applicant_major_class_snapshot }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.applications-view {
  max-width: 700px;
  margin: 0 auto;
  padding: 24px 16px;
}

.loading-container,
.error-container,
.empty-container {
  margin-top: 48px;
  text-align: center;
}

.empty-container .el-button {
  margin-top: 16px;
}

.application-list {
  margin-top: 24px;
}

.application-card {
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}
</style>
