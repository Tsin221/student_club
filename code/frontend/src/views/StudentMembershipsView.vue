<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { ApiRequestError } from '../api/auth'
import { getMyMemberships } from '../api/clubs'
import type { MyMembership } from '../types/club'


const emit = defineEmits<{
  navigate: [path: string]
}>()

// ── 状态 ──────────────────────────────────────────────────

const isLoading = ref(true)
const errorMessage = ref('')
const memberships = ref<MyMembership[]>([])

// ── 数据加载 ──────────────────────────────────────────────

async function loadMemberships() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const data = await getMyMemberships()
    memberships.value = data.items
  } catch (error) {
    if (error instanceof ApiRequestError) {
      if (error.code === 'UNAUTHENTICATED') {
        emit('navigate', '/login?reason=session')
        return
      }
      errorMessage.value = error.message
    } else {
      errorMessage.value = '我的社团加载失败，请稍后重试'
    }
  } finally {
    isLoading.value = false
  }
}


function statusLabel(status: string): string {
  const map: Record<string, string> = {
    active: '在社',
    exited: '已退出',
    removed: '已移除',
  }
  return map[status] ?? status
}


function statusTagType(status: string): 'success' | 'warning' | 'danger' {
  const map: Record<string, 'success' | 'warning' | 'danger'> = {
    active: 'success',
    exited: 'warning',
    removed: 'danger',
  }
  return map[status] ?? 'warning'
}


function roleLabel(role: string): string {
  return role === 'leader' ? '负责人' : '普通成员'
}


function roleTagType(role: string): 'primary' | 'warning' {
  return role === 'leader' ? 'warning' : 'primary'
}


onMounted(() => {
  loadMemberships()
})
</script>

<template>
  <main class="student-page">
    <header class="student-header">
      <div class="brand-mark" aria-hidden="true">社</div>
      <div>
        <p class="eyebrow">校园社团智能管理系统</p>
        <p class="header-title">我的社团</p>
      </div>
    </header>

    <div class="student-content">
      <section class="page-heading" aria-labelledby="memberships-title">
        <p class="section-kicker">成员关系</p>
        <h1 id="memberships-title">我的社团</h1>
        <p>查看你当前加入和历史参与的社团。</p>
      </section>

      <!-- 错误状态 -->
      <el-alert
        v-if="errorMessage"
        type="error"
        :title="errorMessage"
        :closable="false"
        show-icon
        class="form-alert"
      />

      <!-- 加载与列表 -->
      <el-card
        v-loading="isLoading"
        class="data-card"
        shadow="never"
        aria-live="polite"
      >
        <template v-if="!errorMessage && memberships.length === 0 && !isLoading">
          <el-empty description="你还没有加入任何社团" />
        </template>

        <template v-else-if="!errorMessage">
          <el-table :data="memberships" style="width: 100%" stripe>
            <el-table-column label="社团 Logo" width="70">
              <template #default="{ row }">
                <div class="mini-logo">
                  <img
                    v-if="row.club.logo"
                    :src="row.club.logo"
                    :alt="row.club.name"
                    class="mini-logo-img"
                  >
                  <span v-else>{{ row.club.name?.charAt(0) ?? '?' }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="社团名称" min-width="140">
              <template #default="{ row }">
                {{ row.club.name }}
              </template>
            </el-table-column>
            <el-table-column prop="club.category" label="类别" width="100" />
            <el-table-column label="身份" width="100">
              <template #default="{ row }">
                <el-tag
                  :type="roleTagType(row.club_role)"
                  effect="light"
                  size="small"
                >
                  {{ roleLabel(row.club_role) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag
                  :type="statusTagType(row.member_status)"
                  effect="light"
                  size="small"
                >
                  {{ statusLabel(row.member_status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button
                  v-if="row.club_role === 'leader' && row.member_status === 'active' && row.club.status === 'normal'"
                  type="primary"
                  size="small"
                  text
                  @click="emit('navigate', `/leader/clubs/${row.club.id}`)"
                >
                  管理社团
                </el-button>
                <span
                  v-else-if="row.club.status === 'cancelled'"
                  style="font-size: 12px; color: var(--muted)"
                >
                  已注销
                </span>
              </template>
            </el-table-column>
          </el-table>
        </template>
      </el-card>
    </div>
  </main>
</template>

<style scoped>
.mini-logo {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  overflow: hidden;
  display: grid;
  place-items: center;
  background: var(--brand-100);
  color: var(--brand-700);
  font-weight: 750;
  font-size: 14px;
}

.mini-logo-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>
