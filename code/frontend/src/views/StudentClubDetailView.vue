<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'

import { submitApplication } from '../api/applications'
import { ApiRequestError } from '../api/auth'
import { createPost, createReply, getClubDetail, getPublicRecruitments, likePost, listAnnouncements, listPosts, listReplies, unlikePost } from '../api/clubs'
import type { Announcement, Club, Post, Recruitment, Reply } from '../types/club'


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

// ── S10 帖子 ────────────────────────────────────────────────

const posts = ref<Post[]>([])
const isLoadingPosts = ref(false)

//发布帖子弹窗
const showPostDialog = ref(false)
const postFormRef = ref<FormInstance>()
const postForm = reactive({
  title: '',
  content: '',
})
const isSubmittingPost = ref(false)
const postFormRules: FormRules<typeof postForm> = {
  title: [
    { required: true, message: '请输入帖子标题', trigger: 'blur' },
    { max: 255, message: '标题不能超过 255 字', trigger: 'blur' },
  ],
  content: [
    { required: true, message: '请输入帖子内容', trigger: 'blur' },
    { max: 5000, message: '内容不能超过 5000 字', trigger: 'blur' },
  ],
}

// ── S11 回复 ────────────────────────────────────────────────

//每个帖子的回复列表和加载状态
const repliesMap = ref<Record<number, Reply[]>>({})
const isLoadingRepliesMap = ref<Record<number, boolean>>({})
//每个帖子的回复展开状态
const expandedPosts = ref<Set<number>>(new Set())
//回复表单
const replyFormContent = ref<Record<number, string>>({})
const isSubmittingReply = ref<Record<number, boolean>>({})

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


async function loadPosts() {
  if (Number.isNaN(clubId)) return
  isLoadingPosts.value = true
  try {
    const data = await listPosts(clubId)
    posts.value = data.items
  } catch {
    posts.value = []
  } finally {
    isLoadingPosts.value = false
  }
}


async function handleCreatePost() {
  const valid = await postFormRef.value?.validate().catch(() => false)
  if (!valid) return

  isSubmittingPost.value = true
  try {
    await createPost(clubId, {
      title: postForm.title.trim(),
      content: postForm.content.trim(),
    })
    ElMessage.success('帖子发布成功')
    showPostDialog.value = false
    postForm.title = ''
    postForm.content = ''
    await loadPosts()
  } catch (error) {
    if (error instanceof ApiRequestError) {
      ElMessage.error(error.message)
    } else {
      ElMessage.error('发布失败，请稍后重试')
    }
  } finally {
    isSubmittingPost.value = false
  }
}


// ── S11 回复 ──────────────────────────────────────────────

function toggleReplies(postId: number) {
  if (expandedPosts.value.has(postId)) {
    expandedPosts.value.delete(postId)
  } else {
    expandedPosts.value.add(postId)
    //首次展开时加载回复
    if (!repliesMap.value[postId]) {
      loadRepliesForPost(postId)
    }
  }
  //触发响应式更新
  expandedPosts.value = new Set(expandedPosts.value)
}


async function loadRepliesForPost(postId: number) {
  isLoadingRepliesMap.value = { ...isLoadingRepliesMap.value, [postId]: true }
  try {
    const data = await listReplies(postId)
    repliesMap.value = { ...repliesMap.value, [postId]: data.items }
  } catch {
    repliesMap.value = { ...repliesMap.value, [postId]: [] }
  } finally {
    isLoadingRepliesMap.value = { ...isLoadingRepliesMap.value, [postId]: false }
  }
}


async function handleCreateReply(postId: number) {
  const content = (replyFormContent.value[postId] || '').trim()
  if (!content) {
    ElMessage.warning('回复内容不能为空')
    return
  }

  isSubmittingReply.value = { ...isSubmittingReply.value, [postId]: true }
  try {
    await createReply(postId, { content })
    ElMessage.success('回复成功')
    replyFormContent.value = { ...replyFormContent.value, [postId]: '' }
    //重新加载该帖子的回复
    await loadRepliesForPost(postId)
  } catch (error) {
    if (error instanceof ApiRequestError) {
      ElMessage.error(error.message)
    } else {
      ElMessage.error('回复失败，请稍后重试')
    }
  } finally {
    isSubmittingReply.value = { ...isSubmittingReply.value, [postId]: false }
  }
}


// ── S12 点赞 ──────────────────────────────────────────────

//点赞数实时更新时使用 loading 映射防止重复点击
const isTogglingLike = ref<Record<number, boolean>>({})

