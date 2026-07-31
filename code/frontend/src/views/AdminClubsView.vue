<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  ElMessage,
  ElMessageBox,
  type FormInstance,
  type FormRules,
  type UploadFile,
} from 'element-plus'

import { ApiRequestError, getAdminUsers } from '../api/auth'
import { createClub, getAdminClubs } from '../api/clubs'
import { CLUB_CATEGORIES, type Club, type ClubCategory } from '../types/club'
import type { SelfUser } from '../types/user'


const emit = defineEmits<{
  navigate: [path: string]
}>()

// ── 列表状态 ──────────────────────────────────────────────

const isLoading = ref(true)
const errorMessage = ref('')
const clubs = ref<Club[]>([])
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

// ── 创建社团弹窗 ──────────────────────────────────────────

const showCreateDialog = ref(false)
const createFormRef = ref<FormInstance>()
const isCreating = ref(false)
const logoFile = ref<File | null>(null)

const createForm = reactive({
  name: '',
  category: '' as ClubCategory | '',
  introduction: '',
  leaderIds: [] as number[],
})

const createRules: FormRules<typeof createForm> = {
  name: [
    { required: true, message: '请输入社团名称', trigger: 'blur' },
    { max: 100, message: '社团名称不能超过 100 个字符', trigger: 'blur' },
  ],
  category: [
    { required: true, message: '请选择社团类别', trigger: 'change' },
  ],
  introduction: [
    { required: true, message: '请输入社团简介', trigger: 'blur' },
  ],
  leaderIds: [
    {
      type: 'array',
      required: true,
      min: 1,
      message: '至少选择一名初始负责人',
      trigger: 'change',
    },
  ],
}

//学生列表（供负责人选择）
const studentOptions = ref<{ label: string; value: number }[]>([])

// ── 数据加载 ──────────────────────────────────────────────

async function loadClubs() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const data = await getAdminClubs(currentPage.value, pageSize.value)
    clubs.value = data.items
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
      errorMessage.value = '社团列表加载失败，请稍后重试'
    }
  } finally {
    isLoading.value = false
  }
}


async function loadStudentOptions() {
  try {
    const data = await getAdminUsers(1, 100)
    studentOptions.value = data.items
      .filter((u: SelfUser) => u.account_status === 'active')
      .map((u: SelfUser) => ({
        label: `${u.name}（${u.username}）— ${u.major_class}`,
        value: u.id,
      }))
  } catch {
    studentOptions.value = []
  }
}


function handlePageChange(page: number) {
  currentPage.value = page
  loadClubs()
}


function handleSizeChange(size: number) {
  pageSize.value = size
  currentPage.value = 1
  loadClubs()
}

// ── 创建社团 ──────────────────────────────────────────────

function openCreateDialog() {
  createForm.name = ''
  createForm.category = ''
  createForm.introduction = ''
  createForm.leaderIds = []
  logoFile.value = null
  showCreateDialog.value = true
  loadStudentOptions()
}


function handleLogoChange(file: UploadFile) {
  if (file.raw) {
    logoFile.value = file.raw
  }
}


function cancelCreate() {
  showCreateDialog.value = false
}


async function submitCreate() {
  if (!createFormRef.value) return

  try {
    await createFormRef.value.validate()
  } catch {
    return
  }

  if (!logoFile.value) {
    ElMessage.error('请上传社团 Logo')
    return
  }

  isCreating.value = true
  try {
    const formData = new FormData()
    formData.append('name', createForm.name)
    formData.append('category', createForm.category)
    formData.append('introduction', createForm.introduction)
    formData.append('logo', logoFile.value)
    formData.append('leader_user_ids', JSON.stringify(createForm.leaderIds))

    const result = await createClub(formData)
    ElMessage.success(`社团"${result.club.name}"创建成功`)
    showCreateDialog.value = false
    loadClubs()
  } catch (error) {
    ElMessage.error(
      error instanceof ApiRequestError
        ? error.message
        : '社团创建失败，请稍后重试',
    )
  } finally {
    isCreating.value = false
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


function statusTagType(status: string): 'success' | 'info' {
  return status === 'normal' ? 'success' : 'info'
}


function statusLabel(status: string): string {
  return status === 'normal' ? '正常' : '已注销'
}


onMounted(() => {
  loadClubs()
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
        <p class="section-kicker">社团管理</p>
        <h1 id="admin-title">社团</h1>
        <p>创建社团并指定初始负责人，查看全部社团记录。</p>
      </section>

      <div style="margin-bottom: 20px">
        <el-button type="primary" @click="openCreateDialog">
          创建社团
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
        <template v-if="!errorMessage && clubs.length === 0 && !isLoading">
          <el-empty description="暂无社团记录" />
        </template>

        <template v-else-if="!errorMessage">
          <el-table :data="clubs" style="width: 100%" stripe>
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="name" label="社团名称" min-width="140" />
            <el-table-column prop="category" label="类别" width="100" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag
                  :type="statusTagType(row.status)"
                  effect="light"
                  size="small"
                >
                  {{ statusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="创建时间" min-width="170">
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
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

    <!-- 创建社团弹窗 -->
    <el-dialog
      v-model="showCreateDialog"
      title="创建社团"
      width="560px"
      :close-on-click-modal="false"
      @closed="cancelCreate"
    >
      <el-form
        ref="createFormRef"
        :model="createForm"
        :rules="createRules"
        label-position="top"
        @submit.prevent="submitCreate"
      >
        <el-form-item label="社团名称" prop="name">
          <el-input
            v-model="createForm.name"
            placeholder="请输入唯一社团名称"
            maxlength="100"
            show-word-limit
          />
        </el-form-item>

        <el-form-item label="社团类别" prop="category">
          <el-select
            v-model="createForm.category"
            placeholder="请选择社团类别"
            style="width: 100%"
          >
            <el-option
              v-for="cat in CLUB_CATEGORIES"
              :key="cat"
              :label="cat"
              :value="cat"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="社团简介" prop="introduction">
          <el-input
            v-model="createForm.introduction"
            type="textarea"
            :rows="4"
            placeholder="请输入社团简介"
          />
        </el-form-item>

        <el-form-item label="社团 Logo" required>
          <el-upload
            :auto-upload="false"
            :limit="1"
            accept="image/*"
            :on-change="handleLogoChange"
            drag
          >
            <el-icon class="el-icon--upload"><span style="font-size:24px">📷</span></el-icon>
            <div class="el-upload__text">
              将 Logo 文件拖到此处，或<em>点击上传</em>
            </div>
          </el-upload>
        </el-form-item>

        <el-form-item label="初始负责人" prop="leaderIds">
          <el-select
            v-model="createForm.leaderIds"
            multiple
            filterable
            placeholder="请选择至少一名账号正常的学生作为初始负责人"
            style="width: 100%"
          >
            <el-option
              v-for="opt in studentOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="cancelCreate">取消</el-button>
        <el-button
          type="primary"
          :loading="isCreating"
          @click="submitCreate"
        >
          创建
        </el-button>
      </template>
    </el-dialog>
  </main>
</template>
