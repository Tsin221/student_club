<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { ApiRequestError, getProfile } from '../api/auth'
import { getStudentOverview } from '../api/clubs'
import type { JoinApplication, StudentOverview } from '../types/club'
import type { SelfUser } from '../types/user'


const emit = defineEmits<{
  navigate: [path: string]
}>()

const isLoading = ref(true)
const errorMessage = ref('')
const profile = ref<SelfUser | null>(null)
const showUpdateSuccess = ref(false)

// ── S19：数据概览 ──────────────────────────────────────────

const overview = ref<StudentOverview | null>(null)
const isLoadingOverview = ref(false)
const overviewError = ref('')

async function loadOverview() {
  isLoadingOverview.value = true
  overviewError.value = ''
  try {
    overview.value = await getStudentOverview()
  } catch (error) {
    if (error instanceof ApiRequestError) {
      overviewError.value = error.message
    } else {
      overviewError.value = '数据概览加载失败'
    }
  } finally {
    isLoadingOverview.value = false
  }
}

function applicationStatusType(status: string): 'warning' | 'success' | 'info' {
  if (status === '待审核') return 'warning'
  if (status === '已通过') return 'success'
  return 'info'
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('zh-CN')
}

const initials = computed(() => profile.value?.name.slice(0, 1) || '同')
const registeredAt = computed(() => {
  if (!profile.value) {
    return ''
  }
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'long',
    timeStyle: 'short',
    timeZone: 'Asia/Shanghai',
  }).format(new Date(profile.value.registered_at))
})


function dismissUpdateSuccess() {
  showUpdateSuccess.value = false
}


async function loadProfile() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    profile.value = await getProfile()
  } catch (error) {
    if (error instanceof ApiRequestError) {
      if (error.code === 'UNAUTHENTICATED') {
        emit('navigate', '/login?reason=session')
        return
      }
      if (error.code === 'ACCOUNT_DISABLED') {
        emit('navigate', '/login?reason=disabled')
        return
      }
      errorMessage.value = error.message
    } else {
      errorMessage.value = '本人资料加载失败，请稍后重试'
    }
  } finally {
    isLoading.value = false
  }
}


onMounted(() => {
  if (window.location.search.includes('updated=1')) {
    showUpdateSuccess.value = true
  }
  loadProfile()
  loadOverview()
})
</script>

