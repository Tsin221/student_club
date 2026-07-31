<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'

import { submitApplication } from '../api/applications'
import { ApiRequestError } from '../api/auth'
import { getClubDetail, getPublicRecruitments, listAnnouncements } from '../api/clubs'
import type { Announcement, Club, Recruitment } from '../types/club'


const emit = defineEmits<{
  navigate: [path: string]
}>()

//从 URL 路径解析 clubId
function parseClubId(): number {
  const parts = window.location.pathname.split('/')
  const id = Number(parts[parts.length - 1])
  return Number.isFinite(id) && id > 0 ? id : NaN
}

// ── 状态 ──────────────────────────────────────────────────

const isLoading = ref(true)
const errorMessage = ref('')
const club = ref<Club | null>(null)
const clubId = parseClubId()

	// ── 招新 ──────────────────────────────────────────────────

const recruitments = ref<Recruitment[]>([])
const isLoadingRecruitments = ref(false)

// ── S09 公告 ────────────────────────────────────────────────

const announcements = ref<Announcement[]>([])
const isLoadingAnnouncements = ref(false)

// ── 数据加载 ──────────────────────────────────────────────

async function loadDetail() {
  if (Number.isNaN(clubId)) {
    errorMessage.value = '无效的社团 ID'
    isLoading.value = false
    return
  }

  isLoading.value = true
  errorMessage.value = ''
  try {
    club.value = await getClubDetail(clubId)
  } catch (error) {
    if (error instanceof ApiRequestError) {
      if (error.code === 'UNAUTHENTICATED') {
        emit('navigate', '/login?reason=session')
        return
      }
      errorMessage.value = error.message
    } else {
      errorMessage.value = '社团详情加载失败，请稍后重试'
    }
  } finally {
    isLoading.value = false
  }
}


async function loadRecruitments() {
  if (Number.isNaN(clubId)) return
  isLoadingRecruitments.value = true
  try {
    const data = await getPublicRecruitments(clubId)
    recruitments.value = data.items
  } catch {
    recruitments.value = []
  } finally {
    isLoadingRecruitments.value = false
  }
}


async function loadAnnouncements() {
  if (Number.isNaN(clubId)) return
  isLoadingAnnouncements.value = true
  try {
    const data = await listAnnouncements(clubId)
    announcements.value = data.items
  } catch {
    announcements.value = []
  } finally {
    isLoadingAnnouncements.value = false
  }
}


function goBack() {
  emit('navigate', '/student/clubs')
}


function formatDate(isoString: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'long',
    timeZone: 'Asia/Shanghai',
  }).format(new Date(isoString))
}


function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN')
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
  loadDetail().then(() => {
    if (club.value && club.value.status === 'normal') {
      loadRecruitments()
      loadAnnouncements()
    }
  })
})
</script>

