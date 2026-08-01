<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import AdminAnnouncementsView from './views/AdminAnnouncementsView.vue'
import AdminApplicationsView from './views/AdminApplicationsView.vue'
import AdminClubDetailView from './views/AdminClubDetailView.vue'
import AdminClubsView from './views/AdminClubsView.vue'
import AdminEvaluationsView from './views/AdminEvaluationsView.vue'
import AdminMembershipsView from './views/AdminMembershipsView.vue'
import AdminRecruitmentsView from './views/AdminRecruitmentsView.vue'
import AdminUsersView from './views/AdminUsersView.vue'
import LeaderApplicationsView from './views/LeaderApplicationsView.vue'
import LeaderClubWorkspaceView from './views/LeaderClubWorkspaceView.vue'
import LeaderRecruitmentsView from './views/LeaderRecruitmentsView.vue'
import LoginView from './views/LoginView.vue'
import RegisterView from './views/RegisterView.vue'
import StudentApplicationsView from './views/StudentApplicationsView.vue'
import StudentClubDetailView from './views/StudentClubDetailView.vue'
import StudentClubsView from './views/StudentClubsView.vue'
import StudentEvaluationsView from './views/StudentEvaluationsView.vue'
import StudentMembershipsView from './views/StudentMembershipsView.vue'
import StudentNotificationsView from './views/StudentNotificationsView.vue'
import StudentProfileEditView from './views/StudentProfileEditView.vue'
import StudentRecruitmentsView from './views/StudentRecruitmentsView.vue'
import StudentView from './views/StudentView.vue'


const currentPath = ref(window.location.pathname)
const routeRevision = ref(0)

//学生社团详情页匹配（/student/clubs/{数字}）
function isStudentClubDetail(path: string): boolean {
  return /^\/student\/clubs\/\d+$/.test(path)
}

//管理员社团详情页匹配
function isAdminClubDetail(path: string): boolean {
  return /^\/admin\/clubs\/\d+$/.test(path)
}

//负责人社团工作台匹配
function isLeaderClubWorkspace(path: string): boolean {
  return /^\/leader\/clubs\/\d+$/.test(path)
}

//学生招新列表匹配（/student/clubs/{数字}/recruitments）
function isStudentRecruitments(path: string): boolean {
  return /^\/student\/clubs\/\d+\/recruitments$/.test(path)
}

//负责人招新管理匹配（/leader/clubs/{数字}/recruitments）
function isLeaderRecruitments(path: string): boolean {
  return /^\/leader\/clubs\/\d+\/recruitments$/.test(path)
}

//负责人入社申请匹配（/leader/clubs/{数字}/applications）
function isLeaderApplications(path: string): boolean {
  return /^\/leader\/clubs\/\d+\/applications$/.test(path)
}

//管理员公告历史匹配（/admin/clubs/{数字}/announcements）
function isAdminAnnouncements(path: string): boolean {
  return /^\/admin\/clubs\/\d+\/announcements$/.test(path)
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
    case '/student/applications':
      return StudentApplicationsView
    case '/student/notifications':
      return StudentNotificationsView
    case '/student/evaluations':
      return StudentEvaluationsView
    case '/admin/users':
      return AdminUsersView
    case '/admin/clubs':
      return AdminClubsView
    case '/admin/memberships':
      return AdminMembershipsView
    case '/admin/recruitments':
      return AdminRecruitmentsView
    case '/admin/applications':
      return AdminApplicationsView
    case '/admin/evaluations':
      return AdminEvaluationsView
    case '/login':
    default: {
      if (isStudentClubDetail(path)) {
        return StudentClubDetailView
      }
      if (isStudentRecruitments(path)) {
        return StudentRecruitmentsView
      }
      if (isAdminClubDetail(path)) {
        return AdminClubDetailView
      }
      if (isLeaderRecruitments(path)) {
        return LeaderRecruitmentsView
      }
      if (isLeaderApplications(path)) {
        return LeaderApplicationsView
      }
      if (isLeaderClubWorkspace(path)) {
        return LeaderClubWorkspaceView
      }
      if (isAdminAnnouncements(path)) {
        return AdminAnnouncementsView
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
  '/student/applications', '/student/notifications', '/student/evaluations',
  '/admin/users', '/admin/clubs', '/admin/memberships', '/admin/recruitments',
  '/admin/applications', '/admin/evaluations',
]

function isValidPath(path: string): boolean {
  return VALID_PATHS.includes(path)
    || isStudentClubDetail(path)
    || isStudentRecruitments(path)
    || isAdminClubDetail(path)
    || isAdminAnnouncements(path)
    || isLeaderRecruitments(path)
    || isLeaderApplications(path)
    || isLeaderClubWorkspace(path)
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
