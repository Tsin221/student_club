<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import LoginView from './views/LoginView.vue'
import RegisterView from './views/RegisterView.vue'
import StudentProfileEditView from './views/StudentProfileEditView.vue'
import StudentView from './views/StudentView.vue'
import StudentClubsView from './views/StudentClubsView.vue'
import StudentClubDetailView from './views/StudentClubDetailView.vue'
import StudentMembershipsView from './views/StudentMembershipsView.vue'
import AdminUsersView from './views/AdminUsersView.vue'
import AdminClubsView from './views/AdminClubsView.vue'


const currentPath = ref(window.location.pathname)
const routeRevision = ref(0)

//学生社团详情页匹配（/student/clubs/{数字}）
function isStudentClubDetail(path: string): boolean {
  return /^\/student\/clubs\/\d+$/.test(path)
}

const currentView = computed(() => {
  const path = currentPath.value
  switch (path) {
    case '/register':
      return RegisterView
    case '/student/profile/edit':
      return StudentProfileEditView
    case '/student':
      return StudentView
    case '/student/clubs':
      return StudentClubsView
    case '/student/memberships':
      return StudentMembershipsView
    case '/admin/users':
      return AdminUsersView
    case '/admin/clubs':
      return AdminClubsView
    case '/login':
    default: {
      if (isStudentClubDetail(path)) {
        return StudentClubDetailView
      }
      return LoginView
    }
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


const VALID_PATHS = [
  '/login', '/register',
  '/student', '/student/profile/edit', '/student/clubs', '/student/memberships',
  '/admin/users', '/admin/clubs',
]

function isValidPath(path: string): boolean {
  return VALID_PATHS.includes(path) || isStudentClubDetail(path)
}


onMounted(() => {
  window.addEventListener('popstate', syncRoute)
  if (!isValidPath(currentPath.value)) {
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
