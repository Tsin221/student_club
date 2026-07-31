export interface Club {
  id: number
  name: string
  category: ClubCategory
  introduction: string
  logo: string
  created_at: string
  status: ClubStatus
}

export type ClubCategory =
  | '文化艺术'
  | '体育竞技'
  | '学术科技'
  | '公益实践'
  | '兴趣爱好'
  | '其他'

export const CLUB_CATEGORIES: ClubCategory[] = [
  '文化艺术',
  '体育竞技',
  '学术科技',
  '公益实践',
  '兴趣爱好',
  '其他',
]

export type ClubStatus = 'normal' | 'cancelled'

export interface ClubMembership {
  id: number
  user: {
    id: number
    username: string
    name: string
    phone: string
    major_class: string
    grade: string
    account_status: 'active' | 'disabled'
  }
  club: {
    id: number
    name: string
    status: ClubStatus
  }
  member_status: MemberStatus
  club_role: ClubRole
}

export interface MyMembership {
  id: number
  club: {
    id: number
    name: string
    category: ClubCategory
    logo: string
    status: ClubStatus
  }
  member_status: MemberStatus
  club_role: ClubRole
}

export type MemberStatus = 'active' | 'exited' | 'removed'

export type ClubRole = 'leader' | 'member'

export interface PaginatedClubs {
  items: Club[]
  page: number
  page_size: number
  total: number
}

export interface CreateClubResult {
  club: Club
  leaders: ClubMembership[]
}

export interface MyMembershipsResult {
  items: MyMembership[]
}
