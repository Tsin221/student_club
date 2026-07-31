<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { ApiRequestError } from '../api/auth'
import { getAdminAnnouncements, getClubDetail } from '../api/clubs'
import type { Announcement, Club } from '../types/club'


const emit = defineEmits<{
  navigate: [path: string]
}>()

//从 URL 解析 clubId
function parseClubId(): number {
  const match = window.location.pathname.match(/^\/admin\/clubs\/(\d+)\/announcements/)
  return match ? Number(match[1]) : 0
}

const clubId = parseClubId()

// ── 社团信息 ──────────────────────────────────────────────

const club = ref<Club | null>(null)
const isLoading = ref(true)
const errorMessage = ref('')

// ── 公告列表 ──────────────────────────────────────────────

const announcements = ref<Announcement[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)


async function loadClub() {
  if (!clubId) {
    errorMessage.value = '无效的社团 ID'
    isLoading.value = false
    return
  }
  try {
    club.value = await getClubDetail(clubId)
  } catch (error) {
    if (error instanceof ApiRequestError) {
      if (error.code === 'UNAUTHENTICATED') {
        emit('navigate', '/login?reason=session')
        return
      }
      if (error.code === 'FORBIDDEN') {
        emit('navigate', '/admin/clubs')
        return
      }
      errorMessage.value = error.message
    } else {
      errorMessage.value = '社团信息加载失败'
    }
    isLoading.value = false
  }
}


async function loadAnnouncements() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const data = await getAdminAnnouncements(clubId, currentPage.value, pageSize.value)
    announcements.value = data.items
    total.value = data.total
  } catch (error) {
    if (error instanceof ApiRequestError) {
      if (error.code === 'UNAUTHENTICATED') {
        emit('navigate', '/login?reason=session')
        return
      }
      if (error.code === 'FORBIDDEN') {
        emit('navigate', '/admin/clubs')
        return
      }
      errorMessage.value = error.message
    } else {
      errorMessage.value = '公告列表加载失败，请稍后重试'
    }
  } finally {
    isLoading.value = false
  }
}


function handlePageChange(page: number) {
  currentPage.value = page
  loadAnnouncements()
}


function handleSizeChange(size: number) {
  pageSize.value = size
  currentPage.value = 1
  loadAnnouncements()
}


function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN')
}


onMounted(async () => {
  await loadClub()
  if (club.value) {
    loadAnnouncements()
  }
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
        <p class="section-kicker">社团公告历史</p>
        <h1>{{ club?.name ?? '公告历史' }}</h1>
        <p>
          <el-tag
            :type="club?.status === 'normal' ? 'success' : 'info'"
            effect="light"
            size="small"
          >
            {{ club?.status === 'normal' ? '正常' : '已注销' }}
          </el-tag>
          <el-button
            text
            size="small"
            style="margin-left: 12px"
            @click="emit('navigate', '/admin/clubs')"
          >
            ← 返回社团列表
          </el-button>
        </p>
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
      >
        <template v-if="!errorMessage && announcements.length === 0 && !isLoading">
          <el-empty description="暂无公告记录" :image-size="60" />
        </template>

        <template v-else-if="!errorMessage">
          <el-table :data="announcements" stripe>
            <el-table-column label="标题" min-width="160">
              <template #default="{ row }">
                <div style="display: flex; align-items: center; gap: 8px">
                  <el-tag
                    v-if="row.is_pinned && row.status === '正常'"
                    type="warning"
                    size="small"
                    effect="light"
                  >
                    置顶
                  </el-tag>
                  <span>{{ row.title }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag
                  :type="row.status === '正常' ? 'success' : 'info'"
                  effect="light"
                  size="small"
                >
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="发布人" width="120">
              <template #default="{ row }">
                {{ row.publisher.username }}
              </template>
            </el-table-column>
            <el-table-column label="发布时间" width="170">
              <template #default="{ row }">
                <span style="font-size: 13px; color: #909399">
                  {{ formatDateTime(row.published_at) }}
                </span>
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
