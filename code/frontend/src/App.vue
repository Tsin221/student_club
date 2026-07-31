<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import LoginView from './views/LoginView.vue'
import RegisterView from './views/RegisterView.vue'
import StudentProfileEditView from './views/StudentProfileEditView.vue'
import StudentView from './views/StudentView.vue'
import AdminUsersView from './views/AdminUsersView.vue'


const currentPath = ref(window.location.pathname)
const routeRevision = ref(0)

const currentView = computed(() => {
  switch (currentPath.value) {
    case '/register':
      return RegisterView
    case '/student/profile/edit':
      return StudentProfileEditView
    case '/student':
      return StudentView
    case '/admin/users':
      return AdminUsersView
    case '/login':
    default:
      return LoginView
  }
})


function navigate(target: string) {
  const url = new URL(target, window.location.origin)
  window.history.pushState({}, '', `${url.pathname}${url.search}`)
  currentPath.value = url.pathname
  routeRevision.value += 1
  window.scrollTo({ top: 0 })
}


function syncRoute() {
  currentPath.value = window.location.pathname
  routeRevision.value += 1
}


onMounted(() => {
  window.addEventListener('popstate', syncRoute)
  if (!['/login', '/register', '/student', '/student/profile/edit', '/admin/users'].includes(currentPath.value)) {
    navigate('/login')
  }
})


onBeforeUnmount(() => {
  window.removeEventListener('popstate', syncRoute)
})
</script>

<template>
  <component
    :is="currentView"
    :key="routeRevision"
    @navigate="navigate"
  />
</template>
