<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'

import { ApiRequestError } from '../api/auth'
import { getLeaderReports, processReport } from '../api/clubs'
import type { ContentReport } from '../types/club'


const emit = defineEmits<{
  navigate: [path: string]
}>()

const clubId = computed(() => {
  const match = window.location.pathname.match(/^\/leader\/clubs\/(\d+)\/reports/)
  return match ? Number(match[1]) : 0
})

// ── 列表状态 ──────────────────────────────────────────────

const isLoading = ref(true)
const errorMessage = ref('')
const reports = ref<ContentReport[]>([])
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

// ── 处理弹窗 ──────────────────────────────────────────────

const dialogVisible = ref(false)
const isProcessing = ref(false)
const processingReport = ref<ContentReport | null>(null)
const formRef = ref<FormInstance>()

const form = reactive({
  status: '已采纳' as '已采纳' | '未采纳',
  processing_note: '',
  delete_target: false,
})

const formRules: FormRules<typeof form> = {
  status: [
    { required: true, message: '请选择处理结论', trigger: 'change' },
  ],
  processing_note: [
    { required: true, message: '请输入处理说明', trigger: 'blur' },
  ],
}


function statusTagType(status: string): 'warning' | 'success' | 'danger' {
  if (status === '待处理') return 'warning'
  if (status === '已采纳') return 'success'
  return 'danger'
}


function openProcessDialog(report: ContentReport) {
  processingReport.value = report
  form.status = '已采纳'
  form.processing_note = ''
  form.delete_target = false
  dialogVisible.value = true
}


async function handleProcess() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  if (!processingReport.value) return

  isProcessing.value = true
  try {
    await processReport(processingReport.value.id, {
      status: form.status,
      processing_note: form.processing_note.trim(),
      delete_target: form.delete_target,
    })
    dialogVisible.value = false
    ElMessage.success('举报处理成功')
    await loadReports()
  } catch (error) {
    if (error instanceof ApiRequestError) {
      if (error.code === 'UNAUTHENTICATED') {
        emit('navigate', '/login?reason=session')
        return
      }
      ElMessage.error(error.message)
    } else {
      ElMessage.error('处理失败，请稍后重试')
    }
  } finally {
    isProcessing.value = false
  }
}


async function loadReports() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const data = await getLeaderReports(clubId.value, currentPage.value, pageSize.value)
    reports.value = data.items
    total.value = data.total
  } catch (error) {
    if (error instanceof ApiRequestError) {
      if (error.code === 'UNAUTHENTICATED') {
        emit('navigate', '/login?reason=session')
        return
      }
      if (error.code === 'NOT_CLUB_LEADER' || error.code === 'CLUB_CANCELLED') {
        emit('navigate', '/student')
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


function handlePageChange(page: number) {
  currentPage.value = page
  loadReports()
}


function goBack() {
  emit('navigate', `/leader/clubs/${clubId.value}`)
}


function castReport(row: unknown): ContentReport {
  return row as ContentReport
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


function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text
  return text.substring(0, maxLen) + '…'
}


onMounted(() => {
  loadReports()
})
</script>

<template>
  <div class="leader-reports-view">
    <el-page-header @back="goBack">
      <template #content>
        <span>内容举报管理</span>
      </template>
    </el-page-header>

    <el-card v-loading="isLoading" style="margin-top: 16px">
      <!-- 错误态 -->
      <el-result
        v-if="errorMessage && !isLoading"
        icon="error"
        :title="errorMessage"
      >
        <template #extra>
          <el-button type="primary" @click="loadReports">重试</el-button>
          <el-button @click="goBack">返回</el-button>
        </template>
      </el-result>

      <!-- 空状态 -->
      <el-empty
        v-else-if="!isLoading && reports.length === 0"
        description="暂无举报记录"
      />

      <!-- 数据表格 -->
      <template v-else-if="!isLoading">
        <el-table :data="reports" stripe style="width: 100%">
          <el-table-column prop="reporter.username" label="举报人" width="120" />
          <el-table-column label="举报原因" min-width="180">
            <template #default="{ row }">
              <span>{{ truncate(row.reason, 60) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="举报目标" min-width="200">
            <template #default="{ row }">
              <template v-if="(row as ContentReport).target">
                <div v-if="row.post_id" style="font-size: 13px">
                  <span style="color: #909399">[帖子]</span>
                  {{ row.target.title ? truncate(row.target.title, 30) : '(无标题)' }}
                  <el-tag
                    :type="row.target.status === '正常' ? 'info' : 'danger'"
                    size="small"
                    style="margin-left: 6px"
                  >
                    {{ row.target.status }}
                  </el-tag>
                </div>
                <div v-else style="font-size: 13px">
                  <span style="color: #909399">[回复]</span>
                  {{ truncate(row.target.content, 30) }}
                  <el-tag
                    :type="row.target.status === '正常' ? 'info' : 'danger'"
                    size="small"
                    style="margin-left: 6px"
                  >
                    {{ row.target.status }}
                  </el-tag>
                </div>
              </template>
              <span v-else style="color: #909399">目标已不可见</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)">
                {{ row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="处理说明" min-width="150">
            <template #default="{ row }">
              <span v-if="row.processing_note">{{ truncate(row.processing_note, 40) }}</span>
              <span v-else style="color: #c0c4cc">—</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button
                v-if="row.status === '待处理'"
                type="primary"
                size="small"
                link
                @click="openProcessDialog(castReport(row))"
              >
                处理
              </el-button>
              <span v-else style="color: #c0c4cc">—</span>
            </template>
          </el-table-column>
        </el-table>

        <el-pagination
          v-if="total > pageSize"
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          style="margin-top: 16px; justify-content: flex-end"
          @current-change="handlePageChange"
        />
      </template>
    </el-card>

    <!-- 处理对话框 -->
    <el-dialog
      v-model="dialogVisible"
      title="处理举报"
      width="520px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-width="100px"
      >
        <el-form-item label="举报人">
          <span>{{ processingReport?.reporter.username }}</span>
        </el-form-item>
        <el-form-item label="举报原因">
          <p style="margin: 0; white-space: pre-wrap">{{ processingReport?.reason }}</p>
        </el-form-item>
        <el-form-item label="目标内容">
          <template v-if="processingReport?.target">
            <p v-if="processingReport.post_id" style="margin: 0">
              [帖子] {{ processingReport.target.title }}
            </p>
            <p v-else style="margin: 0">
              [回复] {{ processingReport.target?.content }}
            </p>
          </template>
          <span v-else style="color: #909399">目标已不可见</span>
        </el-form-item>
        <el-form-item label="处理结论" prop="status">
          <el-radio-group v-model="form.status">
            <el-radio value="已采纳">已采纳</el-radio>
            <el-radio value="未采纳">未采纳</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="处理说明" prop="processing_note">
          <el-input
            v-model="form.processing_note"
            type="textarea"
            :rows="3"
            maxlength="1000"
            show-word-limit
            placeholder="请填写处理说明（必填）"
          />
        </el-form-item>
        <el-form-item v-if="form.status === '已采纳'" label="删除目标">
          <el-checkbox v-model="form.delete_target">
            同时删除被举报的内容
          </el-checkbox>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="isProcessing"
          @click="handleProcess"
        >
          确认处理
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.leader-reports-view {
  max-width: 960px;
  margin: 24px auto;
  padding: 0 16px;
}
</style>
