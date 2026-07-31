<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { ApiRequestError } from '../api/auth'
import { approveApplication, getLeaderApplications, rejectApplication } from '../api/applications'
import type { JoinApplication } from '../types/club'


const emit = defineEmits<{
  navigate: [path: string]
}>()

const clubId = computed(() => {
  const match = window.location.pathname.match(/^\/leader\/clubs\/(\d+)\/applications/)
  return match ? Number(match[1]) : 0
})

const isLoading = ref(true)
const errorMessage = ref('')
const applications = ref<JoinApplication[]>([])


async function loadApplications() {
  if (!clubId.value) {
    errorMessage.value = '无效的社团 ID'
    isLoading.value = false
    return
  }

  isLoading.value = true
  errorMessage.value = ''
  try {
    const data = await getLeaderApplications(clubId.value)
    applications.value = data.items
  } catch (error) {
    if (error instanceof ApiRequestError) {
      if (error.code === 'UNAUTHENTICATED') {
        emit('navigate', '/login?reason=session')
        return
      }
      if (error.code === 'NOT_CLUB_LEADER') {
        errorMessage.value = '你不是该社团的负责人'
        isLoading.value = false
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


async function handleApprove(app: JoinApplication) {
  try {
    await ElMessageBox.confirm(
      `确定要通过 ${app.applicant_name_snapshot}（${app.applicant_major_class_snapshot}）的入社申请吗？`,
      '确认通过申请',
      { confirmButtonText: '确定通过', cancelButtonText: '取消', type: 'success' },
    )
  } catch {
    return
  }

  try {
    await approveApplication(app.id)
    ElMessage.success('申请已通过')
    await loadApplications()
  } catch (error) {
    if (error instanceof ApiRequestError) {
      ElMessage.error(error.message)
    } else {
      ElMessage.error('操作失败，请稍后重试')
    }
  }
}


async function handleReject(app: JoinApplication) {
  try {
    await ElMessageBox.confirm(
      `确定要拒绝 ${app.applicant_name_snapshot}（${app.applicant_major_class_snapshot}）的入社申请吗？`,
      '确认拒绝申请',
      { confirmButtonText: '确定拒绝', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }

  try {
    await rejectApplication(app.id)
    ElMessage.success('申请已拒绝')
    await loadApplications()
  } catch (error) {
    if (error instanceof ApiRequestError) {
      ElMessage.error(error.message)
    } else {
      ElMessage.error('操作失败，请稍后重试')
    }
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
  emit('navigate', `/leader/clubs/${clubId.value}`)
}


onMounted(() => {
  loadApplications()
})
</script>

<template>
  <div class="leader-applications-view">
    <el-page-header @back="goBack">
      <template #content>
        <span>入社申请审核</span>
      </template>
    </el-page-header>

    <div v-if="isLoading" class="loading-container">
      <el-skeleton :rows="4" animated />
    </div>

    <div v-else-if="errorMessage" class="error-container">
      <el-result icon="error" :title="errorMessage">
        <template #extra>
          <el-button type="primary" @click="loadApplications">重新加载</el-button>
          <el-button @click="goBack">返回社团管理</el-button>
        </template>
      </el-result>
    </div>

    <div v-else-if="applications.length === 0" class="empty-container">
      <el-empty description="暂无入社申请" />
      <el-button @click="goBack">返回社团管理</el-button>
    </div>

    <div v-else class="application-list">
      <el-card
        v-for="app in applications"
        :key="app.id"
        class="application-card"
        :class="{ 'is-pending': app.status === '待审核' }"
        shadow="hover"
      >
        <template #header>
          <div class="card-header">
            <span class="card-title">{{ app.applicant_name_snapshot }}</span>
            <div class="card-header-right">
              <span class="recruitment-label">{{ app.recruitment.title }}</span>
              <el-tag :type="statusTagType(app.status)" size="small">
                {{ app.status }}
              </el-tag>
            </div>
          </div>
        </template>

        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="专业班级">
            {{ app.applicant_major_class_snapshot }}
          </el-descriptions-item>
          <el-descriptions-item label="申请理由">
            {{ app.reason }}
          </el-descriptions-item>
          <el-descriptions-item label="申请时间">
            {{ formatTime(app.applied_at) }}
          </el-descriptions-item>
        </el-descriptions>

        <div v-if="app.status === '待审核'" class="card-actions">
          <el-button type="success" size="small" @click="handleApprove(app)">
            通过
          </el-button>
          <el-button type="danger" size="small" @click="handleReject(app)">
            拒绝
          </el-button>
        </div>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.leader-applications-view {
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

.application-list {
  margin-top: 24px;
}

.application-card {
  margin-bottom: 16px;
}

.application-card.is-pending {
  border-left: 3px solid var(--el-color-warning);
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

.card-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.recruitment-label {
  font-size: 13px;
  color: #909399;
}

.card-actions {
  margin-top: 12px;
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
</style>
