<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { ApiRequestError } from '../api/auth'
import { getMyNotifications } from '../api/applications'
import type { Notification } from '../types/club'


const emit = defineEmits<{
  navigate: [path: string]
}>()

const isLoading = ref(true)
const errorMessage = ref('')
const notifications = ref<Notification[]>([])


async function loadNotifications() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const data = await getMyNotifications()
    notifications.value = data.items
  } catch (error) {
    if (error instanceof ApiRequestError) {
      if (error.code === 'UNAUTHENTICATED') {
        emit('navigate', '/login?reason=session')
        return
      }
      errorMessage.value = error.message
    } else {
      errorMessage.value = '通知列表加载失败，请稍后重试'
    }
  } finally {
    isLoading.value = false
  }
}


function typeTagColor(type: string): string {
  switch (type) {
    case '有人回复了我的帖子': return '#409eff'
    case '我的举报已经处理': return '#e6a23c'
    case '我的入社申请已经审核': return '#67c23a'
    default: return '#909399'
  }
}


function goBack() {
  emit('navigate', '/student')
}


onMounted(() => {
  loadNotifications()
})
</script>

<template>
  <div class="notifications-view">
    <el-page-header @back="goBack">
      <template #content>
        <span>我的通知</span>
      </template>
    </el-page-header>

    <div v-if="isLoading" class="loading-container">
      <el-skeleton :rows="4" animated />
    </div>

    <div v-else-if="errorMessage" class="error-container">
      <el-result icon="error" :title="errorMessage">
        <template #extra>
          <el-button type="primary" @click="loadNotifications">重新加载</el-button>
          <el-button @click="goBack">返回个人中心</el-button>
        </template>
      </el-result>
    </div>

    <div v-else-if="notifications.length === 0" class="empty-container">
      <el-empty description="暂无通知" />
      <el-button @click="goBack">返回个人中心</el-button>
    </div>

    <div v-else class="notification-list">
      <div
        v-for="notif in notifications"
        :key="notif.id"
        class="notification-item"
      >
        <div class="notif-type">
          <el-tag :color="typeTagColor(notif.type)" effect="dark" size="small">
            {{ notif.type }}
          </el-tag>
        </div>
        <div class="notif-content">
          {{ notif.content }}
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.notifications-view {
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

.notification-list {
  margin-top: 24px;
}

.notification-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  margin-bottom: 10px;
}

.notif-type {
  flex-shrink: 0;
  padding-top: 2px;
}

.notif-content {
  flex: 1;
  font-size: 14px;
  color: #303133;
  line-height: 1.6;
}
</style>
