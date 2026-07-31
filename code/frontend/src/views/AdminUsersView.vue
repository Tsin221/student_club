<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  ElMessage,
  ElMessageBox,
  type FormInstance,
  type FormRules,
} from 'element-plus'

import {
  ApiRequestError,
  getAdminUsers,
  resetPassword,
} from '../api/auth'
import type { SelfUser } from '../types/user'


const emit = defineEmits<{
  navigate: [path: string]
}>()

// ── 列表状态 ──────────────────────────────────────────────

const isLoading = ref(true)
const errorMessage = ref('')
const users = ref<SelfUser[]>([])
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

// ── 密码重置弹窗 ──────────────────────────────────────────

const showResetDialog = ref(false)
const resetTarget = ref<SelfUser | null>(null)
const resetFormRef = ref<FormInstance>()
const isResetting = ref(false)
const resetForm = reactive({
  newPassword: '',
})
const resetRules: FormRules<typeof resetForm> = {
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, message: '密码至少需要 8 个字符', trigger: 'blur' },
  ],
}

// ── 数据加载 ──────────────────────────────────────────────

async function loadUsers() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const data = await getAdminUsers(currentPage.value, pageSize.value)
    users.value = data.items
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
      errorMessage.value = '学生列表加载失败，请稍后重试'
    }
  } finally {
    isLoading.value = false
  }
}


function handlePageChange(page: number) {
  currentPage.value = page
  loadUsers()
}


function handleSizeChange(size: number) {
  pageSize.value = size
  currentPage.value = 1
  loadUsers()
}

// ── 密码重置 ──────────────────────────────────────────────

function openResetDialog(user: SelfUser) {
  resetTarget.value = user
  resetForm.newPassword = ''
  showResetDialog.value = true
}


function cancelReset() {
  showResetDialog.value = false
  resetTarget.value = null
}


async function submitReset() {
  if (!resetFormRef.value || !resetTarget.value) {
    return
  }

  try {
    await resetFormRef.value.validate()
  } catch {
    return
  }

  isResetting.value = true
  try {
    await resetPassword(resetTarget.value.id, resetForm.newPassword)
    ElMessage.success(`已为 ${resetTarget.value.name} 重置密码`)
    showResetDialog.value = false
    resetTarget.value = null
  } catch (error) {
    ElMessage.error(
      error instanceof ApiRequestError
        ? error.message
        : '密码重置失败，请稍后重试',
    )
  } finally {
    isResetting.value = false
  }
}

// ── 格式化 ────────────────────────────────────────────────

function formatDate(isoString: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'long',
    timeStyle: 'short',
    timeZone: 'Asia/Shanghai',
  }).format(new Date(isoString))
}


function statusTagType(status: string): 'success' | 'danger' {
  return status === 'active' ? 'success' : 'danger'
}


function statusLabel(status: string): string {
  return status === 'active' ? '正常' : '已停用'
}


onMounted(() => {
  loadUsers()
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
      <section class="page-heading" aria-labelledby="admin-title">
        <p class="section-kicker">用户管理</p>
        <h1 id="admin-title">学生账号</h1>
        <p>查看全部学生账号资料，并为指定学生重置密码。</p>
      </section>

      <div style="margin-bottom: 20px; display: flex; gap: 12px">
        <el-button
          type="default"
          @click="emit('navigate', '/admin/clubs')"
        >
          社团管理
        </el-button>
      </div>

      <!-- 错误状态 -->
      <el-alert
        v-if="errorMessage"
        type="error"
        :title="errorMessage"
        :closable="false"
        show-icon
        class="form-alert"
      />

      <!-- 加载与数据表格 -->
      <el-card
        v-loading="isLoading"
        class="data-card"
        shadow="never"
        aria-live="polite"
      >
        <template v-if="!errorMessage && users.length === 0 && !isLoading">
          <el-empty description="暂无学生账号" />
        </template>

        <template v-else-if="!errorMessage">
          <el-table
            :data="users"
            style="width: 100%"
            stripe
          >
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="username" label="用户名" min-width="120" />
            <el-table-column prop="name" label="姓名" min-width="100" />
            <el-table-column prop="phone" label="手机号" min-width="120" />
            <el-table-column
              prop="major_class"
              label="专业班级"
              min-width="150"
            />
            <el-table-column prop="grade" label="年级" width="80" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag
                  :type="statusTagType(row.account_status)"
                  effect="light"
                  size="small"
                >
                  {{ statusLabel(row.account_status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="注册时间" min-width="170">
              <template #default="{ row }">
                {{ formatDate(row.registered_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button
                  type="primary"
                  link
                  size="small"
                  @click="openResetDialog(row as SelfUser)"
                >
                  重置密码
                </el-button>
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

    <!-- 密码重置弹窗 -->
    <el-dialog
      v-model="showResetDialog"
      :title="`重置密码 — ${resetTarget?.name ?? ''}`"
      width="460px"
      :close-on-click-modal="false"
      @closed="cancelReset"
    >
      <p class="dialog-hint">
        为 <strong>{{ resetTarget?.username }}</strong>（{{ resetTarget?.name }}）设置新密码。重置后旧密码立即失效。
      </p>
      <el-form
        ref="resetFormRef"
        :model="resetForm"
        :rules="resetRules"
        label-position="top"
        @submit.prevent="submitReset"
      >
        <el-form-item label="新密码" prop="newPassword">
          <el-input
            v-model="resetForm.newPassword"
            type="password"
            autocomplete="new-password"
            placeholder="请输入至少 8 位新密码"
            show-password
            @keyup.enter="submitReset"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="cancelReset">取消</el-button>
        <el-button
          type="primary"
          :loading="isResetting"
          @click="submitReset"
        >
          确认重置
        </el-button>
      </template>
    </el-dialog>
  </main>
</template>
