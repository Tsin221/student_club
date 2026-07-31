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

export interface MembershipForLeader {
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
  club_id: number
  member_status: MemberStatus
  club_role: ClubRole
}

export interface LeaderMembersResult {
  items: MembershipForLeader[]
}

export interface PaginatedMemberships {
  items: ClubMembership[]
  page: number
  page_size: number
  total: number
}

// ── S06 招新 ──────────────────────────────────────────────

export type RecruitmentDisplayStatus =
  | '未开始'
  | '进行中'
  | '已满'
  | '已结束'

export interface Recruitment {
  id: number
  title: string
  introduction: string
  requirements: string
  capacity: number
  start_time: string
  end_time: string
  club_id: number
  publisher: {
    id: number
    username: string
  }
  published_at: string
  ended_early: boolean
  display_status: RecruitmentDisplayStatus
  approved_count: number
}

export interface PaginatedRecruitments {
  items: Recruitment[]
  page: number
  page_size: number
  total: number
}

// ── S07 入社申请与通知 ──────────────────────────────────────

export type ApplicationStatus = '待审核' | '已通过' | '已拒绝'

export interface JoinApplication {
  id: number
  applicant_id: number
  applicant_name_snapshot: string
  applicant_major_class_snapshot: string
  club: {
    id: number
    name: string
  }
  recruitment: {
    id: number
    title: string
  }
  reason: string
  applied_at: string
  status: ApplicationStatus
}

export interface PaginatedApplications {
  items: JoinApplication[]
  page: number
  page_size: number
  total: number
}

export interface ApproveApplicationResult {
  application: JoinApplication
  membership: {
    id: number
    user_id: number
    club_id: number
    member_status: string
    club_role: string
  }
}

export type NotificationType =
  | '有人回复了我的帖子'
  | '我的举报已经处理'
  | '我的入社申请已经审核'

export interface Notification {
  id: number
  type: NotificationType
  content: string
}

export interface NotificationsResult {
  items: Notification[]
}

// ── S09 社团公告 ──────────────────────────────────────────────

export type AnnouncementStatus = '正常' | '已删除'

export interface Announcement {
  id: number
  title: string
  content: string
  club_id: number
  publisher: {
    id: number
    username: string
  }
  published_at: string
  is_pinned: boolean
  status: AnnouncementStatus
}

export interface PaginatedAnnouncements {
  items: Announcement[]
  page: number
  page_size: number
  total: number
}

export interface CreateAnnouncementInput {
  title: string
  content: string
  is_pinned?: boolean
}

export interface UpdateAnnouncementInput {
  title?: string
  content?: string
  is_pinned?: boolean
}

export interface DeleteAnnouncementResult {
  id: number
  status: AnnouncementStatus
}

// ── S10 帖子 ──────────────────────────────────────────────────

export type PostStatus = '正常' | '已删除'

export interface Post {
  id: number
  title: string
  content: string
  club_id: number
  author: {
    id: number
    username: string
  }
  is_pinned: boolean
  status: PostStatus
  like_count: number
  liked_by_me: boolean
}

export interface PaginatedPosts {
  items: Post[]
  page: number
  page_size: number
  total: number
}

export interface CreatePostInput {
  title: string
  content: string
}

export interface PinPostInput {
  is_pinned: boolean
}

// ── S11 帖子回复 ──────────────────────────────────────────────

export type ReplyStatus = '正常' | '已删除'

export interface Reply {
  id: number
  content: string
  post_id: number
  author: {
    id: number
    username: string
  }
  status: ReplyStatus
}

export interface PaginatedReplies {
  items: Reply[]
  page: number
  page_size: number
  total: number
}

export interface CreateReplyInput {
  content: string
}
