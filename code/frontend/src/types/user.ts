export interface SelfUser {
  id: number
  username: string
  platform_role: 'student' | 'system_admin'
  account_status: 'active' | 'disabled'
  registered_at: string
  name: string
  phone: string
  major_class: string
  grade: string
}


export interface RegistrationInput {
  username: string
  password: string
  name: string
  phone: string
  major_class: string
  grade: string
}


export interface LoginInput {
  username: string
  password: string
}


export interface ProfileUpdateInput {
  name?: string
  phone?: string
  major_class?: string
  grade?: string
}
