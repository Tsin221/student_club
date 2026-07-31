import {
  ApiRequestError,
  getProfile,
} from '../api/auth'


export async function redirectAuthenticatedStudent(
  navigate: (path: string) => void,
  showError: (message: string) => void,
) {
  try {
    await getProfile()
    navigate('/student')
  } catch (error) {
    if (error instanceof ApiRequestError) {
      // 管理员已登录 → 跳转到管理员工作台
      if (error.code === 'FORBIDDEN') {
        navigate('/admin/users')
        return
      }
      // 预期内的未登录或停用状态，不提示
      if (['UNAUTHENTICATED', 'ACCOUNT_DISABLED'].includes(error.code)) {
        return
      }
      showError(error.message)
    }
  }
}
