import type {
  LoginInput,
  PaginatedUsers,
  ProfileUpdateInput,
  RegistrationInput,
  ResetPasswordResult,
  SelfUser,
  UpdateUserStatusInput,
  UpdateUserStatusResult,
} from '../types/user'
import {
  isSuccessResponse,
  type ApiResponse,
} from './response'


export class ApiRequestError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number,
  ) {
    super(message)
    this.name = 'ApiRequestError'
  }
}


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


function isSelfUser(value: unknown): value is SelfUser {
  if (typeof value !== 'object' || value === null) {
    return false
  }

  const user = value as Record<string, unknown>
  return (
    typeof user.id === 'number'
    && typeof user.username === 'string'
    && ['student', 'system_admin'].includes(String(user.platform_role))
    && ['active', 'disabled'].includes(String(user.account_status))
    && typeof user.registered_at === 'string'
    && typeof user.name === 'string'
    && typeof user.phone === 'string'
    && typeof user.major_class === 'string'
    && typeof user.grade === 'string'
  )
}


function requireSelfUser(value: unknown): SelfUser {
  if (!isSelfUser(value)) {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回的用户资料不完整',
      200,
    )
  }
  return value
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


async function postJson<T>(
  url: string,
  body: Record<string, string>,
): Promise<T> {
  return request<T>(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}


async function patchJson<T>(
  url: string,
  body: Record<string, string>,
): Promise<T> {
  return request<T>(url, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}


export async function registerStudent(
  input: RegistrationInput,
): Promise<SelfUser> {
  const user = await postJson<unknown>('/api/auth/register', {
    username: input.username,
    password: input.password,
    name: input.name,
    phone: input.phone,
    major_class: input.major_class,
    grade: input.grade,
  })
  return requireSelfUser(user)
}


export async function login(input: LoginInput): Promise<SelfUser> {
  const user = await postJson<unknown>('/api/auth/login', {
    username: input.username,
    password: input.password,
  })
  return requireSelfUser(user)
}


export async function getProfile(): Promise<SelfUser> {
  const user = await request<unknown>('/api/me/profile', {
    method: 'GET',
  })
  return requireSelfUser(user)
}


export async function updateProfile(
  input: ProfileUpdateInput,
): Promise<SelfUser> {
  const body: Record<string, string> = {}
  if (input.name !== undefined) body.name = input.name
  if (input.phone !== undefined) body.phone = input.phone
  if (input.major_class !== undefined) body.major_class = input.major_class
  if (input.grade !== undefined) body.grade = input.grade

  const user = await patchJson<unknown>('/api/me/profile', body)
  return requireSelfUser(user)
}


function isPaginatedUsers(value: unknown): value is PaginatedUsers {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const candidate = value as Record<string, unknown>
  return (
    Array.isArray(candidate.items)
    && typeof candidate.page === 'number'
    && typeof candidate.page_size === 'number'
    && typeof candidate.total === 'number'
  )
}


export async function getAdminUsers(
  page = 1,
  pageSize = 20,
): Promise<PaginatedUsers> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })
  const data = await request<unknown>(
    `/api/admin/users?${params.toString()}`,
    { method: 'GET' },
  )

  if (!isPaginatedUsers(data)) {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回的用户列表格式不正确',
      200,
    )
  }

  for (const item of data.items) {
    requireSelfUser(item)
  }

  return data
}


export async function resetPassword(
  userId: number,
  newPassword: string,
): Promise<ResetPasswordResult> {
  const data = await postJson<unknown>(
    `/api/admin/users/${userId}/reset-password`,
    { new_password: newPassword },
  )

  if (
    typeof data !== 'object'
    || data === null
    || typeof (data as Record<string, unknown>).user_id !== 'number'
  ) {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回的密码重置结果格式不正确',
      200,
    )
  }

  return data as ResetPasswordResult
}


export async function updateUserStatus(
  userId: number,
  input: UpdateUserStatusInput,
): Promise<UpdateUserStatusResult> {
  const data = await patchJson<unknown>(
    `/api/admin/users/${userId}/status`,
    { account_status: input.account_status },
  )

  if (
    typeof data !== 'object'
    || data === null
    || typeof (data as Record<string, unknown>).user_id !== 'number'
    || typeof (data as Record<string, unknown>).account_status !== 'string'
  ) {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      '服务器返回的账号状态更新结果格式不正确',
      200,
    )
  }

  return data as UpdateUserStatusResult
}
