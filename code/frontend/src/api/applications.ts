import type {
  ApproveApplicationResult,
  JoinApplication,
  NotificationsResult,
  PaginatedApplications,
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


async function postJson<T>(url: string, body: unknown): Promise<T> {
  return request<T>(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}


// ── 类型守卫 ──────────────────────────────────────────────

function isJoinApplication(value: unknown): value is JoinApplication {
  if (typeof value !== 'object' || value === null) return false
  const a = value as Record<string, unknown>
  return (
    typeof a.id === 'number'
    && typeof a.applicant_id === 'number'
    && typeof a.status === 'string'
    && typeof a.reason === 'string'
    && typeof a.applied_at === 'string'
  )
}


function requireJoinApplication(value: unknown): JoinApplication {
  if (!isJoinApplication(value)) {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回的入社申请数据不完整',
      200,
    )
  }
  return value
}


function isPaginatedApplications(value: unknown): value is PaginatedApplications {
  if (typeof value !== 'object' || value === null) return false
  const c = value as Record<string, unknown>
  return (
    Array.isArray(c.items)
    && typeof c.page === 'number'
    && typeof c.page_size === 'number'
    && typeof c.total === 'number'
  )
}


// ── S07 API 函数 ──────────────────────────────────────────


//POST /api/recruitments/{recruitment_id}/applications — 提交入社申请
export async function submitApplication(
  recruitmentId: number,
  reason: string,
): Promise<JoinApplication> {
  const result = await postJson<unknown>(
    `/api/recruitments/${recruitmentId}/applications`,
    { reason },
  )
  return requireJoinApplication(result)
}


//GET /api/me/join-applications — 我的入社申请
export async function getMyApplications(
  page = 1,
  pageSize = 20,
): Promise<PaginatedApplications> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })
  const data = await request<unknown>(
    `/api/me/join-applications?${params.toString()}`,
    { method: 'GET' },
  )

  if (!isPaginatedApplications(data)) {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回的入社申请列表格式不正确',
      200,
    )
  }

  return data
}


//GET /api/leader/clubs/{club_id}/join-applications — 负责人查看申请
export async function getLeaderApplications(
  clubId: number,
  page = 1,
  pageSize = 20,
): Promise<PaginatedApplications> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })
  const data = await request<unknown>(
    `/api/leader/clubs/${clubId}/join-applications?${params.toString()}`,
    { method: 'GET' },
  )

  if (!isPaginatedApplications(data)) {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回的入社申请列表格式不正确',
      200,
    )
  }

  return data
}


//POST /api/leader/join-applications/{application_id}/approve — 通过申请
export async function approveApplication(
  applicationId: number,
): Promise<ApproveApplicationResult> {
  const data = await postJson<unknown>(
    `/api/leader/join-applications/${applicationId}/approve`,
    {},
  )

  if (
    typeof data !== 'object'
    || data === null
    || !isJoinApplication((data as Record<string, unknown>).application)
    || typeof (data as Record<string, unknown>).membership !== 'object'
  ) {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回的审核结果格式不正确',
      200,
    )
  }

  return data as ApproveApplicationResult
}


//POST /api/leader/join-applications/{application_id}/reject — 拒绝申请
export async function rejectApplication(
  applicationId: number,
): Promise<JoinApplication> {
  const result = await postJson<unknown>(
    `/api/leader/join-applications/${applicationId}/reject`,
    {},
  )
  return requireJoinApplication(result)
}


//GET /api/admin/join-applications — 管理员查看全量申请
export async function getAdminApplications(
  page = 1,
  pageSize = 20,
): Promise<PaginatedApplications> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })
  const data = await request<unknown>(
    `/api/admin/join-applications?${params.toString()}`,
    { method: 'GET' },
  )

  if (!isPaginatedApplications(data)) {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回的入社申请列表格式不正确',
      200,
    )
  }

  return data
}


//GET /api/me/notifications — 我的通知
export async function getMyNotifications(): Promise<NotificationsResult> {
  const data = await request<unknown>(
    '/api/me/notifications',
    { method: 'GET' },
  )

  if (
    typeof data !== 'object'
    || data === null
    || !Array.isArray((data as Record<string, unknown>).items)
  ) {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回的通知列表格式不正确',
      200,
    )
  }

  return data as NotificationsResult
}
