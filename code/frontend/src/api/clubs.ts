import type {
  Announcement,
  Club,
  ClubMembership,
  CreateAnnouncementInput,
  CreateClubResult,
  DeleteAnnouncementResult,
  LeaderMembersResult,
  MyMembership,
  MyMembershipsResult,
  PaginatedAnnouncements,
  PaginatedClubs,
  PaginatedMemberships,
  PaginatedRecruitments,
  Recruitment,
  UpdateAnnouncementInput,
} from '../types/club'
import { ApiRequestError } from './auth'
import {
  isSuccessResponse,
  type ApiResponse,
} from './response'


function isApiResponse(value: unknown): value is ApiResponse<unknown> {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const candidate = value as Record<string, unknown>
  return (
    typeof candidate.code === 'string'
    && typeof candidate.message === 'string'
    && 'data' in candidate
  )
}


async function request<T>(
  url: string,
  options: RequestInit,
): Promise<T> {
  const response = await fetch(url, {
    credentials: 'same-origin',
    ...options,
  })

  let body: unknown
  try {
    body = await response.json()
  } catch {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回了无法识别的响应',
      response.status,
    )
  }

  if (!isApiResponse(body)) {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回了无法识别的响应',
      response.status,
    )
  }

  if (!response.ok || !isSuccessResponse(body)) {
    throw new ApiRequestError(body.code, body.message, response.status)
  }

  return body.data as T
}


// ── 类型守卫 ──────────────────────────────────────────────

function isClub(value: unknown): value is Club {
  if (typeof value !== 'object' || value === null) return false
  const c = value as Record<string, unknown>
  return (
    typeof c.id === 'number'
    && typeof c.name === 'string'
    && typeof c.category === 'string'
    && typeof c.introduction === 'string'
    && typeof c.logo === 'string'
    && typeof c.created_at === 'string'
    && typeof c.status === 'string'
  )
}


function isPaginatedClubs(value: unknown): value is PaginatedClubs {
  if (typeof value !== 'object' || value === null) return false
  const c = value as Record<string, unknown>
  return (
    Array.isArray(c.items)
    && typeof c.page === 'number'
    && typeof c.page_size === 'number'
    && typeof c.total === 'number'
  )
}


function requireClub(value: unknown): Club {
  if (!isClub(value)) {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回的社团数据不完整',
      200,
    )
  }
  return value
}


// ── API 函数 ──────────────────────────────────────────────


//GET /api/admin/clubs — 管理员社团列表
export async function getAdminClubs(
  page = 1,
  pageSize = 20,
): Promise<PaginatedClubs> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })
  const data = await request<unknown>(
    `/api/admin/clubs?${params.toString()}`,
    { method: 'GET' },
  )

  if (!isPaginatedClubs(data)) {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回的社团列表格式不正确',
      200,
    )
  }

  for (const item of data.items) {
    if (!isClub(item)) {
      throw new ApiRequestError(
        'INVALID_RESPONSE',
        '服务器返回的社团数据不完整',
        200,
      )
    }
  }

  return data
}


//POST /api/admin/clubs — 管理员创建社团
export async function createClub(
  formData: FormData,
): Promise<CreateClubResult> {
  const response = await fetch('/api/admin/clubs', {
    method: 'POST',
    credentials: 'same-origin',
    body: formData,
  })

  let body: unknown
  try {
    body = await response.json()
  } catch {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回了无法识别的响应',
      response.status,
    )
  }

  if (!isApiResponse(body)) {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回了无法识别的响应',
      response.status,
    )
  }

  if (!response.ok || !isSuccessResponse(body)) {
    throw new ApiRequestError(body.code, body.message, response.status)
  }

  const data = body.data as Record<string, unknown>
  if (
    typeof data !== 'object'
    || data === null
    || !isClub(data.club)
    || !Array.isArray(data.leaders)
  ) {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回的创建结果格式不正确',
      200,
    )
  }

  return data as unknown as CreateClubResult
}


//GET /api/clubs — 公开社团列表
export async function getPublicClubs(
  page = 1,
  pageSize = 20,
  category?: string,
): Promise<PaginatedClubs> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })
  if (category) {
    params.set('category', category)
  }
  const data = await request<unknown>(
    `/api/clubs?${params.toString()}`,
    { method: 'GET' },
  )

  if (!isPaginatedClubs(data)) {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回的社团列表格式不正确',
      200,
    )
  }

  for (const item of data.items) {
    if (!isClub(item)) {
      throw new ApiRequestError(
        'INVALID_RESPONSE',
        '服务器返回的社团数据不完整',
        200,
      )
    }
  }

  return data
}


