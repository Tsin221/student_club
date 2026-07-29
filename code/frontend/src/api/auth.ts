import type {
  LoginInput,
  RegistrationInput,
  SelfUser,
} from '../types/user'
import {
  isSuccessResponse,
  type ApiResponse,
} from './response'


interface CsrfData {
  csrf_token: string
}


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


async function getCsrfToken(): Promise<string> {
  const data = await request<CsrfData>('/api/auth/csrf', {
    method: 'GET',
  })
  if (typeof data.csrf_token !== 'string' || !data.csrf_token) {
    throw new ApiRequestError(
      'INVALID_RESPONSE',
      'CSRF 令牌初始化失败',
      200,
    )
  }
  return data.csrf_token
}


async function postWithCsrf<T>(
  url: string,
  body: Record<string, string>,
): Promise<T> {
  const csrfToken = await getCsrfToken()
  return request<T>(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken,
    },
    body: JSON.stringify(body),
  })
}


export async function registerStudent(
  input: RegistrationInput,
): Promise<SelfUser> {
  const user = await postWithCsrf<unknown>('/api/auth/register', {
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
  const user = await postWithCsrf<unknown>('/api/auth/login', {
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