async function handleToggleLike(post: Post) {
  if (isTogglingLike.value[post.id]) return
  isTogglingLike.value = { ...isTogglingLike.value, [post.id]: true }
  try {
    if (post.liked_by_me) {
      const updated = await unlikePost(post.id)
      //替换列表中对应帖子
      const idx = posts.value.findIndex(p => p.id === post.id)
      if (idx !== -1) posts.value[idx] = updated
    } else {
      const updated = await likePost(post.id)
      const idx = posts.value.findIndex(p => p.id === post.id)
      if (idx !== -1) posts.value[idx] = updated
    }
  } catch (error) {
    if (error instanceof ApiRequestError) {
      ElMessage.error(error.message)
    } else {
      ElMessage.error('操作失败，请稍后重试')
    }
  } finally {
    isTogglingLike.value = { ...isTogglingLike.value, [post.id]: false }
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
      loadPosts()
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

        <!-- S10 帖子列表 -->
        <el-card
          v-if="club.status === 'normal'"
          class="profile-card"
          shadow="never"
          style="margin-top: 20px"
        >
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span style="font-weight: 600">社团帖子</span>
              <el-button type="primary" size="small" @click="showPostDialog = true">
                发布帖子
              </el-button>
            </div>
          </template>

          <div v-if="isLoadingPosts" v-loading="true" style="min-height: 80px" />

          <div v-else-if="posts.length === 0">
            <el-empty description="暂无帖子" :image-size="60" />
          </div>

          <div v-else>
            <div
              v-for="p in posts"
              :key="p.id"
              class="post-item"
            >
              <div class="post-header">
                <div class="post-title-row">
                  <el-tag v-if="p.is_pinned" type="warning" size="small" effect="light">
                    置顶
                  </el-tag>
                  <span class="post-title">{{ p.title }}</span>
                </div>
                <span class="post-meta">
                  {{ p.author.username }}
                </span>
              </div>
              <p class="post-content">{{ p.content }}</p>

              <!-- S12 点赞 -->
              <div class="post-actions">
                <el-button
                  :type="p.liked_by_me ? 'danger' : 'default'"
                  size="small"
                  :icon="p.liked_by_me ? undefined : undefined"
                  :loading="isTogglingLike[p.id]"
                  @click="handleToggleLike(p)"
                >
                  {{ p.liked_by_me ? '❤️' : '🤍' }} {{ p.like_count }}
                </el-button>
              </div>

              <!-- S11 回复区域 -->
              <div class="post-replies-section">
                <el-button
                  text
                  size="small"
                  type="primary"
                  @click="toggleReplies(p.id)"
                >
                  {{ expandedPosts.has(p.id) ? '收起回复' : '查看回复' }}
                </el-button>

                <div v-if="expandedPosts.has(p.id)" class="replies-container">
                  <!-- 回复列表 -->
                  <div v-if="isLoadingRepliesMap[p.id]" v-loading="true" style="min-height: 60px" />

                  <div v-else-if="!repliesMap[p.id] || repliesMap[p.id].length === 0" class="replies-empty">
                    暂无回复
                  </div>

                  <div v-else class="replies-list">
                    <div
                      v-for="reply in repliesMap[p.id]"
                      :key="reply.id"
                      class="reply-item"
                    >
                      <span class="reply-author">{{ reply.author.username }}</span>
                      <span class="reply-content">{{ reply.content }}</span>
                    </div>
                  </div>

                  <!-- 回复表单 -->
                  <div class="reply-form">
                    <el-input
                      :model-value="replyFormContent[p.id] || ''"
                      type="textarea"
                      :rows="2"
                      maxlength="1000"
                      show-word-limit
                      placeholder="写下你的回复…"
                      @update:model-value="(val: string) => {
                        replyFormContent = { ...replyFormContent, [p.id]: val }
                      }"
                    />
                    <el-button
                      type="primary"
                      size="small"
                      :loading="isSubmittingReply[p.id]"
                      style="margin-top: 8px"
                      @click="handleCreateReply(p.id)"
                    >
                      发表回复
                    </el-button>
                  </div>
                </div>
              </div>

              <el-divider v-if="p !== posts[posts.length - 1]" />
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

        <!-- 发布帖子弹窗 -->
        <el-dialog
          v-model="showPostDialog"
          title="发布帖子"
          width="520px"
          :close-on-click-modal="false"
        >
          <el-form
            ref="postFormRef"
            :model="postForm"
            :rules="postFormRules"
            label-position="top"
          >
            <el-form-item label="帖子标题" prop="title">
              <el-input
                v-model="postForm.title"
                maxlength="255"
                show-word-limit
                placeholder="请输入帖子标题"
              />
            </el-form-item>
            <el-form-item label="帖子内容" prop="content">
              <el-input
                v-model="postForm.content"
                type="textarea"
                :rows="5"
                maxlength="5000"
                show-word-limit
                placeholder="请输入帖子内容"
              />
            </el-form-item>
          </el-form>

          <template #footer>
            <el-button @click="showPostDialog = false">取消</el-button>
            <el-button type="primary" :loading="isSubmittingPost" @click="handleCreatePost">
              发布
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

.post-item {
  padding: 4px 0;
}

.post-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.post-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.post-title {
  font-size: 15px;
  font-weight: 600;
}

.post-meta {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
}

.post-content {
  color: #606266;
  line-height: 1.7;
  white-space: pre-wrap;
  margin: 0;
}

.post-actions {
  margin-top: 8px;
}

.post-replies-section {
  margin-top: 10px;
}

.replies-container {
  margin-top: 8px;
  padding: 10px 12px;
  background: #fafbfc;
  border-radius: 8px;
  border: 1px solid #ebeef5;
}

.replies-empty {
  color: #909399;
  font-size: 13px;
  padding: 12px 0;
  text-align: center;
}

.replies-list {
  margin-bottom: 10px;
}

.reply-item {
  padding: 6px 0;
  border-bottom: 1px solid #f0f0f0;
}

.reply-item:last-child {
  border-bottom: none;
}

.reply-author {
  font-weight: 600;
  font-size: 13px;
  color: #303133;
  margin-right: 8px;
}

.reply-content {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
  white-space: pre-wrap;
}

.reply-form {
  margin-top: 8px;
}
</style>
