export interface ApiResponse<T> {
  code: string
  message: string
  data: T | null
}


export interface SuccessResponse<T> extends ApiResponse<T> {
  code: 'SUCCESS'
  data: T
}


export function isSuccessResponse<T>(
  response: ApiResponse<T>,
): response is SuccessResponse<T> {
  return response.code === 'SUCCESS' && response.data !== null
}