//GET /api/clubs/{club_id} — 社团详情
export async function getClubDetail(clubId: number): Promise<Club> {
  const data = await request<unknown>(
    `/api/clubs/${clubId}`,
    { method: 'GET' },
  )
  return requireClub(data)
}


//GET /api/me/memberships — 我的社团
export async function getMyMemberships(): Promise<MyMembershipsResult> {
  const data = await request<unknown>(
    '/api/me/memberships',
    { method: 'GET' },
  )

  if (
    typeof data !== 'object'
    || data === null
    || !Array.isArray((data as Record<string, unknown>).items)
  ) {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回的成员关系列表格式不正确',
      200,
    )
  }

  return data as MyMembershipsResult
}


// ── S05 新增 API 函数 ──────────────────────────────────────


async function patchJson<T>(url: string, body: unknown): Promise<T> {
  return request<T>(url, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}


async function postJson<T>(url: string, body: unknown): Promise<T> {
  return request<T>(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}


async function deleteRequest<T>(url: string): Promise<T> {
  return request<T>(url, { method: 'DELETE' })
}


//PATCH /api/admin/clubs/{club_id} — 管理员修改社团
export async function updateAdminClub(
  clubId: number,
  data: { name?: string; category?: string; introduction?: string },
): Promise<Club> {
  const result = await patchJson<unknown>(
    `/api/admin/clubs/${clubId}`,
    data,
  )
  return requireClub(result)
}


//POST /api/admin/clubs/{club_id}/cancel — 管理员注销社团
export async function cancelClub(clubId: number): Promise<Club> {
  const result = await postJson<unknown>(
    `/api/admin/clubs/${clubId}/cancel`,
    {},
  )
  return requireClub(result)
}


//PATCH /api/leader/clubs/{club_id} — 负责人修改社团简介
export async function updateLeaderClub(
  clubId: number,
  data: { introduction?: string },
): Promise<Club> {
  const result = await patchJson<unknown>(
    `/api/leader/clubs/${clubId}`,
    data,
  )
  return requireClub(result)
}


//GET /api/admin/memberships — 管理员查看全量成员关系
export async function getAdminMemberships(
  page = 1,
  pageSize = 20,
): Promise<PaginatedMemberships> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })
  const data = await request<unknown>(
    `/api/admin/memberships?${params.toString()}`,
    { method: 'GET' },
  )

  if (
    typeof data !== 'object'
    || data === null
    || !Array.isArray((data as Record<string, unknown>).items)
  ) {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回的成员关系列表格式不正确',
      200,
    )
  }

  return data as PaginatedMemberships
}


//GET /api/leader/clubs/{club_id}/members — 负责人查看在社成员
export async function getLeaderMembers(
  clubId: number,
): Promise<LeaderMembersResult> {
  const data = await request<unknown>(
    `/api/leader/clubs/${clubId}/members`,
    { method: 'GET' },
  )

  if (
    typeof data !== 'object'
    || data === null
    || !Array.isArray((data as Record<string, unknown>).items)
  ) {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回的成员列表格式不正确',
      200,
    )
  }

  return data as LeaderMembersResult
}


//POST /api/admin/clubs/{club_id}/leaders — 管理员提升负责人
export async function addClubLeader(
  clubId: number,
  membershipId: number,
): Promise<ClubMembership> {
  const data = await postJson<unknown>(
    `/api/admin/clubs/${clubId}/leaders`,
    { membership_id: membershipId },
  )
  return data as ClubMembership
}


//DELETE /api/admin/clubs/{club_id}/leaders/{membership_id} — 管理员降级负责人
export async function removeClubLeader(
  clubId: number,
  membershipId: number,
): Promise<ClubMembership> {
  const data = await deleteRequest<unknown>(
    `/api/admin/clubs/${clubId}/leaders/${membershipId}`,
  )
  return data as ClubMembership
}


// ═════════════════════════════════════════════════════════════
// S06 招新 API
// ═════════════════════════════════════════════════════════════


function isRecruitment(value: unknown): value is Recruitment {
  if (typeof value !== 'object' || value === null) return false
  const r = value as Record<string, unknown>
  return (
    typeof r.id === 'number'
    && typeof r.title === 'string'
    && typeof r.introduction === 'string'
    && typeof r.requirements === 'string'
    && typeof r.capacity === 'number'
    && typeof r.start_time === 'string'
    && typeof r.end_time === 'string'
    && typeof r.club_id === 'number'
    && typeof r.published_at === 'string'
    && typeof r.ended_early === 'boolean'
    && typeof r.display_status === 'string'
    && typeof r.approved_count === 'number'
  )
}


