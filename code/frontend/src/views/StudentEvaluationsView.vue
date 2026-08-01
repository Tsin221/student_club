<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'

import { ApiRequestError } from '../api/auth'
import { getMyEvaluations, updateEvaluation } from '../api/clubs'
import type { ClubEvaluation } from '../types/club'


const emit = defineEmits<{
  navigate: [path: string]
}>()

const isLoading = ref(true)
const errorMessage = ref('')
const evaluations = ref<ClubEvaluation[]>([])

//修改弹窗
const editDialogVisible = ref(false)
const editingEvaluation = ref<ClubEvaluation | null>(null)
const editFormRef = ref<FormInstance>()
const editForm = reactive({
  rating: 0,
  comment: '',
})
const isSubmitting = ref(false)
const editFormRules: FormRules<typeof editForm> = {
  rating: [
    { required: true, message: '请选择评分', trigger: 'change' },
  ],
}


async function loadEvaluations() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const data = await getMyEvaluations()
    evaluations.value = data.items
  } catch (error) {
    if (error instanceof ApiRequestError) {
      if (error.code === 'UNAUTHENTICATED') {
        emit('navigate', '/login?reason=session')
        return
      }
      errorMessage.value = error.message
    } else {
      errorMessage.value = '评价列表加载失败，请稍后重试'
    }
  } finally {
    isLoading.value = false
  }
}


function openEditDialog(evaluation: ClubEvaluation) {
  editingEvaluation.value = evaluation
  editForm.rating = evaluation.rating
  editForm.comment = evaluation.comment || ''
  editDialogVisible.value = true
}


async function handleUpdate() {
  if (!editingEvaluation.value) return

  const valid = await editFormRef.value?.validate().catch(() => false)
  if (!valid) return

  isSubmitting.value = true
  try {
    const updated = await updateEvaluation(editingEvaluation.value.id, {
      rating: editForm.rating,
      comment: editForm.comment.trim() || undefined,
    })
    ElMessage.success('评价修改成功')

    //替换列表中的评价
    const idx = evaluations.value.findIndex(e => e.id === updated.id)
    if (idx !== -1) evaluations.value[idx] = updated

    editDialogVisible.value = false
  } catch (error) {
    if (error instanceof ApiRequestError) {
      ElMessage.error(error.message)
    } else {
      ElMessage.error('修改失败，请稍后重试')
    }
  } finally {
    isSubmitting.value = false
  }
}


function goBack() {
  emit('navigate', '/student')
}


function starsLabel(rating: number): string {
  return '★'.repeat(rating) + '☆'.repeat(5 - rating)
}


onMounted(() => {
  loadEvaluations()
})
</script>

<template>
  <div class="evaluations-view">
    <el-page-header @back="goBack">
      <template #content>
        <span>我的评价</span>
      </template>
    </el-page-header>

    <div v-if="isLoading" class="loading-container">
      <el-skeleton :rows="4" animated />
    </div>

    <div v-else-if="errorMessage" class="error-container">
      <el-result icon="error" :title="errorMessage">
        <template #extra>
          <el-button type="primary" @click="loadEvaluations">重新加载</el-button>
          <el-button @click="goBack">返回个人中心</el-button>
        </template>
      </el-result>
    </div>

    <div v-else-if="evaluations.length === 0" class="empty-container">
      <el-empty description="暂无评价">
        <template #extra>
          <el-button @click="goBack">返回个人中心</el-button>
        </template>
      </el-empty>
    </div>

    <div v-else class="evaluation-list">
      <div
        v-for="evaluation in evaluations"
        :key="evaluation.id"
        class="evaluation-item"
      >
        <div class="eval-header">
          <div class="eval-club">
            <span class="eval-club-name">{{ evaluation.club.name }}</span>
          </div>
          <span class="eval-stars">{{ starsLabel(evaluation.rating) }}</span>
        </div>

        <p v-if="evaluation.comment" class="eval-comment">{{ evaluation.comment }}</p>
        <p v-else class="eval-comment eval-comment-empty">（无文字评价）</p>

        <div class="eval-actions">
          <el-button type="primary" size="small" text @click="openEditDialog(evaluation)">
            修改评价
          </el-button>
        </div>
      </div>
    </div>

    <!-- 修改弹窗 -->
    <el-dialog
      v-model="editDialogVisible"
      title="修改评价"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="editFormRef"
        :model="editForm"
        :rules="editFormRules"
        label-position="top"
      >
        <el-form-item label="评分" prop="rating">
          <el-rate
            v-model="editForm.rating"
            :max="5"
            :texts="['很差', '较差', '一般', '较好', '很好']"
            show-text
          />
        </el-form-item>

        <el-form-item label="评价内容（可选）">
          <el-input
            v-model="editForm.comment"
            type="textarea"
            :rows="4"
            maxlength="500"
            show-word-limit
            placeholder="写下你对社团的评价…"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="isSubmitting" @click="handleUpdate">
          确认修改
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.evaluations-view {
  max-width: 650px;
  margin: 0 auto;
  padding: 24px 16px;
}

.loading-container,
.error-container,
.empty-container {
  margin-top: 48px;
  text-align: center;
}

.evaluation-list {
  margin-top: 24px;
}

.evaluation-item {
  padding: 16px;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  margin-bottom: 12px;
}

.eval-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.eval-club-name {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.eval-stars {
  font-size: 16px;
  color: #e6a23c;
  letter-spacing: 2px;
}

.eval-comment {
  color: #606266;
  line-height: 1.6;
  margin: 0 0 8px;
  white-space: pre-wrap;
}

.eval-comment-empty {
  color: #c0c4cc;
  font-style: italic;
}

.eval-actions {
  text-align: right;
}
</style>
