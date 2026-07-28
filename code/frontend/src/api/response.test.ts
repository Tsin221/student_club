import { describe, expect, it } from 'vitest'

import {
  isSuccessResponse,
  type ApiResponse,
} from './response'


describe('isSuccessResponse', () => {
  it('recognizes the confirmed SUCCESS envelope', () => {
    const response: ApiResponse<{ ready: boolean }> = {
      code: 'SUCCESS',
      message: '基础检查通过',
      data: { ready: true },
    }

    expect(isSuccessResponse(response)).toBe(true)
  })

  it('rejects an error envelope with null data', () => {
    const response: ApiResponse<never> = {
      code: 'INVALID_REQUEST',
      message: '请求无效',
      data: null,
    }

    expect(isSuccessResponse(response)).toBe(false)
  })
})