function requireRecruitment(value: unknown): Recruitment {
  if (!isRecruitment(value)) {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回的招新数据不完整',
      200,
    )
  }
  return value
}


function isPaginatedRecruitments(value: unknown): value is PaginatedRecruitments {
  if (typeof value !== 'object' || value === null) return false
  const c = value as Record<string, unknown>
  return (
    Array.isArray(c.items)
    && typeof c.page === 'number'
    && typeof c.page_size === 'number'
    && typeof c.total === 'number'
  )
}


//GET /api/clubs/{club_id}/recruitments — 学生查看有效招新
export async function getPublicRecruitments(
  clubId: number,
  page = 1,
  pageSize = 20,
): Promise<PaginatedRecruitments> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })
  const data = await request<unknown>(
    `/api/clubs/${clubId}/recruitments?${params.toString()}`,
    { method: 'GET' },
  )

  if (!isPaginatedRecruitments(data)) {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回的招新列表格式不正确',
      200,
    )
  }

  for (const item of data.items) {
    if (!isRecruitment(item)) {
      throw new ApiRequestError(
        'INVALID_RESPONSE',
        '服务器返回的招新数据不完整',
        200,
      )
    }
  }

  return data
}


//GET /api/leader/clubs/{club_id}/recruitments — 负责人查看全部招新
export async function getLeaderRecruitments(
  clubId: number,
  page = 1,
  pageSize = 20,
): Promise<PaginatedRecruitments> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })
  const data = await request<unknown>(
    `/api/leader/clubs/${clubId}/recruitments?${params.toString()}`,
    { method: 'GET' },
  )

  if (!isPaginatedRecruitments(data)) {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回的招新列表格式不正确',
      200,
    )
  }

  for (const item of data.items) {
    if (!isRecruitment(item)) {
      throw new ApiRequestError(
        'INVALID_RESPONSE',
        '服务器返回的招新数据不完整',
        200,
      )
    }
  }

  return data
}


//POST /api/leader/clubs/{club_id}/recruitments — 负责人发布招新
export async function createRecruitment(
  clubId: number,
  data: {
    title: string
    introduction: string
    requirements: string
    capacity: number
    start_time: string
    end_time: string
  },
): Promise<Recruitment> {
  const result = await postJson<unknown>(
    `/api/leader/clubs/${clubId}/recruitments`,
    data,
  )
  return requireRecruitment(result)
}


//PATCH /api/leader/recruitments/{recruitment_id} — 负责人修改招新
export async function updateRecruitment(
  recruitmentId: number,
  data: {
    title?: string
    introduction?: string
    requirements?: string
    capacity?: number
    start_time?: string
    end_time?: string
  },
): Promise<Recruitment> {
  const result = await patchJson<unknown>(
    `/api/leader/recruitments/${recruitmentId}`,
    data,
  )
  return requireRecruitment(result)
}


//POST /api/leader/recruitments/{recruitment_id}/end — 负责人提前结束招新
export async function endRecruitment(
  recruitmentId: number,
): Promise<Recruitment> {
  const result = await postJson<unknown>(
    `/api/leader/recruitments/${recruitmentId}/end`,
    {},
  )
  return requireRecruitment(result)
}


//GET /api/admin/recruitments — 管理员查看全量招新记录
export async function getAdminRecruitments(
  page = 1,
  pageSize = 20,
): Promise<PaginatedRecruitments> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })
  const data = await request<unknown>(
    `/api/admin/recruitments?${params.toString()}`,
    { method: 'GET' },
  )

  if (!isPaginatedRecruitments(data)) {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回的招新记录格式不正确',
      200,
    )
  }

  for (const item of data.items) {
    if (!isRecruitment(item)) {
      throw new ApiRequestError(
        'INVALID_RESPONSE',
        '服务器返回的招新数据不完整',
        200,
      )
    }
  }

  return data
}


// ═════════════════════════════════════════════════════════════
// S08 成员退出与移除 API
// ═════════════════════════════════════════════════════════════


//POST /api/me/memberships/{membership_id}/exit — 学生主动退出社团
export async function exitMembership(
  membershipId: number,
): Promise<MyMembership> {
  const data = await postJson<unknown>(
    `/api/me/memberships/${membershipId}/exit`,
    {},
  )
  return data as MyMembership
}


//POST /api/leader/memberships/{membership_id}/remove — 负责人移除成员
export async function removeMember(
  membershipId: number,
): Promise<{
  id: number
  user_id: number
  club_id: number
  member_status: string
  club_role: string
}> {
  const data = await postJson<unknown>(
    `/api/leader/memberships/${membershipId}/remove`,
    {},
  )
  return data as {
    id: number
    user_id: number
    club_id: number
    member_status: string
    club_role: string
  }
}


