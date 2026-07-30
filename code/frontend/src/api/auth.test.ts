import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  ApiRequestError,
  getProfile,
  registerStudent,
  updateProfile,
} from './auth'


const student = {
  id: 1,
  username: 'student_2026',
  platform_role: 'student' as const,
  account_status: 'active' as const,
  registered_at: '2026-07-29T10:00:00+08:00',
  name: '张同学',
  phone: '13800000000',
  major_class: '计算机科学与技术1班',
  grade: '2026',
}


function apiResponse(data: unknown, init?: ResponseInit) {
  return new Response(JSON.stringify(data), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
}


afterEach(() => {
  vi.unstubAllGlobals()
})


describe('registerStudent', () => {
  it('initializes CSRF and submits only allowed registration fields', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        apiResponse({
          code: 'SUCCESS',
          message: 'CSRF 令牌初始化成功',
          data: { csrf_token: 'csrf-token' },
        }),
      )
      .mockResolvedValueOnce(
        apiResponse(
          {
            code: 'SUCCESS',
            message: '注册成功，请登录',
            data: student,
          },
          { status: 201 },
        ),
      )
    vi.stubGlobal('fetch', fetchMock)

    const result = await registerStudent({
      username: 'student_2026',
      password: 'StrongPass!2026',
      name: '张同学',
      phone: '13800000000',
      major_class: '计算机科学与技术1班',
      grade: '2026',
    })

    expect(result).toEqual(student)
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/auth/csrf',
      expect.objectContaining({
        credentials: 'same-origin',
        method: 'GET',
      }),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/auth/register',
      expect.objectContaining({
        credentials: 'same-origin',
        method: 'POST',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
          'X-CSRFToken': 'csrf-token',
        }),
      }),
    )
  })
})


describe('getProfile', () => {
  it('exposes the stable API error code to route guards', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        apiResponse(
          {
            code: 'UNAUTHENTICATED',
            message: '请先登录',
            data: null,
          },
          { status: 401 },
        ),
      ),
    )

    const request = getProfile()

    await expect(request).rejects.toBeInstanceOf(ApiRequestError)
    await expect(request).rejects.toMatchObject({
      code: 'UNAUTHENTICATED',
      message: '请先登录',
    })
  })

  it('rejects a SUCCESS envelope with an invalid profile shape', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        apiResponse({
          code: 'SUCCESS',
          message: '本人资料获取成功',
          data: { id: 1, username: 'incomplete' },
        }),
      ),
    )

    await expect(getProfile()).rejects.toMatchObject({
      code: 'INVALID_RESPONSE',
    })
  })
})


describe('updateProfile', () => {
  it('initializes CSRF and submits a PATCH with allowed fields', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        apiResponse({
          code: 'SUCCESS',
          message: 'CSRF 令牌初始化成功',
          data: { csrf_token: 'csrf-token-patch' },
        }),
      )
      .mockResolvedValueOnce(
        apiResponse({
          code: 'SUCCESS',
          message: '资料修改成功',
          data: { ...student, name: '新姓名', phone: '13700000001' },
        }),
      )
    vi.stubGlobal('fetch', fetchMock)

    const result = await updateProfile({
      name: '新姓名',
      phone: '13700000001',
    })

    expect(result.name).toBe('新姓名')
    expect(result.phone).toBe('13700000001')

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/auth/csrf',
      expect.objectContaining({
        credentials: 'same-origin',
        method: 'GET',
      }),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/me/profile',
      expect.objectContaining({
        credentials: 'same-origin',
        method: 'PATCH',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
          'X-CSRFToken': 'csrf-token-patch',
        }),
      }),
    )
  })

  it('rejects an error response with the stable error code', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(
          apiResponse({
            code: 'SUCCESS',
            message: 'CSRF 令牌初始化成功',
            data: { csrf_token: 'csrf-token-patch' },
          }),
        )
        .mockResolvedValueOnce(
          apiResponse(
            {
              code: 'INVALID_REQUEST',
              message: '请求包含不允许修改的字段',
              data: null,
            },
            { status: 400 },
          ),
        ),
    )

    await expect(
      updateProfile({ username: 'hacked' } as unknown as Record<string, string>),
    ).rejects.toMatchObject({
      code: 'INVALID_REQUEST',
    })
  })
})
