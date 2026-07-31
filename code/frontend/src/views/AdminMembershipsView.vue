<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { ApiRequestError } from '../api/auth'
import { getAdminMemberships } from '../api/clubs'
import type { ClubMembership } from '../types/club'


const emit = defineEmits<{
  navigate: [path: string]
}>()

const isLoading = ref(true)
const errorMessage = ref('')
const memberships = ref<ClubMembership[]>([])
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)


async function loadData() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const data = await getAdminMemberships(currentPage.value, pageSize.value)
    memberships.value = data.items
    total.value = data.total
  } catch (error) {
    if (error instanceof ApiRequestError) {
      if (error.code === 'UNAUTHENTICATED') {
        emit('navigate', '/login?reason=session')
        return
      }
      if (error.code === 'FORBIDDEN') {
        emit('navigate', '/login')
        return
      }
      errorMessage.value = error.message
    } else {
      errorMessage.value = '成员关系列表加载失败'
    }
  } finally {
    isLoading.value = false
  }
}


function handlePageChange(page: number) {
  currentPage.value = page
  loadData()
}


function handleSizeChange(size: number) {
  pageSize.value = size
  currentPage.value = 1
  loadData()
}


function statusTagType(status: string): 'success' | 'info' | 'danger' {
  if (status === 'active') return 'success'
  if (status === 'exited') return 'info'
  return 'danger'
}


function statusLabel(status: string): string {
  if (status === 'active') return '在社'
  if (status === 'exited') return '已退出'
  return '已移除'
}


function roleLabel(role: string): string {
  return role === 'leader' ? '负责人' : '普通成员'
}


onMounted(() => {
  loadData()
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
        <p class="section-kicker">成员管理</p>
        <h1>全部成员关系</h1>
        <p>查看平台所有学生与社团的成员关系记录。</p>
      </section>

      <el-alert
        v-if="errorMessage"
        type="error"
        :title="errorMessage"
        :closable="false"
        show-icon
        class="form-alert"
      />

      <el-card
        v-loading="isLoading"
        class="data-card"
        shadow="never"
        aria-live="polite"
      >
        <template v-if="!errorMessage && memberships.length === 0 && !isLoading">
          <el-empty description="暂无成员关系记录" />
        </template>

        <template v-else-if="!errorMessage">
          <el-table :data="memberships" stripe>
            <el-table-column label="ID" prop="id" width="70" />
            <el-table-column label="用户名" prop="user.username" width="120" />
            <el-table-column label="姓名" prop="user.name" width="100" />
            <el-table-column label="社团名称" prop="club.name" min-width="140" />
            <el-table-column label="社团状态" width="90">
              <template #default="{ row }">
                <el-tag
                  :type="row.club.status === 'normal' ? 'success' : 'info'"
                  effect="light"
                  size="small"
                >
                  {{ row.club.status === 'normal' ? '正常' : '已注销' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="成员状态" width="90">
              <template #default="{ row }">
                <el-tag
                  :type="statusTagType(row.member_status)"
                  effect="light"
                  size="small"
                >
                  {{ statusLabel(row.member_status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="社团身份" width="90">
              <template #default="{ row }">
                <el-tag
                  :type="row.club_role === 'leader' ? 'warning' : 'info'"
                  effect="light"
                  size="small"
                >
                  {{ roleLabel(row.club_role) }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>

          <div class="pagination-wrap">
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
        </template>
      </el-card>
    </div>
  </main>
</template>