// ═════════════════════════════════════════════════════════════
// S09 社团公告 API
// ═════════════════════════════════════════════════════════════


function isAnnouncement(value: unknown): value is Announcement {
  if (typeof value !== 'object' || value === null) return false
  const a = value as Record<string, unknown>
  return (
    typeof a.id === 'number'
    && typeof a.title === 'string'
    && typeof a.content === 'string'
    && typeof a.club_id === 'number'
    && typeof a.publisher === 'object'
    && a.publisher !== null
    && typeof a.published_at === 'string'
    && typeof a.is_pinned === 'boolean'
    && typeof a.status === 'string'
  )
}


function requireAnnouncement(value: unknown): Announcement {
  if (!isAnnouncement(value)) {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回的公告数据不完整',
      200,
    )
  }
  return value
}


function isPaginatedAnnouncements(value: unknown): value is PaginatedAnnouncements {
  if (typeof value !== 'object' || value === null) return false
  const c = value as Record<string, unknown>
  return (
    Array.isArray(c.items)
    && typeof c.page === 'number'
    && typeof c.page_size === 'number'
    && typeof c.total === 'number'
  )
}


//GET /api/clubs/{club_id}/announcements — 成员查看正常公告
export async function listAnnouncements(
  clubId: number,
  page = 1,
  pageSize = 20,
): Promise<PaginatedAnnouncements> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })
  const data = await request<unknown>(
    `/api/clubs/${clubId}/announcements?${params.toString()}`,
    { method: 'GET' },
  )

  if (!isPaginatedAnnouncements(data)) {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回的公告列表格式不正确',
      200,
    )
  }

  for (const item of data.items) {
    if (!isAnnouncement(item)) {
      throw new ApiRequestError(
        'INVALID_RESPONSE',
        '服务器返回的公告数据不完整',
        200,
      )
    }
  }

  return data
}


//GET /api/leader/clubs/{club_id}/announcements — 负责人查看全量公告
export async function getLeaderAnnouncements(
  clubId: number,
  page = 1,
  pageSize = 20,
): Promise<PaginatedAnnouncements> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })
  const data = await request<unknown>(
    `/api/leader/clubs/${clubId}/announcements?${params.toString()}`,
    { method: 'GET' },
  )

  if (!isPaginatedAnnouncements(data)) {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回的公告列表格式不正确',
      200,
    )
  }

  for (const item of data.items) {
    if (!isAnnouncement(item)) {
      throw new ApiRequestError(
        'INVALID_RESPONSE',
        '服务器返回的公告数据不完整',
        200,
      )
    }
  }

  return data
}


//POST /api/leader/clubs/{club_id}/announcements — 负责人发布公告
export async function createAnnouncement(
  clubId: number,
  data: CreateAnnouncementInput,
): Promise<Announcement> {
  const result = await postJson<unknown>(
    `/api/leader/clubs/${clubId}/announcements`,
    data,
  )
  return requireAnnouncement(result)
}


//PATCH /api/leader/announcements/{announcement_id} — 负责人修改公告
export async function updateAnnouncement(
  announcementId: number,
  data: UpdateAnnouncementInput,
): Promise<Announcement> {
  const result = await patchJson<unknown>(
    `/api/leader/announcements/${announcementId}`,
    data,
  )
  return requireAnnouncement(result)
}


//DELETE /api/leader/announcements/{announcement_id} — 负责人逻辑删除公告
export async function deleteAnnouncement(
  announcementId: number,
): Promise<DeleteAnnouncementResult> {
  const data = await deleteRequest<unknown>(
    `/api/leader/announcements/${announcementId}`,
  )
  return data as DeleteAnnouncementResult
}


//GET /api/admin/clubs/{club_id}/announcements — 管理员查看已注销社团公告
export async function getAdminAnnouncements(
  clubId: number,
  page = 1,
  pageSize = 20,
): Promise<PaginatedAnnouncements> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })
  const data = await request<unknown>(
    `/api/admin/clubs/${clubId}/announcements?${params.toString()}`,
    { method: 'GET' },
  )

  if (!isPaginatedAnnouncements(data)) {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回的公告列表格式不正确',
      200,
    )
  }

  for (const item of data.items) {
    if (!isAnnouncement(item)) {
      throw new ApiRequestError(
        'INVALID_RESPONSE',
        '服务器返回的公告数据不完整',
        200,
      )
    }
  }

  return data
}
