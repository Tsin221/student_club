<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

import { ApiRequestError } from '../api/auth'
import {
  createAnnouncement,
  deleteAnnouncement,
  getClubDetail,
  getLeaderAnnouncements,
  getLeaderFeedbacks,
  getLeaderMembers,
  listPosts,
  pinPost,
  processFeedback,
  removeMember,
  updateAnnouncement,
  updateLeaderClub,
} from '../api/clubs'
import type { Announcement, Club, Feedback, MembershipForLeader, Post } from '../types/club'


const emit = defineEmits<{
  navigate: [path: string]
}>()

const clubId = computed(() => {
  const match = window.location.pathname.match(/^\/leader\/clubs\/(\d+)/)
  return match ? Number(match[1]) : 0
})

// ── 社团信息 ──────────────────────────────────────────────

const isLoading = ref(true)
const errorMessage = ref('')
const club = ref<Club | null>(null)

const editFormRef = ref<FormInstance>()
const isSaving = ref(false)

const editForm = reactive({
  introduction: '',
})

const editRules: FormRules<typeof editForm> = {
  introduction: [
    { required: true, message: '请输入社团简介', trigger: 'blur' },
  ],
}

// ── 成员列表 ──────────────────────────────────────────────

const members = ref<MembershipForLeader[]>([])
const isLoadingMembers = ref(false)
const removingId = ref<number | null>(null)


async function loadClub() {
  if (!clubId.value) {
    errorMessage.value = '无效的社团 ID'
    isLoading.value = false
    return
  }

  isLoading.value = true
  errorMessage.value = ''
  try {
    const data = await getClubDetail(clubId.value)
    club.value = data
    editForm.introduction = data.introduction
  } catch (error) {
    if (error instanceof ApiRequestError) {
      if (error.code === 'UNAUTHENTICATED') {
        emit('navigate', '/login?reason=session')
        return
      }
      if (error.code === 'FORBIDDEN' || error.code === 'ACCOUNT_DISABLED') {
        emit('navigate', '/login')
        return
      }
      errorMessage.value = error.message
    } else {
      errorMessage.value = '社团信息加载失败'
    }
  } finally {
    isLoading.value = false
  }
}


async function loadMembers() {
  isLoadingMembers.value = true
  try {
    const data = await getLeaderMembers(clubId.value)
    members.value = data.items
  } catch (error) {
    if (error instanceof ApiRequestError && error.code === 'NOT_CLUB_LEADER') {
      ElMessage.error('你不是该社团的负责人')
      emit('navigate', '/student/memberships')
      return
    }
    members.value = []
  } finally {
    isLoadingMembers.value = false
  }
}


