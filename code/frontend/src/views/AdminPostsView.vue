<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { ApiRequestError } from '../api/auth'
import { deletePost, getAdminPosts } from '../api/clubs'
import type { Post } from '../types/club'


const emit = defineEmits<{
  navigate: [path: string]
}>()

const isLoading = ref(true)
const errorMessage = ref('')
const posts = ref<Post[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const deletingPostId = ref<number | null>(null)


async function loadPosts() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const data = await getAdminPosts(page.value, pageSize.value)
    posts.value = data.items
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


async function handleDelete(post: Post) {
  deletingPostId.value = post.id
  try {
    await deletePost(post.id)
    ElMessage.success('帖子已删除')
    await loadPosts()
  } catch (error) {
    ElMessage.error(
      error instanceof ApiRequestError ? error.message : '删除失败',
    )
  } finally {
    deletingPostId.value = null
  }
}


function handlePageChange(newPage: number) {
  page.value = newPage
  loadPosts()
}


onMounted(() => {
  loadPosts()
})
</script>

<template>
  <main class="admin-page">
    <header class="admin-header">
      <div class="brand-mark" aria-hidden="true">社</div>
      <div>
        <p class="eyebrow">校园社团智能管理系统</p>
        <p class="header-title">全部帖子</p>
      </div>
    </header>

    <section class="admin-content">
      <p class="admin-intro">
        查看平台全部帖子（含已删除），管理员可逻辑删除正常帖子。
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
          v-if="posts.length === 0"
          description="暂无帖子"
          :image-size="60"
        />

        <el-table v-else :data="posts" stripe>
          <el-table-column label="ID" prop="id" width="60" />
          <el-table-column label="标题" prop="title" min-width="160" />
          <el-table-column label="作者" width="120">
            <template #default="{ row }">
              {{ row.author.username }}
            </template>
          </el-table-column>
          <el-table-column label="社团" width="100">
            <template #default="{ row }">
              <span style="font-size: 13px; color: #606266">#{{ row.club_id }}</span>
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
                :loading="deletingPostId === row.id"
                @click="handleDelete(row as Post)"
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
