<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { ApiRequestError } from '../api/auth'
import { getAdminApplications } from '../api/applications'
import type { JoinApplication } from '../types/club'


const emit = defineEmits<{
  navigate: [path: string]
}>()

const isLoading = ref(true)
const errorMessage = ref('')
const applications = ref<JoinApplication[]>([])
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)


async function loadApplications() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const data = await getAdminApplications(currentPage.value, pageSize.value)
    applications.value = data.items
    total.value = data.total
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


function onPageChange(page: number) {
  currentPage.value = page
  loadApplications()
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
  emit('navigate', '/admin/users')
}


onMounted(() => {
  loadApplications()
})
</script>

<template>
  <main class="student-page">
    <header class="admin-header">
      <div class="brand-mark" aria-hidden="true">社</div>
      <div>
        <p class="eyebrow">校园社团智能管理系统</p>
        <p class="header-title">入社申请记录</p>
      </div>
    </header>

    <div class="student-content">
      <section class="page-heading">
        <p class="section-kicker">管理员工作台</p>
        <h1>入社申请记录</h1>
        <p>
          <el-button
            text
            size="small"
            @click="emit('navigate', '/admin/users')"
          >
            ← 返回工作台
          </el-button>
        </p>
      </section>

      <div v-if="isLoading" class="loading-container">
        <el-skeleton :rows="5" animated />
      </div>

      <div v-else-if="errorMessage" class="error-container">
        <el-result icon="error" :title="errorMessage">
          <template #extra>
            <el-button type="primary" @click="loadApplications">重新加载</el-button>
          </template>
        </el-result>
      </div>

      <div v-else-if="applications.length === 0" class="empty-container">
        <el-empty description="暂无入社申请记录" />
      </div>

      <el-card v-else class="data-card" shadow="never">
        <el-table :data="applications" stripe>
          <el-table-column label="申请人" width="100">
            <template #default="{ row }">
              {{ row.applicant_name_snapshot }}
            </template>
          </el-table-column>
          <el-table-column label="专业班级" prop="applicant_major_class_snapshot" width="130" />
          <el-table-column label="目标社团" width="120">
            <template #default="{ row }">
              {{ row.club.name }}
            </template>
          </el-table-column>
          <el-table-column label="招新" min-width="150">
            <template #default="{ row }">
              {{ row.recruitment.title }}
            </template>
          </el-table-column>
          <el-table-column label="申请理由" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.reason }}
            </template>
          </el-table-column>
          <el-table-column label="申请时间" width="170">
            <template #default="{ row }">
              {{ formatTime(row.applied_at) }}
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)" size="small">
                {{ row.status }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-container">
          <el-pagination
            :current-page="currentPage"
            :page-size="pageSize"
            :total="total"
            layout="total, prev, pager, next"
            @current-change="onPageChange"
          />
        </div>
      </el-card>
    </div>
  </main>
</template>

<style scoped>
.student-page {
  min-height: 100vh;
  background: #f5f7fa;
}

.admin-header {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 32px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
}

.brand-mark {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #409eff, #337ecc);
  color: #fff;
  font-size: 22px;
  font-weight: 700;
  border-radius: 10px;
}

.eyebrow {
  margin: 0;
  font-size: 12px;
  color: #909399;
  letter-spacing: 1px;
}

.header-title {
  margin: 2px 0 0;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.student-content {
  max-width: 960px;
  margin: 0 auto;
  padding: 32px 16px;
}

.page-heading {
  margin-bottom: 24px;
}

.section-kicker {
  margin: 0;
  font-size: 13px;
  color: #909399;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.page-heading h1 {
  margin: 4px 0 8px;
  font-size: 22px;
  font-weight: 700;
  color: #303133;
}

.loading-container,
.error-container,
.empty-container {
  margin-top: 48px;
  text-align: center;
}

.data-card {
  margin-bottom: 20px;
}

.pagination-container {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
