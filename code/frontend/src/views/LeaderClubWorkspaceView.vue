<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'

import { ApiRequestError } from '../api/auth'
import {
  getClubDetail,
  getLeaderMembers,
  updateLeaderClub,
} from '../api/clubs'
import type { Club, MembershipForLeader } from '../types/club'


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


onMounted(() => {
  loadClub().then(() => {
    if (club.value) loadMembers()
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
            </el-table>
          </div>
        </el-card>
      </template>
    </div>
  </main>
</template>
