<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

import { ApiRequestError } from '../api/auth'
import {
  createRecruitment,
  endRecruitment,
  getLeaderRecruitments,
  updateRecruitment,
} from '../api/clubs'
import type { Recruitment } from '../types/club'


const emit = defineEmits<{
  navigate: [path: string]
}>()

const clubId = computed(() => {
  const match = window.location.pathname.match(/^\/leader\/clubs\/(\d+)\/recruitments/)
  return match ? Number(match[1]) : 0
})

// ── 列表状态 ──────────────────────────────────────────────

const isLoading = ref(true)
const errorMessage = ref('')
const recruitments = ref<Recruitment[]>([])

// ── 创建/编辑弹窗 ────────────────────────────────────────

const dialogVisible = ref(false)
const dialogTitle = ref('发布招新')
const isEditing = ref(false)
const editingRecruitmentId = ref<number | null>(null)
const isSaving = ref(false)
const formRef = ref<FormInstance>()

const form = reactive({
  title: '',
  introduction: '',
  requirements: '',
  capacity: 1,
  start_time: '',
  end_time: '',
})

const formRules: FormRules<typeof form> = {
  title: [
    { required: true, message: '请输入招新标题', trigger: 'blur' },
    { max: 200, message: '标题不能超过 200 字', trigger: 'blur' },
  ],
  introduction: [
    { required: true, message: '请输入招新简介', trigger: 'blur' },
  ],
  requirements: [
    { required: true, message: '请输入招新要求', trigger: 'blur' },
  ],
  capacity: [
    { required: true, message: '请输入招新人数', trigger: 'blur' },
  ],
  start_time: [
    { required: true, message: '请选择开始时间', trigger: 'change' },
  ],
  end_time: [
    { required: true, message: '请选择结束时间', trigger: 'change' },
  ],
}


function openCreateDialog() {
  isEditing.value = false
  editingRecruitmentId.value = null
  dialogTitle.value = '发布招新'
  form.title = ''
  form.introduction = ''
  form.requirements = ''
  form.capacity = 1
  form.start_time = ''
  form.end_time = ''
  dialogVisible.value = true
}


function openEditDialog(recruitment: Recruitment) {
  isEditing.value = true
  editingRecruitmentId.value = recruitment.id
  dialogTitle.value = '修改招新'
  form.title = recruitment.title
  form.introduction = recruitment.introduction
  form.requirements = recruitment.requirements
  form.capacity = recruitment.capacity
  //格式化时间为 datetime-local 兼容格式
  form.start_time = recruitment.start_time.substring(0, 16)
  form.end_time = recruitment.end_time.substring(0, 16)
  dialogVisible.value = true
}


function canModify(recruitment: Recruitment): boolean {
  return recruitment.display_status !== '已结束'
}


async function handleSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  isSaving.value = true
  try {
    const payload = {
      title: form.title,
      introduction: form.introduction,
      requirements: form.requirements,
      capacity: form.capacity,
      start_time: form.start_time ? new Date(form.start_time).toISOString() : '',
      end_time: form.end_time ? new Date(form.end_time).toISOString() : '',
    }

    if (isEditing.value && editingRecruitmentId.value) {
      await updateRecruitment(editingRecruitmentId.value, payload)
      ElMessage.success('招新修改成功')
    } else {
      await createRecruitment(clubId.value, payload)
      ElMessage.success('招新发布成功')
    }

    dialogVisible.value = false
    await loadRecruitments()
  } catch (error) {
    if (error instanceof ApiRequestError) {
      if (error.code === 'UNAUTHENTICATED') {
        emit('navigate', '/login?reason=session')
        return
      }
      ElMessage.error(error.message)
    } else {
      ElMessage.error('操作失败，请稍后重试')
    }
  } finally {
    isSaving.value = false
  }
}


