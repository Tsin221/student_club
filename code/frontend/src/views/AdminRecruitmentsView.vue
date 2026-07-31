<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { ApiRequestError } from '../api/auth'
import { getAdminRecruitments } from '../api/clubs'
import type { Recruitment } from '../types/club'


const emit = defineEmits<{
  navigate: [path: string]
}>()

const isLoading = ref(true)
const errorMessage = ref('')
const recruitments = ref<Recruitment[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)


async function loadRecruitments() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const data = await getAdminRecruitments(currentPage.value, pageSize.value)
    recruitments.value = data.items
    total.value = data.total
  } catch (error) {
    if (error instanceof ApiRequestError) {
      if (error.code === 'UNAUTHENTICATED') {
        emit('navigate', '/login?reason=session')
        return
      }
      if (error.code === 'FORBIDDEN') {
        emit('navigate', '/student')
        return
      }
      errorMessage.value = error.message
    } else {
      errorMessage.value = '招新记录加载失败，请稍后重试'
    }
  } finally {
    isLoading.value = false
  }
}


function handlePageChange(page: number) {
  currentPage.value = page
  loadRecruitments()
}


function handleSizeChange(size: number) {
  pageSize.value = size
  currentPage.value = 1
  loadRecruitments()
}


function statusTagType(status: string): 'info' | 'success' | 'warning' | 'danger' {
  switch (status) {
    case '未开始': return 'info'
    case '进行中': return 'success'
    case '已满': return 'warning'
    case '已结束': return 'danger'
    default: return 'info'
  }
}


function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN')
}


onMounted(() => {
  loadRecruitments()
})
</script>

<template>
  <main class="admin-page">
    <header class="admin-header">
      <div class="brand-mark" aria-hidden="true">管</div>
      <div>
        <p class="eyebrow">校园社团智能管理系统</p>
        <p class="header-title">管理员工作台</p>
      </div>
    </header>

    <div class="admin-content">
      <section class="page-heading">
        <p class="section-kicker">招新管理</p>
        <h1>招新信息记录</h1>
        <p>查看平台上所有社团的全部招新历史记录。</p>
      </section>

      <div style="margin-bottom: 20px; display: flex; gap: 12px">
        <el-button @click="emit('navigate', '/admin/clubs')">
          社团管理
        </el-button>
        <el-button @click="emit('navigate', '/admin/memberships')">
          成员记录
        </el-button>
      </div>

    <div v-if="isLoading" class="loading-container">
      <el-skeleton :rows="6" animated />
    </div>

    <div v-else-if="errorMessage" class="error-container">
      <el-result icon="error" :title="errorMessage">
        <template #extra>
          <el-button type="primary" @click="loadRecruitments">重新加载</el-button>
        </template>
      </el-result>
    </div>

    <div v-else-if="recruitments.length === 0" class="empty-container">
      <el-empty description="暂无招新记录" />
    </div>

    <div v-else>
      <el-table
        :data="recruitments"
        border
        stripe
        style="width: 100%"
      >
        <el-table-column prop="id" label="ID" width="70" align="center" />
        <el-table-column prop="title" label="招新标题" min-width="160" show-overflow-tooltip />
        <el-table-column label="社团" width="140" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.club_id }}
          </template>
        </el-table-column>
        <el-table-column label="发布人" width="120">
          <template #default="{ row }">
            {{ row.publisher.username }}
          </template>
        </el-table-column>
        <el-table-column label="人数" width="100" align="center">
          <template #default="{ row }">
            {{ row.approved_count }} / {{ row.capacity }}
          </template>
        </el-table-column>
        <el-table-column label="展示状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.display_status)" size="small">
              {{ row.display_status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="发布时间" width="170">
          <template #default="{ row }">
            {{ formatTime(row.published_at) }}
          </template>
        </el-table-column>
        <el-table-column label="开始时间" width="170">
          <template #default="{ row }">
            {{ formatTime(row.start_time) }}
          </template>
        </el-table-column>
        <el-table-column label="结束时间" width="170">
          <template #default="{ row }">
            {{ formatTime(row.end_time) }}
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          background
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </div>
    </div>
  </main>
</template>

<style scoped>
.loading-container,
.error-container,
.empty-container {
  margin-top: 48px;
}

.pagination-container {
  margin-top: 16px;
  display: flex;
  justify-content: center;
}
</style>
