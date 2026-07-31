<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'

import { submitApplication } from '../api/applications'
import { ApiRequestError } from '../api/auth'
import { getPublicRecruitments } from '../api/clubs'
import type { Recruitment } from '../types/club'


const emit = defineEmits<{
  navigate: [path: string]
}>()

const clubId = computed(() => {
  const match = window.location.pathname.match(/^\/student\/clubs\/(\d+)\/recruitments/)
  return match ? Number(match[1]) : 0
})

const isLoading = ref(true)
const errorMessage = ref('')
const recruitments = ref<Recruitment[]>([])


async function loadRecruitments() {
  if (!clubId.value) {
    errorMessage.value = '无效的社团 ID'
    isLoading.value = false
    return
  }

  isLoading.value = true
  errorMessage.value = ''
  try {
    const data = await getPublicRecruitments(clubId.value)
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
  emit('navigate', `/student/clubs/${clubId.value}`)
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


// ── S07 申请弹窗 ──────────────────────────────────────────

const dialogVisible = ref(false)
const applyingRecruitmentId = ref(0)
const applyingRecruitmentTitle = ref('')
const isSubmitting = ref(false)
const formRef = ref<FormInstance>()

const form = reactive({
  reason: '',
})

const formRules: FormRules<typeof form> = {
  reason: [
    { required: true, message: '请输入申请理由', trigger: 'blur' },
  ],
}


function openApplyDialog(recruitment: Recruitment) {
  applyingRecruitmentId.value = recruitment.id
  applyingRecruitmentTitle.value = recruitment.title
  form.reason = ''
  dialogVisible.value = true
}


async function handleSubmitApplication() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  isSubmitting.value = true
  try {
    await submitApplication(applyingRecruitmentId.value, form.reason)
    ElMessage.success('入社申请提交成功')
    dialogVisible.value = false
    //不重新加载，因为学生看不到自己刚提交的申请在此页面
  } catch (error) {
    if (error instanceof ApiRequestError) {
      ElMessage.error(error.message)
    } else {
      ElMessage.error('提交失败，请稍后重试')
    }
  } finally {
    isSubmitting.value = false
  }
}


onMounted(() => {
  loadRecruitments()
})
</script>

<template>
  <div class="student-recruitments-view">
    <el-page-header @back="goBack">
      <template #content>
        <span>社团招新</span>
      </template>
    </el-page-header>

    <div v-if="isLoading" class="loading-container">
      <el-skeleton :rows="3" animated />
    </div>

    <div v-else-if="errorMessage" class="error-container">
      <el-result icon="error" :title="errorMessage">
        <template #extra>
          <el-button type="primary" @click="loadRecruitments">重新加载</el-button>
          <el-button @click="goBack">返回社团详情</el-button>
        </template>
      </el-result>
    </div>

    <div v-else-if="recruitments.length === 0" class="empty-container">
      <el-empty description="该社团暂无有效招新" />
      <el-button type="primary" @click="goBack">返回社团详情</el-button>
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
            <el-tag :type="statusTagType(recruitment.display_status)" size="small">
              {{ recruitment.display_status }}
            </el-tag>
          </div>
        </template>

        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="招新人数">
            {{ recruitment.approved_count }} / {{ recruitment.capacity }}
          </el-descriptions-item>
          <el-descriptions-item label="发布人">
            {{ recruitment.publisher.username }}
          </el-descriptions-item>
          <el-descriptions-item label="开始时间">
            {{ formatTime(recruitment.start_time) }}
          </el-descriptions-item>
          <el-descriptions-item label="结束时间">
            {{ formatTime(recruitment.end_time) }}
          </el-descriptions-item>
        </el-descriptions>

        <el-divider content-position="left">招新简介</el-divider>
        <p class="recruitment-text">{{ recruitment.introduction }}</p>

        <el-divider content-position="left">招新要求</el-divider>
        <p class="recruitment-text">{{ recruitment.requirements }}</p>

        <div class="card-footer">
          <span class="published-at">发布于 {{ formatTime(recruitment.published_at) }}</span>
          <el-button
            v-if="recruitment.display_status === '进行中'"
            type="primary"
            size="small"
            style="margin-left: 12px"
            @click="openApplyDialog(recruitment)"
          >
            申请加入
          </el-button>
        </div>
      </el-card>
    </div>

    <!-- 申请弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="`申请加入 — ${applyingRecruitmentTitle}`"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-position="top"
      >
        <el-form-item label="申请理由" prop="reason">
          <el-input
            v-model="form.reason"
            type="textarea"
            :rows="4"
            maxlength="500"
            show-word-limit
            placeholder="请简要说明你希望加入该社团的理由"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="isSubmitting" @click="handleSubmitApplication">
          提交申请
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.student-recruitments-view {
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

.empty-container .el-button {
  margin-top: 16px;
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

.recruitment-text {
  color: #606266;
  line-height: 1.7;
  white-space: pre-wrap;
  margin: 0 0 8px 0;
}

.card-footer {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
  align-items: center;
}

.published-at {
  font-size: 12px;
  color: #909399;
}
</style>
