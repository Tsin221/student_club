<script setup lang="ts">
const checks = [
  'Vue 3 与 TypeScript 已配置',
  'Element Plus 已加载',
  '开发代理已指向 Django',
]
</script>

<template>
  <main class="app-shell">
    <el-card class="status-card" shadow="never">
      <template #header>
        <div class="status-card__header">
          <div>
            <p class="eyebrow">S00 · 工程骨架</p>
            <h1>校园社团智能管理系统</h1>
          </div>
          <el-tag type="success" effect="light">前端已就绪</el-tag>
        </div>
      </template>

      <p class="summary">
        当前仅验证基础工程、组件库和开发配置，不包含登录、注册或业务页面。
      </p>

      <el-space direction="vertical" alignment="start" :size="14">
        <div v-for="check in checks" :key="check" class="check-item">
          <span class="check-mark" aria-hidden="true">✓</span>
          <span>{{ check }}</span>
        </div>
      </el-space>
    </el-card>
  </main>
</template>
