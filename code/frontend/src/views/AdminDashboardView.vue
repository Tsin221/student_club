<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { ApiRequestError } from '../api/auth'
import { getAdminOverview } from '../api/clubs'
import type { AdminOverview } from '../types/club'


const emit = defineEmits<{
  navigate: [path: string]
}>()

const overview = ref<AdminOverview | null>(null)
const isLoading = ref(true)
const errorMessage = ref('')

async function loadOverview() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    overview.value = await getAdminOverview()
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
      errorMessage.value = '数据概览加载失败，请稍后重试'
    }
  } finally {
    isLoading.value = false
  }
}

const adminMenus = [
  { label: '用户管理', desc: '查看学生账号并重置密码', path: '/admin/users' },
  { label: '社团管理', desc: '创建、查看和注销社团', path: '/admin/clubs' },
  { label: '成员关系', desc: '查看所有社团成员关系', path: '/admin/memberships' },
  { label: '招新记录', desc: '查看全部招新活动', path: '/admin/recruitments' },
  { label: '入社申请', desc: '查看全部入社申请', path: '/admin/applications' },
  { label: '评价记录', desc: '查看所有社团评价', path: '/admin/evaluations' },
  { label: '帖子管理', desc: '查看和管理全部帖子', path: '/admin/posts' },
  { label: '回复管理', desc: '查看和管理全部回复', path: '/admin/replies' },
]

onMounted(() => {
  loadOverview()
})
</script>

<template>
  <main class="student-page">
    <header class="admin-header">
      <div class="brand-mark" aria-hidden="true">社</div>
      <div>
        <p class="eyebrow">校园社团智能管理系统</p>
        <p class="header-title">管理员工作台</p>
      </div>
    </header>

    <div class="student-content">
      <section class="page-heading">
        <p class="section-kicker">系统概览</p>
        <h1>数据概览</h1>
        <p>系统实时统计，不使用图表或趋势数据。</p>
      </section>

      <!-- 概览卡片 -->
      <el-card
        v-loading="isLoading"
        class="data-card"
        shadow="never"
        aria-live="polite"
      >
        <template v-if="errorMessage">
          <el-result
            icon="error"
            title="概览加载失败"
            :sub-title="errorMessage"
          >
            <template #extra>
              <el-button type="primary" @click="loadOverview">重新加载</el-button>
            </template>
          </el-result>
        </template>

        <template v-else-if="overview">
          <div class="overview-stats">
            <div class="stat-card">
              <div class="stat-number">{{ overview.user_count }}</div>
              <div class="stat-label">用户总数</div>
              <div class="stat-hint">仅学生用户</div>
            </div>
            <div class="stat-card">
              <div class="stat-number">{{ overview.normal_club_count }}</div>
              <div class="stat-label">正常社团</div>
              <div class="stat-hint">不含已注销</div>
            </div>
          </div>
        </template>
      </el-card>

      <!-- 管理入口 -->
      <section class="page-heading" style="margin-top: 28px">
        <p class="section-kicker">功能入口</p>
        <h2>管理功能</h2>
      </section>

      <div class="admin-menus-grid">
        <el-card
          v-for="menu in adminMenus"
          :key="menu.path"
          class="menu-card"
          shadow="never"
          @click="emit('navigate', menu.path)"
        >
          <h3 class="menu-label">{{ menu.label }}</h3>
          <p class="menu-desc">{{ menu.desc }}</p>
          <el-button type="primary" text size="small" style="margin-top: 8px">
            进入 →
          </el-button>
        </el-card>
      </div>
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
  min-width: 160px;
  padding: 24px;
  border: 1px solid var(--el-border-color-light, #e4e7ed);
  border-radius: 8px;
  text-align: center;
  background: #fff;
}

.stat-number {
  font-size: 36px;
  font-weight: 700;
  color: var(--el-color-primary, #409eff);
  line-height: 1.2;
}

.stat-label {
  margin-top: 8px;
  font-size: 15px;
  color: #303133;
  font-weight: 500;
}

.stat-hint {
  margin-top: 4px;
  font-size: 12px;
  color: #c0c4cc;
}

.admin-menus-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}

.menu-card {
  cursor: pointer;
  transition:
    border-color 0.2s,
    box-shadow 0.2s;
}

.menu-card:hover {
  border-color: var(--el-color-primary, #409eff);
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.12);
}

.menu-label {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.menu-desc {
  margin: 0;
  font-size: 13px;
  color: #909399;
  line-height: 1.5;
}
</style>
