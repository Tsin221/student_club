import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  ApiRequestError,
  getAdminUsers,
  getProfile,
  registerStudent,
  resetPassword,
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
  it('submits only allowed registration fields', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
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
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/auth/register',
      expect.objectContaining({
        credentials: 'same-origin',
        method: 'POST',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
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
  it('submits a PATCH with allowed fields', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
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

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/me/profile',
      expect.objectContaining({
        credentials: 'same-origin',
        method: 'PATCH',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
        }),
      }),
    )
  })

  it('rejects an error response with the stable error code', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
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


describe('getAdminUsers', () => {
  it('sends pagination query params and returns paginated users', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        apiResponse({
          code: 'SUCCESS',
          message: '学生用户列表获取成功',
          data: {
            items: [student],
            page: 1,
            page_size: 20,
            total: 1,
          },
        }),
      ),
    )

    const result = await getAdminUsers(1, 20)

    expect(result.items).toEqual([student])
    expect(result.page).toBe(1)
    expect(result.page_size).toBe(20)
    expect(result.total).toBe(1)

    expect(fetch).toHaveBeenCalledWith(
      '/api/admin/users?page=1&page_size=20',
      expect.objectContaining({
        credentials: 'same-origin',
        method: 'GET',
      }),
    )
  })

  it('rejects a malformed paginated response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        apiResponse({
          code: 'SUCCESS',
          message: '学生用户列表获取成功',
          data: { items: 'not-an-array', page: 1 },
        }),
      ),
    )

    await expect(getAdminUsers()).rejects.toMatchObject({
      code: 'INVALID_RESPONSE',
    })
  })
})


describe('resetPassword', () => {
  it('POSTs new password for a student', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      apiResponse({
        code: 'SUCCESS',
        message: '密码重置成功',
        data: { user_id: 1 },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await resetPassword(1, 'NewStrongPass!2026')

    expect(result.user_id).toBe(1)

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/admin/users/1/reset-password',
      expect.objectContaining({
        credentials: 'same-origin',
        method: 'POST',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
        }),
      }),
    )
  })

  it('rejects an error response with the stable error code', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        apiResponse(
          {
            code: 'VALIDATION_ERROR',
            message: '密码太常见。',
            data: null,
          },
          { status: 422 },
        ),
      ),
    )

    await expect(
      resetPassword(1, '12345678'),
    ).rejects.toMatchObject({
      code: 'VALIDATION_ERROR',
    })
  })
})