<template>
  <main class="student-page">
    <header class="student-header">
      <div class="brand-mark" aria-hidden="true">社</div>
      <div>
        <p class="eyebrow">校园社团智能管理系统</p>
        <p class="header-title">社团详情</p>
      </div>
    </header>

    <div class="student-content">
      <el-button
        text
        type="primary"
        style="margin-bottom: 24px"
        @click="goBack"
      >
        ← 返回社团列表
      </el-button>

      <!-- 错误状态 -->
      <el-alert
        v-if="errorMessage"
        type="error"
        :title="errorMessage"
        :closable="false"
        show-icon
        class="form-alert"
      />

      <!-- 加载 -->
      <el-card
        v-if="isLoading"
        v-loading="true"
        class="profile-card"
        shadow="never"
        style="min-height: 240px"
      />

      <!-- 详情 -->
      <template v-else-if="club">
        <el-card class="profile-card" shadow="never">
          <div class="profile-summary">
            <div
              v-if="club.logo"
              class="club-detail-logo"
            >
              <img
                :src="club.logo"
                :alt="`${club.name} Logo`"
                class="club-detail-logo-img"
              >
            </div>
            <div class="profile-summary-body">
              <div class="profile-name-row">
                <h2>{{ club.name }}</h2>
                <el-tag
                  :type="club.status === 'normal' ? 'success' : 'info'"
                  effect="light"
                  size="small"
                >
                  {{ club.status === 'normal' ? '正常' : '已注销' }}
                </el-tag>
              </div>
              <p>
                <strong>类别：</strong>{{ club.category }}
                &nbsp;|&nbsp;
                <strong>创建于：</strong>{{ formatDate(club.created_at) }}
              </p>
            </div>
          </div>
        </el-card>

        <el-card
          class="profile-card"
          shadow="never"
          style="margin-top: 20px"
        >
          <h3 style="margin: 0 0 12px">社团简介</h3>
          <p style="color: var(--muted); line-height: 1.8; white-space: pre-wrap">
            {{ club.introduction }}
          </p>
        </el-card>

        <!-- S09 社团公告 -->
        <el-card
          v-if="club.status === 'normal'"
          class="profile-card"
          shadow="never"
          style="margin-top: 20px"
        >
          <template #header>
            <span style="font-weight: 600">社团公告</span>
          </template>

          <div v-if="isLoadingAnnouncements" v-loading="true" style="min-height: 80px" />

          <div v-else-if="announcements.length === 0">
            <el-empty description="暂无公告" :image-size="60" />
          </div>

          <div v-else>
            <div
              v-for="a in announcements"
              :key="a.id"
              class="announcement-item"
            >
              <div class="announcement-header">
                <div class="announcement-title-row">
                  <el-tag v-if="a.is_pinned" type="warning" size="small" effect="light">
                    置顶
                  </el-tag>
                  <span class="announcement-title">{{ a.title }}</span>
                </div>
                <span class="announcement-meta">
                  {{ a.publisher.username }} · {{ formatDateTime(a.published_at) }}
                </span>
              </div>
              <p class="announcement-content">{{ a.content }}</p>
              <el-divider v-if="a !== announcements[announcements.length - 1]" />
            </div>
          </div>
        </el-card>

        <el-card
          v-if="club.status === 'normal'"
          class="profile-card"
          shadow="never"
          style="margin-top: 20px"
        >
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span style="font-weight: 600">招新信息</span>
            </div>
          </template>

          <div v-if="isLoadingRecruitments" v-loading="true" style="min-height: 80px" />

          <div v-else-if="recruitments.length === 0">
            <el-empty description="该社团暂无有效招新" :image-size="60" />
          </div>

          <div v-else>
            <el-card
              v-for="recruitment in recruitments"
              :key="recruitment.id"
              class="recruitment-inline-card"
              shadow="hover"
            >
              <div class="recruitment-inline-header">
                <span class="recruitment-inline-title">{{ recruitment.title }}</span>
                <el-tag :type="statusTagType(recruitment.display_status)" size="small">
                  {{ recruitment.display_status }}
                </el-tag>
              </div>

              <el-descriptions :column="2" border size="small" style="margin-top: 12px">
                <el-descriptions-item label="招新人数">
                  {{ recruitment.approved_count }} / {{ recruitment.capacity }}
                </el-descriptions-item>
                <el-descriptions-item label="发布人">
                  {{ recruitment.publisher.username }}
                </el-descriptions-item>
                <el-descriptions-item label="开始时间">
                  {{ formatDateTime(recruitment.start_time) }}
                </el-descriptions-item>
                <el-descriptions-item label="结束时间">
                  {{ formatDateTime(recruitment.end_time) }}
                </el-descriptions-item>
              </el-descriptions>

              <el-divider content-position="left">招新简介</el-divider>
              <p class="recruitment-text">{{ recruitment.introduction }}</p>

              <el-divider content-position="left">招新要求</el-divider>
              <p class="recruitment-text">{{ recruitment.requirements }}</p>

              <div v-if="recruitment.display_status === '进行中'" class="recruitment-actions">
                <el-button type="primary" size="small" @click="openApplyDialog(recruitment)">
                  申请加入
                </el-button>
              </div>
            </el-card>
          </div>
        </el-card>

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
      </template>
    </div>
  </main>
</template>

<style scoped>
.club-detail-logo {
  width: 80px;
  height: 80px;
  border-radius: 16px;
  overflow: hidden;
  background: var(--brand-100);
}

.club-detail-logo-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.recruitment-inline-card {
  margin-bottom: 12px;
}

.recruitment-inline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.recruitment-inline-title {
  font-size: 15px;
  font-weight: 600;
}

.recruitment-text {
  color: #606266;
  line-height: 1.7;
  white-space: pre-wrap;
  margin: 0;
}

.recruitment-actions {
  margin-top: 12px;
  text-align: right;
}

.announcement-item {
  padding: 4px 0;
}

.announcement-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.announcement-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.announcement-title {
  font-size: 15px;
  font-weight: 600;
}

.announcement-meta {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
}

.announcement-content {
  color: #606266;
  line-height: 1.7;
  white-space: pre-wrap;
  margin: 0;
}
</style>