<template>
  <main class="student-page">
    <header class="student-header">
      <div class="brand-mark" aria-hidden="true">社</div>
      <div>
        <p class="eyebrow">校园社团智能管理系统</p>
        <p class="header-title">学生个人中心</p>
      </div>
    </header>

    <div class="student-content">
      <section class="page-heading" aria-labelledby="profile-title">
        <p class="section-kicker">个人中心</p>
        <h1 id="profile-title">本人资料</h1>
        <p>这里的信息来自当前服务端登录会话，刷新页面后会重新读取。</p>
      </section>

      <el-alert
        v-if="showUpdateSuccess"
        type="success"
        title="资料修改成功"
        :closable="true"
        show-icon
        class="form-alert"
        @close="dismissUpdateSuccess"
      />

      <el-card
        v-loading="isLoading"
        class="profile-card"
        shadow="never"
        aria-live="polite"
      >
        <template v-if="errorMessage">
          <el-result
            icon="error"
            title="资料加载失败"
            :sub-title="errorMessage"
          >
            <template #extra>
              <el-button type="primary" @click="loadProfile">
                重新加载
              </el-button>
            </template>
          </el-result>
        </template>

        <template v-else-if="profile">
          <div class="profile-summary">
            <div class="profile-avatar" aria-label="默认头像">
              {{ initials }}
            </div>
            <div class="profile-summary-body">
              <div class="profile-name-row">
                <h2>{{ profile.name }}</h2>
                <el-tag type="primary" effect="light">学生用户</el-tag>
                <el-tag type="success" effect="light">账号正常</el-tag>
              </div>
              <p>@{{ profile.username }}</p>
            </div>
            <div class="profile-actions">
              <el-button
                type="primary"
                plain
                @click="emit('navigate', '/student/clubs')"
              >
                社团广场
              </el-button>
              <el-button
                type="primary"
                plain
                @click="emit('navigate', '/student/memberships')"
              >
                我的社团
              </el-button>
              <el-button
                type="primary"
                plain
                @click="emit('navigate', '/student/applications')"
              >
                我的申请
              </el-button>
              <el-button
                type="primary"
                plain
                @click="emit('navigate', '/student/notifications')"
              >
                我的通知
              </el-button>
              <el-button
                type="primary"
                plain
                @click="emit('navigate', '/student/evaluations')"
              >
                我的评价
              </el-button>
              <el-button
                type="primary"
                plain
                @click="emit('navigate', '/student/feedbacks')"
              >
                我的反馈
              </el-button>
              <el-button
                type="primary"
                @click="emit('navigate', '/student/profile/edit')"
              >
                编辑资料
              </el-button>
            </div>
          </div>

          <el-divider />

          <el-descriptions :column="2" border>
            <el-descriptions-item label="用户名">
              {{ profile.username }}
            </el-descriptions-item>
            <el-descriptions-item label="姓名">
              {{ profile.name }}
            </el-descriptions-item>
            <el-descriptions-item label="手机号">
              {{ profile.phone }}
            </el-descriptions-item>
            <el-descriptions-item label="年级">
              {{ profile.grade }}
            </el-descriptions-item>
            <el-descriptions-item label="专业班级" :span="2">
              {{ profile.major_class }}
            </el-descriptions-item>
            <el-descriptions-item label="注册时间" :span="2">
              {{ registeredAt }}
            </el-descriptions-item>
          </el-descriptions>
        </template>
      </el-card>

      <!-- S19：数据概览 -->
      <section class="page-heading" style="margin-top: 28px" aria-labelledby="overview-title">
        <p class="section-kicker">数据概览</p>
        <h1 id="overview-title">我的概览</h1>
      </section>

      <el-card
        v-loading="isLoadingOverview"
        class="data-card"
        shadow="never"
        aria-live="polite"
      >
        <template v-if="overviewError">
          <el-result icon="error" title="概览加载失败" :sub-title="overviewError">
            <template #extra>
              <el-button type="primary" @click="loadOverview">重新加载</el-button>
            </template>
          </el-result>
        </template>

        <template v-else-if="overview">
          <!-- 加入社团数卡片 -->
          <div class="overview-stats">
            <div
              class="stat-card"
              role="button"
              tabindex="0"
              @click="emit('navigate', '/student/memberships')"
              @keydown.enter="emit('navigate', '/student/memberships')"
            >
              <div class="stat-number">{{ overview.joined_normal_club_count }}</div>
              <div class="stat-label">当前加入社团</div>
              <div class="stat-hint">点击查看详情</div>
            </div>
          </div>

          <el-divider />

          <!-- 入社申请记录 -->
          <div style="margin-top: 8px">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px">
              <h3 style="margin: 0; font-size: 15px; font-weight: 600">入社申请记录</h3>
              <el-button
                v-if="overview.join_applications.length > 0"
                text
                type="primary"
                size="small"
                @click="emit('navigate', '/student/applications')"
              >
                查看全部
              </el-button>
            </div>

            <el-empty
              v-if="overview.join_applications.length === 0"
              description="暂无申请记录"
              :image-size="48"
            />

            <el-table
              v-else
              :data="overview.join_applications.slice(0, 5)"
              stripe
              size="small"
            >
              <el-table-column label="社团" min-width="120">
                <template #default="{ row }">
                  {{ row.club.name }}
                </template>
              </el-table-column>
              <el-table-column label="招新标题" min-width="140">
                <template #default="{ row }">
                  {{ row.recruitment.title }}
                </template>
              </el-table-column>
              <el-table-column label="申请状态" width="90">
                <template #default="{ row }">
                  <el-tag
                    :type="applicationStatusType(row.status)"
                    effect="light"
                    size="small"
                  >
                    {{ row.status }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="申请时间" width="110">
                <template #default="{ row }">
                  <span style="font-size: 13px; color: #909399">
                    {{ formatDate(row.applied_at) }}
                  </span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </template>
      </el-card>
    </div>
  </main>
</template>

<style scoped>
.overview-stats {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.stat-card {
  flex: 1;
  min-width: 140px;
  padding: 20px 24px;
  border: 1px solid var(--el-border-color-light, #e4e7ed);
  border-radius: 8px;
  text-align: center;
  cursor: pointer;
  transition:
    border-color 0.2s,
    box-shadow 0.2s;
  background: #fff;
}

.stat-card:hover {
  border-color: var(--el-color-primary, #409eff);
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.15);
}

.stat-number {
  font-size: 32px;
  font-weight: 700;
  color: var(--el-color-primary, #409eff);
  line-height: 1.2;
}

.stat-label {
  margin-top: 8px;
  font-size: 14px;
  color: #606266;
}

.stat-hint {
  margin-top: 4px;
  font-size: 12px;
  color: #c0c4cc;
}
</style>
