import type {
  Club,
  CreateClubResult,
  MyMembershipsResult,
  PaginatedClubs,
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