async function handleRemove(member: MembershipForLeader) {
  try {
    await ElMessageBox.confirm(
      `确定要将「${member.user.name}」移出社团吗？移出后该成员将失去社团内部权限。`,
      '确认移除',
      {
        confirmButtonText: '确定移除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return //用户取消
  }

  removingId.value = member.id
  try {
    await removeMember(member.id)
    //从列表中移除该成员
    members.value = members.value.filter((m) => m.id !== member.id)
    ElMessage.success(`已将「${member.user.name}」移出社团`)
  } catch (error) {
    ElMessage.error(
      error instanceof ApiRequestError ? error.message : '移除失败，请稍后重试',
    )
  } finally {
    removingId.value = null
  }
}


function onRemove(member: unknown) {
  handleRemove(member as MembershipForLeader)
}


function onEditAnnounce(row: unknown) {
  openEditDialog(row as Announcement)
}


function onDeleteAnnounce(row: unknown) {
  handleDeleteAnnouncement(row as Announcement)
}


// ── S09 公告管理 ──────────────────────────────────────────

const announcements = ref<Announcement[]>([])
const isLoadingAnnouncements = ref(false)

//创建/编辑弹窗
const announceDialogVisible = ref(false)
const announceDialogTitle = ref('发布公告')
const isEditing = ref(false)
const editingAnnouncementId = ref(0)
const isSavingAnnounce = ref(false)
const announceFormRef = ref<FormInstance>()
const deletingAnnounceId = ref<number | null>(null)

const announceForm = reactive({
  title: '',
  content: '',
  is_pinned: false,
})

const announceFormRules: FormRules<typeof announceForm> = {
  title: [
    { required: true, message: '请输入公告标题', trigger: 'blur' },
    { max: 200, message: '标题不能超过 200 字', trigger: 'blur' },
  ],
  content: [
    { required: true, message: '请输入公告内容', trigger: 'blur' },
  ],
}


async function loadAnnouncements() {
  isLoadingAnnouncements.value = true
  try {
    const data = await getLeaderAnnouncements(clubId.value)
    announcements.value = data.items
  } catch {
    announcements.value = []
  } finally {
    isLoadingAnnouncements.value = false
  }
}


function openCreateDialog() {
  isEditing.value = false
  editingAnnouncementId.value = 0
  announceDialogTitle.value = '发布公告'
  announceForm.title = ''
  announceForm.content = ''
  announceForm.is_pinned = false
  announceDialogVisible.value = true
}


function openEditDialog(announcement: Announcement) {
  isEditing.value = true
  editingAnnouncementId.value = announcement.id
  announceDialogTitle.value = '编辑公告'
  announceForm.title = announcement.title
  announceForm.content = announcement.content
  announceForm.is_pinned = announcement.is_pinned
  announceDialogVisible.value = true
}


async function handleSaveAnnouncement() {
  const valid = await announceFormRef.value?.validate().catch(() => false)
  if (!valid) return

  isSavingAnnounce.value = true
  try {
    if (isEditing.value) {
      const updated = await updateAnnouncement(editingAnnouncementId.value, {
        title: announceForm.title,
        content: announceForm.content,
        is_pinned: announceForm.is_pinned,
      })
      const idx = announcements.value.findIndex((a) => a.id === updated.id)
      if (idx !== -1) announcements.value[idx] = updated
      ElMessage.success('公告修改成功')
    } else {
      const created = await createAnnouncement(clubId.value, {
        title: announceForm.title,
        content: announceForm.content,
        is_pinned: announceForm.is_pinned,
      })
      announcements.value.unshift(created)
      ElMessage.success('公告发布成功')
    }
    announceDialogVisible.value = false
  } catch (error) {
    ElMessage.error(
      error instanceof ApiRequestError ? error.message : '操作失败',
    )
  } finally {
    isSavingAnnounce.value = false
  }
}


async function handleDeleteAnnouncement(announcement: Announcement) {
  try {
    await ElMessageBox.confirm(
      `确定要删除公告「${announcement.title}」吗？删除后成员将不再可见。`,
      '确认删除',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }

  deletingAnnounceId.value = announcement.id
  try {
    await deleteAnnouncement(announcement.id)
    //更新本地状态
    const idx = announcements.value.findIndex((a) => a.id === announcement.id)
    if (idx !== -1) {
      announcements.value[idx] = {
        ...announcements.value[idx],
        status: '已删除',
      }
    }
    ElMessage.success('公告已删除')
  } catch (error) {
    ElMessage.error(
      error instanceof ApiRequestError ? error.message : '删除失败',
    )
  } finally {
    deletingAnnounceId.value = null
  }
}


// ── S10 帖子管理（置顶） ──────────────────────────────────

const posts = ref<Post[]>([])
const isLoadingPosts = ref(false)
const pinningPostId = ref<number | null>(null)


async function loadPosts() {
  isLoadingPosts.value = true
  try {
    const data = await listPosts(clubId.value)
    posts.value = data.items
  } catch {
    posts.value = []
  } finally {
    isLoadingPosts.value = false
  }
}


async function handleTogglePin(post: Post) {
  pinningPostId.value = post.id
  try {
    const updated = await pinPost(post.id, { is_pinned: !post.is_pinned })
    const idx = posts.value.findIndex((p) => p.id === post.id)
    if (idx !== -1) posts.value[idx] = updated
    ElMessage.success(updated.is_pinned ? '帖子已置顶' : '已取消置顶')
  } catch (error) {
    ElMessage.error(
      error instanceof ApiRequestError ? error.message : '操作失败',
    )
  } finally {
    pinningPostId.value = null
  }
}


function onTogglePin(row: unknown) {
  handleTogglePin(row as Post)
}


function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN')
}


async function saveIntro() {
  if (!editFormRef.value) return
  try {
    await editFormRef.value.validate()
  } catch {
    return
  }

  isSaving.value = true
  try {
    const updated = await updateLeaderClub(clubId.value, {
      introduction: editForm.introduction,
    })
    club.value = updated
    ElMessage.success('社团简介保存成功')
  } catch (error) {
    ElMessage.error(
      error instanceof ApiRequestError ? error.message : '保存失败',
    )
  } finally {
    isSaving.value = false
  }
}


function roleLabel(role: string): string {
  return role === 'leader' ? '负责人' : '普通成员'
}


function accountStatusLabel(status: string): string {
  return status === 'active' ? '正常' : '已停用'
}


// ── S14 意见反馈管理 ────────────────────────────────────────

const feedbacks = ref<Feedback[]>([])
const isLoadingFeedbacks = ref(false)
const feedbackPage = ref(1)
const feedbackPageSize = ref(20)
const feedbackTotal = ref(0)
const processingFeedbackId = ref<number | null>(null)
const showProcessDialog = ref(false)
const processForm = reactive({
  processing_note: '',
})
const isProcessing = ref(false)


async function loadFeedbacks() {
  if (!clubId.value) return
  isLoadingFeedbacks.value = true
  try {
    const data = await getLeaderFeedbacks(
      clubId.value,
      feedbackPage.value,
      feedbackPageSize.value,
    )
    feedbacks.value = data.items
    feedbackTotal.value = data.total
  } catch {
    feedbacks.value = []
    feedbackTotal.value = 0
  } finally {
    isLoadingFeedbacks.value = false
  }
}


function handleFeedbackPageChange(page: number) {
  feedbackPage.value = page
  loadFeedbacks()
}


function openProcessDialog(feedback: Feedback) {
  processingFeedbackId.value = feedback.id
  processForm.processing_note = ''
  showProcessDialog.value = true
}


function onProcess(row: unknown) {
  openProcessDialog(row as Feedback)
}


async function handleProcessFeedback() {
  if (processingFeedbackId.value === null) return
  isProcessing.value = true
  try {
    const updated = await processFeedback(processingFeedbackId.value, {
      processing_note: processForm.processing_note.trim() || undefined,
    })
    ElMessage.success('反馈处理成功')
    //替换列表中的反馈
    const idx = feedbacks.value.findIndex(f => f.id === updated.id)
    if (idx !== -1) feedbacks.value[idx] = updated
    showProcessDialog.value = false
  } catch (error) {
    if (error instanceof ApiRequestError) {
      ElMessage.error(error.message)
    } else {
      ElMessage.error('处理失败，请稍后重试')
    }
  } finally {
    isProcessing.value = false
  }
}


onMounted(() => {
  loadClub().then(() => {
    if (club.value) {
      loadMembers()
      loadAnnouncements()
      loadPosts()
      loadFeedbacks()
    }
  })
})
</script>

<template>
  <main class="student-page">
    <header class="admin-header">
      <div class="brand-mark" aria-hidden="true">社</div>
      <div>
        <p class="eyebrow">校园社团智能管理系统</p>
        <p class="header-title">社团管理</p>
      </div>
    </header>

    <div class="student-content">
      <section class="page-heading">
        <p class="section-kicker">负责人工作台</p>
        <h1>{{ club?.name ?? '社团管理' }}</h1>
        <p>
          <el-tag type="warning" effect="light" size="small">
            正在管理此社团
          </el-tag>
          <el-button
            text
            size="small"
            style="margin-left: 12px"
            @click="emit('navigate', '/student/memberships')"
          >
            ← 返回我的社团
          </el-button>
        </p>
      </section>

      <el-alert
        v-if="errorMessage"
        type="error"
        :title="errorMessage"
        :closable="false"
        show-icon
        class="form-alert"
      />

      <el-card v-if="isLoading" v-loading="isLoading" class="data-card" shadow="never" />

      <template v-else-if="club">
        <!-- 编辑社团简介 -->
        <el-card class="data-card" shadow="never">
          <template #header>社团信息维护</template>

          <el-form
            ref="editFormRef"
            :model="editForm"
            :rules="editRules"
            label-position="top"
            @submit.prevent="saveIntro"
          >
            <el-form-item label="社团简介" prop="introduction">
              <el-input
                v-model="editForm.introduction"
                type="textarea"
                :rows="5"
                placeholder="请输入社团简介"
              />
            </el-form-item>

            <el-form-item>
              <el-button type="primary" :loading="isSaving" @click="saveIntro">
                保存简介
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <!-- 成员列表 -->
        <el-card class="data-card" shadow="never" style="margin-top: 20px">
          <template #header>当前在社成员</template>

          <div v-loading="isLoadingMembers">
            <template v-if="members.length === 0 && !isLoadingMembers">
              <el-empty description="暂无成员" :image-size="60" />
            </template>
            <el-table v-else :data="members" stripe>
              <el-table-column label="用户名" prop="user.username" width="120" />
              <el-table-column label="姓名" prop="user.name" width="100" />
              <el-table-column label="手机号" prop="user.phone" width="130" />
              <el-table-column label="专业班级" prop="user.major_class" />
              <el-table-column label="账号状态" width="90">
                <template #default="{ row }">
                  <el-tag
                    :type="row.user.account_status === 'active' ? 'success' : 'danger'"
                    effect="light"
                    size="small"
                  >
                    {{ accountStatusLabel(row.user.account_status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="社团身份" width="90">
                <template #default="{ row }">
                  <el-tag
                    :type="row.club_role === 'leader' ? 'warning' : 'info'"
                    effect="light"
                    size="small"
                  >
                    {{ roleLabel(row.club_role) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="80">
                <template #default="{ row }">
                  <el-button
                    v-if="row.club_role === 'member'"
                    type="danger"
                    size="small"
                    text
                    :loading="removingId === row.id"
                    @click="onRemove(row)"
                  >
                    移除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-card>

        <!-- 招新管理入口 -->
        <el-card class="data-card" shadow="never" style="margin-top: 20px">
          <div style="display: flex; justify-content: space-between; align-items: center">
            <h3 style="margin: 0; font-size: 16px">招新管理</h3>
            <el-button
              type="primary"
              @click="emit('navigate', `/leader/clubs/${clubId}/recruitments`)"
            >
              管理招新
            </el-button>
          </div>
        </el-card>

        <!-- 入社申请审核入口 -->
        <el-card class="data-card" shadow="never" style="margin-top: 20px">
          <div style="display: flex; justify-content: space-between; align-items: center">
            <h3 style="margin: 0; font-size: 16px">入社申请审核</h3>
            <el-button
              type="primary"
              @click="emit('navigate', `/leader/clubs/${clubId}/applications`)"
            >
              审阅申请
            </el-button>
          </div>
        </el-card>

        <!-- S09 公告管理 -->
        <el-card class="data-card" shadow="never" style="margin-top: 20px">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span style="font-weight: 600">公告管理</span>
              <el-button type="primary" size="small" @click="openCreateDialog">
                发布公告
              </el-button>
            </div>
          </template>

          <div v-loading="isLoadingAnnouncements">
            <template v-if="announcements.length === 0 && !isLoadingAnnouncements">
              <el-empty description="暂无公告" :image-size="60" />
            </template>
            <el-table v-else :data="announcements" stripe>
              <el-table-column label="标题" prop="title" min-width="160">
                <template #default="{ row }">
                  <div class="announce-title-cell">
                    <el-tag
                      v-if="row.is_pinned && row.status === '正常'"
                      type="warning"
                      size="small"
                      effect="light"
                    >
                      置顶
                    </el-tag>
                    <span>{{ row.title }}</span>
                  </div>
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
              <el-table-column label="发布时间" width="170">
                <template #default="{ row }">
                  <span style="font-size: 13px; color: #909399">
                    {{ formatDateTime(row.published_at) }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="140">
                <template #default="{ row }">
                  <el-button
                    v-if="row.status === '正常'"
                    type="primary"
                    size="small"
                    text
                    @click="onEditAnnounce(row)"
                  >
                    编辑
                  </el-button>
                  <el-button
                    v-if="row.status === '正常'"
                    type="danger"
                    size="small"
                    text
                    :loading="deletingAnnounceId === row.id"
                    @click="onDeleteAnnounce(row)"
                  >
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-card>

        <!-- S10 帖子管理 -->
        <el-card class="data-card" shadow="never" style="margin-top: 20px">
          <template #header>
            <span style="font-weight: 600">帖子管理</span>
          </template>

          <div v-loading="isLoadingPosts">
            <template v-if="posts.length === 0 && !isLoadingPosts">
              <el-empty description="暂无帖子" :image-size="60" />
            </template>
            <el-table v-else :data="posts" stripe>
              <el-table-column label="标题" prop="title" min-width="160">
                <template #default="{ row }">
                  <div class="post-title-cell">
                    <el-tag
                      v-if="row.is_pinned && row.status === '正常'"
                      type="warning"
                      size="small"
                      effect="light"
                    >
                      置顶
                    </el-tag>
                    <span>{{ row.title }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="作者" width="120">
                <template #default="{ row }">
                  {{ row.author.username }}
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
              <el-table-column label="操作" width="120">
                <template #default="{ row }">
                  <el-button
                    v-if="row.status === '正常'"
                    :type="row.is_pinned ? 'info' : 'primary'"
                    size="small"
                    text
                    :loading="pinningPostId === row.id"
                    @click="onTogglePin(row)"
                  >
                    {{ row.is_pinned ? '取消置顶' : '置顶' }}
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-card>

        <!-- S14 反馈管理 -->
        <el-card class="data-card" shadow="never" style="margin-top: 20px">
          <template #header>
            <span style="font-weight: 600">反馈管理</span>
          </template>

          <div v-if="isLoadingFeedbacks" v-loading="true" style="min-height: 120px" />

          <template v-else-if="feedbacks.length === 0">
            <el-empty description="暂无反馈" :image-size="60" />
          </template>

          <template v-else>
            <el-table :data="feedbacks" stripe>
              <el-table-column label="提交人" width="100">
                <template #default="{ row }">
                  {{ row.submitter.username }}
                </template>
              </el-table-column>
              <el-table-column label="反馈内容" min-width="200">
                <template #default="{ row }">
                  <div style="white-space: pre-wrap; word-break: break-all">
                    {{ row.content.length > 100 ? row.content.slice(0, 100) + '…' : row.content }}
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="90">
                <template #default="{ row }">
                  <el-tag
                    :type="row.status === '已处理' ? 'success' : 'warning'"
                    effect="light"
                    size="small"
                  >
                    {{ row.status }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="提交时间" width="160">
                <template #default="{ row }">
                  {{ formatDateTime(row.submitted_at) }}
                </template>
              </el-table-column>
              <el-table-column label="处理说明" min-width="120">
                <template #default="{ row }">
                  <span v-if="row.processing_note">{{ row.processing_note }}</span>
                  <span v-else style="color: #c0c4cc">—</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="90">
                <template #default="{ row }">
                  <el-button
                    v-if="row.status === '待处理'"
                    type="primary"
                    size="small"
                    text
                    @click="onProcess(row)"
                  >
                    处理
                  </el-button>
                  <span v-else style="color: #c0c4cc; font-size: 13px">已处理</span>
                </template>
              </el-table-column>
            </el-table>

            <div style="display: flex; justify-content: center; margin-top: 16px">
              <el-pagination
                v-model:current-page="feedbackPage"
                :page-size="feedbackPageSize"
                :total="feedbackTotal"
                layout="total, prev, pager, next"
                @current-change="handleFeedbackPageChange"
              />
            </div>
          </template>
        </el-card>

        <!-- 处理反馈弹窗 -->
        <el-dialog
          v-model="showProcessDialog"
          title="处理反馈"
          width="480px"
          :close-on-click-modal="false"
        >
          <div>
            <label style="display: block; margin-bottom: 8px; font-weight: 500">
              处理说明（可选）
            </label>
            <el-input
              v-model="processForm.processing_note"
              type="textarea"
              :rows="4"
              maxlength="1000"
              show-word-limit
              placeholder="填写处理说明…"
            />
          </div>

          <template #footer>
            <el-button @click="showProcessDialog = false">取消</el-button>
            <el-button type="primary" :loading="isProcessing" @click="handleProcessFeedback">
              确认处理
            </el-button>
          </template>
        </el-dialog>

        <!-- 公告弹窗 -->
        <el-dialog
          v-model="announceDialogVisible"
          :title="announceDialogTitle"
          width="560px"
          :close-on-click-modal="false"
        >
          <el-form
            ref="announceFormRef"
            :model="announceForm"
            :rules="announceFormRules"
            label-position="top"
          >
            <el-form-item label="公告标题" prop="title">
              <el-input
                v-model="announceForm.title"
                maxlength="200"
                show-word-limit
                placeholder="请输入公告标题"
              />
            </el-form-item>
            <el-form-item label="公告内容" prop="content">
              <el-input
                v-model="announceForm.content"
                type="textarea"
                :rows="6"
                placeholder="请输入公告内容"
              />
            </el-form-item>
            <el-form-item label="置顶">
              <el-switch v-model="announceForm.is_pinned" />
              <span style="margin-left: 8px; color: #909399; font-size: 13px">
                置顶公告将在列表顶部显示
              </span>
            </el-form-item>
          </el-form>

          <template #footer>
            <el-button @click="announceDialogVisible = false">取消</el-button>
            <el-button type="primary" :loading="isSavingAnnounce" @click="handleSaveAnnouncement">
              {{ isEditing ? '保存修改' : '发布' }}
            </el-button>
          </template>
        </el-dialog>
      </template>
    </div>
  </main>
</template>

<style scoped>
.announce-title-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.post-title-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