async function handleEnd(recruitment: Recruitment) {
  try {
    await ElMessageBox.confirm(
      `确定要提前结束招新「${recruitment.title}」吗？结束后学生将无法提交申请。`,
      '确认操作',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }

  try {
    await endRecruitment(recruitment.id)
    ElMessage.success('招新已提前结束')
    await loadRecruitments()
  } catch (error) {
    if (error instanceof ApiRequestError) {
      ElMessage.error(error.message)
    } else {
      ElMessage.error('操作失败，请稍后重试')
    }
  }
}


// ── 数据加载 ──────────────────────────────────────────────

async function loadRecruitments() {
  if (!clubId.value) {
    errorMessage.value = '无效的社团 ID'
    isLoading.value = false
    return
  }

  isLoading.value = true
  errorMessage.value = ''
  try {
    const data = await getLeaderRecruitments(clubId.value)
    recruitments.value = data.items
  } catch (error) {
    if (error instanceof ApiRequestError) {
      if (error.code === 'UNAUTHENTICATED') {
        emit('navigate', '/login?reason=session')
        return
      }
      errorMessage.value = error.message
    } else {
      errorMessage.value = '招新列表加载失败，请稍后重试'
    }
  } finally {
    isLoading.value = false
  }
}


function goBack() {
  emit('navigate', `/leader/clubs/${clubId.value}`)
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
  <div class="leader-recruitments-view">
    <el-page-header @back="goBack">
      <template #content>
        <span>招新管理</span>
      </template>
      <template #extra>
        <el-button type="primary" @click="openCreateDialog">发布招新</el-button>
      </template>
    </el-page-header>

    <div v-if="isLoading" class="loading-container">
      <el-skeleton :rows="4" animated />
    </div>

    <div v-else-if="errorMessage" class="error-container">
      <el-result icon="error" :title="errorMessage">
        <template #extra>
          <el-button type="primary" @click="loadRecruitments">重新加载</el-button>
        </template>
      </el-result>
    </div>

    <div v-else-if="recruitments.length === 0" class="empty-container">
      <el-empty description="暂无招新信息">
        <el-button type="primary" @click="openCreateDialog">发布第一条招新</el-button>
      </el-empty>
    </div>

    <div v-else class="recruitment-list">
      <el-card
        v-for="recruitment in recruitments"
        :key="recruitment.id"
        class="recruitment-card"
        shadow="hover"
      >
        <template #header>
          <div class="card-header">
            <span class="card-title">{{ recruitment.title }}</span>
            <div class="card-header-right">
              <el-tag :type="statusTagType(recruitment.display_status)" size="small">
                {{ recruitment.display_status }}
              </el-tag>
              <span class="approved-count">
                {{ recruitment.approved_count }} / {{ recruitment.capacity }} 人
              </span>
            </div>
          </div>
        </template>

        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="开始时间">
            {{ formatTime(recruitment.start_time) }}
          </el-descriptions-item>
          <el-descriptions-item label="结束时间">
            {{ formatTime(recruitment.end_time) }}
          </el-descriptions-item>
          <el-descriptions-item label="发布时间">
            {{ formatTime(recruitment.published_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="发布人">
            {{ recruitment.publisher.username }}
          </el-descriptions-item>
        </el-descriptions>

        <el-divider content-position="left">招新简介</el-divider>
        <p class="recruitment-text">{{ recruitment.introduction }}</p>

        <el-divider content-position="left">招新要求</el-divider>
        <p class="recruitment-text">{{ recruitment.requirements }}</p>

        <div v-if="canModify(recruitment)" class="card-actions">
          <el-button type="primary" size="small" @click="openEditDialog(recruitment)">
            修改
          </el-button>
          <el-button type="danger" size="small" @click="handleEnd(recruitment)">
            提前结束
          </el-button>
        </div>
        <div v-else class="card-actions">
          <el-tag type="info" size="small">已结束，不可操作</el-tag>
        </div>
      </el-card>
    </div>

    <!-- 创建/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="560px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-width="80px"
        label-position="top"
      >
        <el-form-item label="招新标题" prop="title">
          <el-input v-model="form.title" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="招新简介" prop="introduction">
          <el-input
            v-model="form.introduction"
            type="textarea"
            :rows="3"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="招新要求" prop="requirements">
          <el-input
            v-model="form.requirements"
            type="textarea"
            :rows="3"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="招新人数" prop="capacity">
          <el-input-number v-model="form.capacity" :min="1" :max="9999" />
        </el-form-item>
        <el-form-item label="开始时间" prop="start_time">
          <el-date-picker
            v-model="form.start_time"
            type="datetime"
            placeholder="选择开始时间"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DDTHH:mm"
          />
        </el-form-item>
        <el-form-item label="结束时间" prop="end_time">
          <el-date-picker
            v-model="form.end_time"
            type="datetime"
            placeholder="选择结束时间"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DDTHH:mm"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="isSaving" @click="handleSave">
          {{ isEditing ? '保存修改' : '发布' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.leader-recruitments-view {
  max-width: 800px;
  margin: 0 auto;
  padding: 24px 16px;
}

.loading-container,
.error-container,
.empty-container {
  margin-top: 48px;
  text-align: center;
}

.recruitment-list {
  margin-top: 24px;
}

.recruitment-card {
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.card-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.approved-count {
  font-size: 13px;
  color: #909399;
}

.recruitment-text {
  color: #606266;
  line-height: 1.7;
  white-space: pre-wrap;
  margin: 0 0 8px 0;
}

.card-actions {
  margin-top: 12px;
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
</style>
