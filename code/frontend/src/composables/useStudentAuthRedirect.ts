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
    if (
      error instanceof ApiRequestError
      && !['UNAUTHENTICATED', 'ACCOUNT_DISABLED'].includes(error.code)
    ) {
      showError(error.message)
    }
  }
}
