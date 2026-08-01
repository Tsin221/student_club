<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { ApiRequestError } from '../api/auth'
import { deleteReply, getAdminReplies } from '../api/clubs'
import type { Reply } from '../types/club'


const emit = defineEmits<{
  navigate: [path: string]
}>()

const isLoading = ref(true)
const errorMessage = ref('')
const replies = ref<Reply[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const deletingReplyId = ref<number | null>(null)


async function loadReplies() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const data = await getAdminReplies(page.value, pageSize.value)
    replies.value = data.items
    total.value = data.total
  } catch (error) {
    if (error instanceof ApiRequestError) {
      if (error.code === 'UNAUTHENTICATED' || error.code === 'FORBIDDEN') {
        emit('navigate', '/login?reason=session')
        return
      }
      errorMessage.value = error.message
    } else {
      errorMessage.value = '加载失败，请稍后重试'
    }
  } finally {
    isLoading.value = false
  }
}


async function handleDelete(reply: Reply) {
  deletingReplyId.value = reply.id
  try {
    await deleteReply(reply.id)
    ElMessage.success('回复已删除')
    await loadReplies()
  } catch (error) {
    ElMessage.error(
      error instanceof ApiRequestError ? error.message : '删除失败',
    )
  } finally {
    deletingReplyId.value = null
  }
}


function handlePageChange(newPage: number) {
  page.value = newPage
  loadReplies()
}


function truncateContent(content: string, maxLength = 80): string {
  if (content.length <= maxLength) return content
  return content.slice(0, maxLength) + '…'
}


onMounted(() => {
  loadReplies()
})
</script>

<template>
  <main class="admin-page">
    <header class="admin-header">
      <div class="brand-mark" aria-hidden="true">社</div>
      <div>
        <p class="eyebrow">校园社团智能管理系统</p>
        <p class="header-title">全部回复</p>
      </div>
    </header>

    <section class="admin-content">
      <p class="admin-intro">
        查看平台全部回复（含已删除），管理员可逻辑删除正常回复。
      </p>

      <div class="toolbar">
        <el-button @click="emit('navigate', '/admin/users')">
          返回管理面板
        </el-button>
      </div>

      <div v-if="isLoading" v-loading="true" style="min-height: 200px" />

      <el-alert
        v-else-if="errorMessage"
        :title="errorMessage"
        type="error"
        show-icon
        :closable="false"
        style="margin-bottom: 16px"
      />

      <template v-else>
        <el-empty
          v-if="replies.length === 0"
          description="暂无回复"
          :image-size="60"
        />

        <el-table v-else :data="replies" stripe>
          <el-table-column label="ID" prop="id" width="60" />
          <el-table-column label="内容" min-width="200">
            <template #default="{ row }">
              {{ truncateContent(row.content) }}
            </template>
          </el-table-column>
          <el-table-column label="作者" width="120">
            <template #default="{ row }">
              {{ row.author.username }}
            </template>
          </el-table-column>
          <el-table-column label="所属帖子" width="80">
            <template #default="{ row }">
              #{{ row.post_id }}
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
          <el-table-column label="操作" width="80">
            <template #default="{ row }">
              <el-button
                v-if="row.status === '正常'"
                type="danger"
                size="small"
                text
                :loading="deletingReplyId === row.id"
                @click="handleDelete(row as Reply)"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-pagination
          v-if="total > pageSize"
          style="margin-top: 20px; justify-content: center"
          layout="prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="page"
          @current-change="handlePageChange"
        />
      </template>
    </section>
  </main>
</template>
