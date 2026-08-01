<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { ApiRequestError } from '../api/auth'
import { getMyFeedbacks } from '../api/clubs'
import type { Feedback } from '../types/club'


const emit = defineEmits<{
  navigate: [path: string]
}>()

const isLoading = ref(true)
const errorMessage = ref('')
const feedbacks = ref<Feedback[]>([])

async function loadFeedbacks() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const data = await getMyFeedbacks()
    feedbacks.value = data.items
  } catch (error) {
    if (error instanceof ApiRequestError) {
      if (error.code === 'UNAUTHENTICATED') {
        emit('navigate', '/login?reason=session')
        return
      }
      errorMessage.value = error.message
    } else {
      errorMessage.value = '反馈列表加载失败，请稍后重试'
    }
  } finally {
    isLoading.value = false
  }
}


function goBack() {
  emit('navigate', '/student')
}


function formatDate(isoString: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(isoString))
}


onMounted(() => {
  loadFeedbacks()
})
</script>

<template>
  <div class="feedbacks-view">
    <el-page-header @back="goBack">
      <template #content>
        <span>我的反馈</span>
      </template>
    </el-page-header>

    <div v-if="isLoading" class="loading-container">
      <el-skeleton :rows="4" animated />
    </div>

    <div v-else-if="errorMessage" class="error-container">
      <el-result icon="error" :title="errorMessage">
        <template #extra>
          <el-button type="primary" @click="loadFeedbacks">重新加载</el-button>
          <el-button @click="goBack">返回个人中心</el-button>
        </template>
      </el-result>
    </div>

    <div v-else-if="feedbacks.length === 0" class="empty-container">
      <el-empty description="暂无反馈">
        <template #extra>
          <el-button @click="goBack">返回个人中心</el-button>
        </template>
      </el-empty>
    </div>

    <div v-else class="feedback-list">
      <div
        v-for="feedback in feedbacks"
        :key="feedback.id"
        class="feedback-item"
      >
        <div class="fb-header">
          <span class="fb-club-name">{{ feedback.club.name }}</span>
          <el-tag
            :type="feedback.status === '已处理' ? 'success' : 'warning'"
            size="small"
          >
            {{ feedback.status }}
          </el-tag>
        </div>

        <p class="fb-content">{{ feedback.content }}</p>

        <p v-if="feedback.processing_note" class="fb-note">
          <span class="fb-note-label">处理说明：</span>
          {{ feedback.processing_note }}
        </p>

        <div class="fb-meta">
          <span class="fb-time">{{ formatDate(feedback.submitted_at) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.feedbacks-view {
  max-width: 650px;
  margin: 0 auto;
  padding: 24px 16px;
}

.loading-container,
.error-container,
.empty-container {
  margin-top: 48px;
  text-align: center;
}

.feedback-list {
  margin-top: 24px;
}

.feedback-item {
  padding: 16px;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  margin-bottom: 12px;
}

.fb-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.fb-club-name {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.fb-content {
  color: #606266;
  line-height: 1.7;
  margin: 0 0 10px;
  white-space: pre-wrap;
}

.fb-note {
  background: #f5f7fa;
  border-left: 3px solid #409eff;
  padding: 10px 12px;
  margin: 0 0 10px;
  color: #606266;
  line-height: 1.6;
  border-radius: 0 4px 4px 0;
  font-size: 14px;
  white-space: pre-wrap;
}

.fb-note-label {
  font-weight: 600;
  color: #409eff;
}

.fb-meta {
  display: flex;
  justify-content: flex-end;
}

.fb-time {
  font-size: 12px;
  color: #c0c4cc;
}
</style>
