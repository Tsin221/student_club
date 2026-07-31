<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  ElMessage,
  ElMessageBox,
  type FormInstance,
  type FormRules,
} from 'element-plus'

import { ApiRequestError } from '../api/auth'
import {
  addClubLeader,
  cancelClub,
  getClubDetail,
  getLeaderMembers,
  removeClubLeader,
  updateAdminClub,
} from '../api/clubs'
import {
  CLUB_CATEGORIES,
  type Club,
  type ClubCategory,
  type MembershipForLeader,
} from '../types/club'


const emit = defineEmits<{
  navigate: [path: string]
}>()

//解析路由中的 clubId
const clubId = computed(() => {
  const match = window.location.pathname.match(/^\/admin\/clubs\/(\d+)/)
  return match ? Number(match[1]) : 0
})

// ── 社团信息 ──────────────────────────────────────────────

const isLoading = ref(true)
const errorMessage = ref('')
const club = ref<Club | null>(null)

const editFormRef = ref<FormInstance>()
const isSaving = ref(false)
const isCancelling = ref(false)

const editForm = reactive({
  name: '',
  category: '' as ClubCategory | '',
  introduction: '',
})

const editRules: FormRules<typeof editForm> = {
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
}

// ── 负责人管理 ────────────────────────────────────────────

const members = ref<MembershipForLeader[]>([])
const isLoadingMembers = ref(false)
const isAddingLeader = ref(false)
const isRemovingLeader = ref<number | null>(null)

const leaders = computed(() =>
  members.value.filter((m) => m.club_role === 'leader'),
)
const ordinaryMembers = computed(() =>
  members.value.filter((m) => m.club_role === 'member'),
)

// ── 数据加载 ──────────────────────────────────────────────

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
    editForm.name = data.name
    editForm.category = data.category
    editForm.introduction = data.introduction
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
      //管理员没有负责人身份，使用管理员接口可能存在替代方案
      //当前通过 leader 成员接口获取在社成员；管理员可以查看
    }
    members.value = []
  } finally {
    isLoadingMembers.value = false
  }
}

// ── 编辑 ──────────────────────────────────────────────────

async function saveEdit() {
  if (!editFormRef.value) return
  try {
    await editFormRef.value.validate()
  } catch {
    return
  }

  isSaving.value = true
  try {
    const updated = await updateAdminClub(clubId.value, {
      name: editForm.name,
      category: editForm.category,
      introduction: editForm.introduction,
    })
    club.value = updated
    ElMessage.success('社团信息保存成功')
  } catch (error) {
    ElMessage.error(
      error instanceof ApiRequestError ? error.message : '保存失败',
    )
  } finally {
    isSaving.value = false
  }
}

// ── 注销 ──────────────────────────────────────────────────

async function doCancel() {
  try {
    await ElMessageBox.confirm(
      '注销后学生将无法访问该社团，且不可恢复。确定要继续吗？',
      '确认注销社团',
      {
        confirmButtonText: '确认注销',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      },
    )
  } catch {
    return
  }

  isCancelling.value = true
  try {
    const updated = await cancelClub(clubId.value)
    club.value = updated
    ElMessage.success('社团已注销')
  } catch (error) {
    ElMessage.error(
      error instanceof ApiRequestError ? error.message : '注销失败',
    )
  } finally {
    isCancelling.value = false
  }
}

// ── 负责人管理 ────────────────────────────────────────────

async function promoteToLeader(membershipId: number) {
  isAddingLeader.value = true
  try {
    await addClubLeader(clubId.value, membershipId)
    ElMessage.success('已提升为负责人')
    loadMembers()
  } catch (error) {
    ElMessage.error(
      error instanceof ApiRequestError ? error.message : '操作失败',
    )
  } finally {
    isAddingLeader.value = false
  }
}


async function demoteLeader(membershipId: number) {
  isRemovingLeader.value = membershipId
  try {
    await removeClubLeader(clubId.value, membershipId)
    ElMessage.success('已降级为普通成员')
    loadMembers()
  } catch (error) {
    ElMessage.error(
      error instanceof ApiRequestError ? error.message : '操作失败',
    )
  } finally {
    isRemovingLeader.value = null
  }
}

// ── 格式化 ────────────────────────────────────────────────

function statusTagType(status: string): 'success' | 'info' {
  return status === 'normal' ? 'success' : 'info'
}

function statusLabel(status: string): string {
  return status === 'normal' ? '正常' : '已注销'
}

function formatDate(isoString: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'long',
    timeStyle: 'short',
    timeZone: 'Asia/Shanghai',
  }).format(new Date(isoString))
}


