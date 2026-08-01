<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { ApiRequestError } from '../api/auth'
import { getAdminEvaluations } from '../api/clubs'
import type { ClubEvaluation } from '../types/club'


const emit = defineEmits<{
  navigate: [path: string]
}>()

const isLoading = ref(true)
const errorMessage = ref('')
const evaluations = ref<ClubEvaluation[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)


async function loadEvaluations() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const data = await getAdminEvaluations(page.value, pageSize.value)
    evaluations.value = data.items
    total.value = data.total
  } catch (error) {
    if (error instanceof ApiRequestError) {
      if (error.code === 'UNAUTHENTICATED') {
        emit('navigate', '/login?reason=session')
        return
      }
      errorMessage.value = error.message
    } else {
      errorMessage.value = '评价列表加载失败，请稍后重试'
    }
  } finally {
    isLoading.value = false
  }
}


function handlePageChange(newPage: number) {
  page.value = newPage
  loadEvaluations()
}


function starsLabel(rating: number): string {
  return '★'.repeat(rating) + '☆'.repeat(5 - rating)
}


function goBack() {
  emit('navigate', '/admin/users')
}


onMounted(() => {
  loadEvaluations()
})
</script>

<template>
  <main class="admin-page">
    <header class="admin-header">
      <div class="brand-mark" aria-hidden="true">社</div>
      <div>
        <p class="eyebrow">校园社团智能管理系统</p>
        <p class="header-title">全部评价记录</p>
      </div>
    </header>

    <div class="admin-content">
      <div v-if="isLoading" v-loading="true" style="min-height: 200px" />

      <el-alert
        v-else-if="errorMessage"
        type="error"
        :title="errorMessage"
        :closable="false"
        show-icon
        class="form-alert"
      />

      <template v-else>
        <div v-if="evaluations.length === 0">
          <el-empty description="暂无评价记录" />
        </div>

        <div v-else>
          <el-table
            :data="evaluations"
            border
            stripe
            style="width: 100%"
            :default-sort="{ prop: 'id', order: 'descending' }"
          >
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column label="评价用户" width="150">
              <template #default="scope">
                {{ scope.row.user.username }}
              </template>
            </el-table-column>
            <el-table-column label="社团" width="180">
              <template #default="scope">
                {{ scope.row.club.name }}
              </template>
            </el-table-column>
            <el-table-column label="评分" width="150">
              <template #default="scope">
                <span class="stars-display">{{ starsLabel(scope.row.rating) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="评价内容">
              <template #default="scope">
                <span v-if="scope.row.comment">{{ scope.row.comment }}</span>
                <span v-else style="color: #c0c4cc; font-style: italic">（无文字评价）</span>
              </template>
            </el-table-column>
          </el-table>

          <div style="margin-top: 16px; text-align: right">
            <el-pagination
              v-model:current-page="page"
              :page-size="pageSize"
              :total="total"
              layout="total, prev, pager, next"
              @current-change="handlePageChange"
            />
          </div>
        </div>
      </template>
    </div>
  </main>
</template>

<style scoped>
.stars-display {
  color: #e6a23c;
  letter-spacing: 2px;
  font-size: 16px;
}
</style>
