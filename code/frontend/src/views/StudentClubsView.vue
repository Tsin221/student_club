<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { ApiRequestError } from '../api/auth'
import { getPublicClubs } from '../api/clubs'
import { CLUB_CATEGORIES, type Club, type ClubCategory } from '../types/club'


const emit = defineEmits<{
  navigate: [path: string]
}>()

// ── 列表状态 ──────────────────────────────────────────────

const isLoading = ref(true)
const errorMessage = ref('')
const clubs = ref<Club[]>([])
const currentPage = ref(1)
const pageSize = ref(12)
const total = ref(0)
const activeCategory = ref<ClubCategory | ''>('')

// ── 数据加载 ──────────────────────────────────────────────

async function loadClubs() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const data = await getPublicClubs(
      currentPage.value,
      pageSize.value,
      activeCategory.value || undefined,
    )
    clubs.value = data.items
    total.value = data.total
  } catch (error) {
    if (error instanceof ApiRequestError) {
      if (error.code === 'UNAUTHENTICATED') {
        emit('navigate', '/login?reason=session')
        return
      }
      errorMessage.value = error.message
    } else {
      errorMessage.value = '社团列表加载失败，请稍后重试'
    }
  } finally {
    isLoading.value = false
  }
}


function selectCategory(cat: ClubCategory | '') {
  activeCategory.value = cat
  currentPage.value = 1
  loadClubs()
}


function goToDetail(clubId: number) {
  emit('navigate', `/student/clubs/${clubId}`)
}


function handlePageChange(page: number) {
  currentPage.value = page
  loadClubs()
}

// ── 格式化 ────────────────────────────────────────────────

const categoryChipType = (cat: string): 'primary' | 'success' | 'warning' | 'danger' | 'info' => {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'danger' | 'info'> = {
    '文化艺术': 'primary',
    '体育竞技': 'success',
    '学术科技': 'warning',
    '公益实践': 'danger',
    '兴趣爱好': 'info',
  }
  return map[cat] ?? 'primary'
}


onMounted(() => {
  loadClubs()
})
</script>

<template>
  <main class="student-page">
    <header class="student-header">
      <div class="brand-mark" aria-hidden="true">社</div>
      <div>
        <p class="eyebrow">校园社团智能管理系统</p>
        <p class="header-title">社团广场</p>
      </div>
    </header>

    <div class="student-content">
      <section class="page-heading" aria-labelledby="clubs-title">
        <p class="section-kicker">探索</p>
        <h1 id="clubs-title">全部社团</h1>
        <p>浏览校园内全部正常运作的社团，发现你感兴趣的组织。</p>
      </section>

      <!-- 类别筛选 -->
      <div class="category-filter" style="margin-bottom: 24px">
        <el-button
          :type="activeCategory === '' ? 'primary' : 'default'"
          size="small"
          @click="selectCategory('')"
        >
          全部
        </el-button>
        <el-button
          v-for="cat in CLUB_CATEGORIES"
          :key="cat"
          :type="activeCategory === cat ? 'primary' : 'default'"
          size="small"
          @click="selectCategory(cat)"
        >
          {{ cat }}
        </el-button>
      </div>

      <!-- 错误状态 -->
      <el-alert
        v-if="errorMessage"
        type="error"
        :title="errorMessage"
        :closable="false"
        show-icon
        class="form-alert"
      />

      <!-- 加载与社团卡片 -->
      <div v-loading="isLoading" aria-live="polite">
        <template v-if="!errorMessage && clubs.length === 0 && !isLoading">
          <el-empty description="暂无社团" />
        </template>

        <template v-else-if="!errorMessage">
          <div class="club-cards-grid">
            <el-card
              v-for="club in clubs"
              :key="club.id"
              class="club-card"
              shadow="hover"
              @click="goToDetail(club.id)"
            >
              <div class="club-card-logo">
                <img
                  v-if="club.logo"
                  :src="club.logo"
                  :alt="`${club.name} Logo`"
                  class="club-logo-img"
                >
                <div v-else class="club-logo-placeholder">
                  {{ club.name.charAt(0) }}
                </div>
              </div>
              <div class="club-card-body">
                <div class="club-card-header">
                  <h3>{{ club.name }}</h3>
                  <el-tag
                    :type="categoryChipType(club.category)"
                    effect="light"
                    size="small"
                  >
                    {{ club.category }}
                  </el-tag>
                </div>
                <p class="club-card-intro">
                  {{ club.introduction.length > 80
                    ? club.introduction.slice(0, 80) + '…'
                    : club.introduction }}
                </p>
              </div>
            </el-card>
          </div>

          <div class="pagination-wrap">
            <el-pagination
              v-model:current-page="currentPage"
              :page-size="pageSize"
              :total="total"
              layout="total, prev, pager, next"
              background
              @current-change="handlePageChange"
            />
          </div>
        </template>
      </div>
    </div>
  </main>
</template>

<style scoped>
.club-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
}

.club-card {
  cursor: pointer;
  border: 1px solid var(--border);
  transition: box-shadow 0.2s;
}

.club-card .el-card__body {
  display: flex;
  gap: 16px;
  padding: 20px;
}

.club-card-logo {
  flex: none;
  width: 64px;
  height: 64px;
  border-radius: 12px;
  overflow: hidden;
  background: var(--brand-100);
}

.club-logo-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.club-logo-placeholder {
  display: grid;
  width: 100%;
  height: 100%;
  place-items: center;
  color: var(--brand-700);
  font-size: 24px;
  font-weight: 750;
}

.club-card-body {
  flex: 1;
  min-width: 0;
}

.club-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.club-card-header h3 {
  margin: 0;
  color: var(--text);
  font-size: 17px;
  font-weight: 700;
}

.club-card-intro {
  margin: 8px 0 0;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.6;
}

.category-filter {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