onMounted(() => {
  loadClub().then(() => {
    if (club.value?.status === 'normal') {
      loadMembers()
    }
  })
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
      <section class="page-heading">
        <p class="section-kicker">社团管理</p>
        <h1>{{ club?.name ?? '社团详情' }}</h1>
        <p>
          <el-button text size="small" @click="emit('navigate', '/admin/clubs')">
            ← 返回社团列表
          </el-button>
        </p>
      </section>

      <!-- 错误 -->
      <el-alert
        v-if="errorMessage"
        type="error"
        :title="errorMessage"
        :closable="false"
        show-icon
        class="form-alert"
      />

      <!-- 加载 -->
      <el-card v-if="isLoading" v-loading="isLoading" class="data-card" shadow="never" />

      <template v-else-if="club">
        <!-- 社团信息编辑 -->
        <el-card class="data-card" shadow="never">
          <template #header>
            <span>社团信息</span>
            <el-tag
              :type="statusTagType(club.status)"
              effect="light"
              size="small"
              style="margin-left: 12px"
            >
              {{ statusLabel(club.status) }}
            </el-tag>
            <span style="margin-left: 12px; font-size: 13px; color: var(--muted)">
              创建于 {{ formatDate(club.created_at) }}
            </span>
          </template>

          <template v-if="club.status === 'normal'">
            <el-form
              ref="editFormRef"
              :model="editForm"
              :rules="editRules"
              label-position="top"
              @submit.prevent="saveEdit"
            >
              <el-form-item label="社团名称" prop="name">
                <el-input
                  v-model="editForm.name"
                  maxlength="100"
                  show-word-limit
                />
              </el-form-item>

              <el-form-item label="社团类别" prop="category">
                <el-select v-model="editForm.category" style="width: 100%">
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
                  v-model="editForm.introduction"
                  type="textarea"
                  :rows="4"
                />
              </el-form-item>

              <el-form-item>
                <el-button type="primary" :loading="isSaving" @click="saveEdit">
                  保存修改
                </el-button>
              </el-form-item>
            </el-form>

            <!-- 注销按钮 -->
            <el-divider />
            <div style="text-align: right">
              <el-button
                type="danger"
                :loading="isCancelling"
                @click="doCancel"
              >
                注销社团
              </el-button>
            </div>
          </template>

          <template v-else>
            <el-result icon="info" title="社团已注销" sub-title="此社团已注销，无法编辑" />
          </template>
        </el-card>

        <!-- 负责人管理 -->
        <el-card
          v-if="club.status === 'normal'"
          class="data-card"
          shadow="never"
          style="margin-top: 20px"
        >
          <template #header>负责人管理</template>

          <div v-loading="isLoadingMembers">
            <!-- 当前负责人 -->
            <h3 style="margin-bottom: 12px">当前负责人</h3>
            <template v-if="leaders.length === 0 && !isLoadingMembers">
              <el-empty description="暂无负责人" :image-size="60" />
            </template>
            <el-table v-else :data="leaders" stripe size="small">
              <el-table-column label="用户名" prop="user.username" />
              <el-table-column label="姓名" prop="user.name" />
              <el-table-column label="专业班级" prop="user.major_class" />
              <el-table-column label="操作" width="120">
                <template #default="{ row }">
                  <el-popconfirm
                    title="确定要取消该成员的负责人身份吗？"
                    @confirm="demoteLeader(row.id)"
                  >
                    <template #reference>
                      <el-button
                        type="danger"
                        size="small"
                        text
                        :loading="isRemovingLeader === row.id"
                      >
                        降级
                      </el-button>
                    </template>
                  </el-popconfirm>
                </template>
              </el-table-column>
            </el-table>

            <!-- 可提升为负责人的普通成员 -->
            <h3 style="margin: 20px 0 12px">当前普通成员</h3>
            <template v-if="ordinaryMembers.length === 0 && !isLoadingMembers">
              <el-empty description="暂无普通成员" :image-size="60" />
            </template>
            <el-table v-else :data="ordinaryMembers" stripe size="small">
              <el-table-column label="用户名" prop="user.username" />
              <el-table-column label="姓名" prop="user.name" />
              <el-table-column label="专业班级" prop="user.major_class" />
              <el-table-column label="操作" width="120">
                <template #default="{ row }">
                  <el-button
                    type="primary"
                    size="small"
                    text
                    :loading="isAddingLeader"
                    @click="promoteToLeader(row.id)"
                  >
                    提升为负责人
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-card>
      </template>
    </div>
  </main>
</template>
