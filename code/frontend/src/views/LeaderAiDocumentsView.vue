<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { ApiRequestError } from '../api/auth'
import { generateAiDocument } from '../api/clubs'
import { AI_DOCUMENT_TYPES, type AiDocumentType } from '../types/club'


const emit = defineEmits<{
  navigate: [path: string]
}>()

const clubId = computed(() => {
  const match = window.location.pathname.match(/^\/leader\/clubs\/(\d+)\/ai-documents/)
  return match ? Number(match[1]) : 0
})

// ── 表单状态 ──────────────────────────────────────────────

const form = reactive({
  document_type: '' as AiDocumentType | '',
  title_or_topic: '',
  main_content: '',
  audience: '',
  time: '',
  location: '',
  contact: '',
  expected_length: '',
  style: '',
  additional_requirements: '',
})

const isGenerating = ref(false)
const draft = ref('')
const errorMessage = ref('')

// ── 操作 ──────────────────────────────────────────────────

async function handleGenerate() {
  if (!form.document_type) {
    ElMessage.warning('请选择文档类型')
    return
  }

  isGenerating.value = true
  errorMessage.value = ''
  draft.value = ''

  try {
    const result = await generateAiDocument(clubId.value, {
      document_type: form.document_type as AiDocumentType,
      title_or_topic: form.title_or_topic.trim() || undefined,
      main_content: form.main_content.trim() || undefined,
      audience: form.audience.trim() || undefined,
      time: form.time.trim() || undefined,
      location: form.location.trim() || undefined,
      contact: form.contact.trim() || undefined,
      expected_length: form.expected_length.trim() || undefined,
      style: form.style.trim() || undefined,
      additional_requirements: form.additional_requirements.trim() || undefined,
    })
    draft.value = result.draft
    ElMessage.success('AI 文档草稿生成成功')
  } catch (error) {
    if (error instanceof ApiRequestError) {
      if (error.code === 'UNAUTHENTICATED') {
        emit('navigate', '/login?reason=session')
        return
      }
      if (error.code === 'NOT_CLUB_LEADER' || error.code === 'CLUB_CANCELLED') {
        emit('navigate', '/student')
        return
      }
      errorMessage.value = error.message
    } else {
      errorMessage.value = '生成失败，请稍后重试'
    }
  } finally {
    isGenerating.value = false
  }
}

async function handleCopy() {
  try {
    await navigator.clipboard.writeText(draft.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

function goBack() {
  emit('navigate', `/leader/clubs/${clubId.value}`)
}

onMounted(() => {
  //页面加载时不自动生成
})
</script>

<template>
  <div class="leader-ai-documents-view">
    <el-page-header @back="goBack">
      <template #content>
        <span>AI 文档生成</span>
      </template>
      <template #extra>
        <span style="font-size: 13px; color: #909399">
          使用 AI 为当前社团生成文档草稿，结果不会自动保存或发布
        </span>
      </template>
    </el-page-header>

    <el-card style="margin-top: 16px">
      <!-- 表单区 -->
      <el-form label-width="120px" :disabled="isGenerating">
        <el-form-item label="文档类型" required>
          <el-select
            v-model="form.document_type"
            placeholder="请选择要生成的文档类型"
            style="width: 240px"
          >
            <el-option
              v-for="t in AI_DOCUMENT_TYPES"
              :key="t"
              :label="t"
              :value="t"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="标题/主题">
          <el-input
            v-model="form.title_or_topic"
            placeholder="例如：社团招新通知、新学期活动预告"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>

        <el-form-item label="主要内容">
          <el-input
            v-model="form.main_content"
            type="textarea"
            :rows="3"
            placeholder="描述需要包含的核心内容…"
            maxlength="2000"
            show-word-limit
          />
        </el-form-item>

        <el-form-item label="面向对象">
          <el-input
            v-model="form.audience"
            placeholder="例如：全体成员、新生、校内师生"
            maxlength="100"
          />
        </el-form-item>

        <el-form-item label="时间">
          <el-input
            v-model="form.time"
            placeholder="例如：9月15日下午2点、2026年秋季学期"
            maxlength="100"
          />
        </el-form-item>

        <el-form-item label="地点">
          <el-input
            v-model="form.location"
            placeholder="例如：体育馆、线上腾讯会议"
            maxlength="100"
          />
        </el-form-item>

        <el-form-item label="联系方式">
          <el-input
            v-model="form.contact"
            placeholder="例如：社长 138xxxx、扫码加群"
            maxlength="100"
          />
        </el-form-item>

        <el-form-item label="期望字数">
          <el-input
            v-model="form.expected_length"
            placeholder="例如：300字、不超过500字"
            maxlength="50"
          />
        </el-form-item>

        <el-form-item label="文风">
          <el-input
            v-model="form.style"
            placeholder="例如：正式、活泼、简洁"
            maxlength="50"
          />
        </el-form-item>

        <el-form-item label="其他要求">
          <el-input
            v-model="form.additional_requirements"
            type="textarea"
            :rows="2"
            placeholder="其他补充要求…"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            :loading="isGenerating"
            @click="handleGenerate"
          >
            {{ draft ? '重新生成' : '生成草稿' }}
          </el-button>
        </el-form-item>
      </el-form>

      <!-- 错误态 -->
      <el-result
        v-if="errorMessage && !draft"
        icon="error"
        :title="errorMessage"
      >
        <template #extra>
          <el-button type="primary" @click="handleGenerate">重试</el-button>
        </template>
      </el-result>

      <!-- 结果展示区 -->
      <div v-if="draft" style="margin-top: 24px">
        <el-divider />
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px">
          <h3 style="margin: 0; font-size: 16px">生成结果</h3>
          <el-button size="small" @click="handleCopy">
            复制草稿
          </el-button>
        </div>
        <div
          style="
            background: #f5f7fa;
            border: 1px solid #e4e7ed;
            border-radius: 4px;
            padding: 16px;
            white-space: pre-wrap;
            font-size: 14px;
            line-height: 1.8;
            max-height: 500px;
            overflow-y: auto;
          "
        >{{ draft }}</div>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.leader-ai-documents-view {
  max-width: 800px;
  margin: 24px auto;
  padding: 0 16px;
}
</style>
