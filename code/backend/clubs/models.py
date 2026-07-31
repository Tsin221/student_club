from django.conf import settings
from django.db import models


#社团
class Club(models.Model):


    #社团类别固定枚举
    class Category(models.TextChoices):
        ARTS = "文化艺术", "文化艺术"
        SPORTS = "体育竞技", "体育竞技"
        ACADEMIC = "学术科技", "学术科技"
        WELFARE = "公益实践", "公益实践"
        HOBBY = "兴趣爱好", "兴趣爱好"
        OTHER = "其他", "其他"


    #社团状态
    class Status(models.TextChoices):
        ACTIVE = "normal", "正常"
        CANCELLED = "cancelled", "已注销"


    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
    )
    introduction = models.TextField()
    logo = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )


    class Meta:
        db_table = "club"
        indexes = [
            models.Index(
                fields=["status", "category"],
                name="club_status_category_idx",
            ),
        ]


    def __str__(self):
        return self.name


#社团成员关系
class ClubMembership(models.Model):


    #成员状态
    class MemberStatus(models.TextChoices):
        ACTIVE = "active", "在社"
        EXITED = "exited", "已退出"
        REMOVED = "removed", "已移除"


    #社团身份
    class ClubRole(models.TextChoices):
        LEADER = "leader", "负责人"
        MEMBER = "member", "普通成员"


    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="memberships",
        db_column="user_id",
    )
    club = models.ForeignKey(
        Club,
        on_delete=models.PROTECT,
        related_name="memberships",
        db_column="club_id",
    )
    member_status = models.CharField(
        max_length=20,
        choices=MemberStatus.choices,
        default=MemberStatus.ACTIVE,
    )
    club_role = models.CharField(
        max_length=20,
        choices=ClubRole.choices,
        default=ClubRole.MEMBER,
    )


    class Meta:
        db_table = "club_membership"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "club"],
                name="unique_user_club_membership",
            ),
        ]
        indexes = [
            models.Index(
                fields=["club", "member_status", "club_role"],
                name="memb_club_status_role_idx",
            ),
            models.Index(
                fields=["user", "member_status"],
                name="memb_user_status_idx",
            ),
        ]


    def __str__(self):
        return f"{self.user.username} → {self.club.name} ({self.club_role})"


#招新信息
class Recruitment(models.Model):

    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=200)
    introduction = models.TextField()
    requirements = models.TextField()
    capacity = models.PositiveIntegerField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    club = models.ForeignKey(
        Club,
        on_delete=models.PROTECT,
        related_name="recruitments",
        db_column="club_id",
    )
    publisher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="published_recruitments",
        db_column="publisher_id",
    )
    published_at = models.DateTimeField(auto_now_add=True)
    ended_early = models.BooleanField(default=False)

    class Meta:
        db_table = "recruitment"
        indexes = [
            models.Index(
                fields=["club", "ended_early", "start_time", "end_time"],
                name="recruit_club_early_time_idx",
            ),
            models.Index(
                fields=["publisher"],
                name="recruit_publisher_idx",
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.club.name})"


#入社申请
class JoinApplication(models.Model):

    class Status(models.TextChoices):
        PENDING = "待审核", "待审核"
        APPROVED = "已通过", "已通过"
        REJECTED = "已拒绝", "已拒绝"

    id = models.BigAutoField(primary_key=True)
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="join_applications",
        db_column="applicant_id",
    )
    applicant_name_snapshot = models.CharField(max_length=50)
    applicant_major_class_snapshot = models.CharField(max_length=100)
    club = models.ForeignKey(
        Club,
        on_delete=models.PROTECT,
        related_name="join_applications",
        db_column="club_id",
    )
    recruitment = models.ForeignKey(
        Recruitment,
        on_delete=models.PROTECT,
        related_name="join_applications",
        db_column="recruitment_id",
    )
    reason = models.TextField()
    applied_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    class Meta:
        db_table = "join_application"
        indexes = [
            models.Index(
                fields=["applicant", "status"],
                name="ja_applicant_status_idx",
            ),
            models.Index(
                fields=["club", "status", "applied_at"],
                name="ja_club_status_time_idx",
            ),
            models.Index(
                fields=["recruitment", "applicant", "status"],
                name="ja_rec_app_status_idx",
            ),
        ]

    def __str__(self):
        return f"{self.applicant.username} → {self.club.name}（{self.status}）"


#站内通知
class Notification(models.Model):

    class Type(models.TextChoices):
        REPLY = "有人回复了我的帖子", "有人回复了我的帖子"
        REPORT_PROCESSED = "我的举报已经处理", "我的举报已经处理"
        APPLICATION_REVIEWED = "我的入社申请已经审核", "我的入社申请已经审核"

    id = models.BigAutoField(primary_key=True)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="notifications",
        db_column="recipient_id",
    )
    type = models.CharField(max_length=50, choices=Type.choices)
    content = models.TextField()

    class Meta:
        db_table = "notification"
        indexes = [
            models.Index(
                fields=["recipient", "type"],
                name="notif_recipient_type_idx",
            ),
        ]

    def __str__(self):
        return f"[{self.type}] → {self.recipient.username}"


#社团公告
class Announcement(models.Model):


    #公告状态
    class Status(models.TextChoices):
        NORMAL = "正常", "正常"
        DELETED = "已删除", "已删除"


    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=200)
    content = models.TextField()
    club = models.ForeignKey(
        Club,
        on_delete=models.PROTECT,
        related_name="announcements",
        db_column="club_id",
    )
    publisher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="published_announcements",
        db_column="publisher_id",
    )
    published_at = models.DateTimeField(auto_now_add=True)
    is_pinned = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NORMAL,
    )

    class Meta:
        db_table = "announcement"
        indexes = [
            models.Index(
                fields=["club", "status", "is_pinned", "published_at"],
                name="ann_club_status_pin_time_idx",
            ),
            models.Index(
                fields=["publisher"],
                name="ann_publisher_idx",
            ),
        ]

    def __str__(self):
        return f"{self.title}（{self.club.name}）"


# ── S10：帖子 ────────────────────────────────────────────


class Post(models.Model):

    """社团帖子 —— 发布后不可修改，用自增 ID 表示发布先后。"""

    class Status(models.TextChoices):
        NORMAL = "正常", "正常"
        DELETED = "已删除", "已删除"

    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=255)
    content = models.TextField()
    club = models.ForeignKey(
        Club,
        on_delete=models.PROTECT,
        related_name="posts",
        db_column="club_id",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="posts",
        db_column="author_id",
    )
    is_pinned = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NORMAL,
    )

    class Meta:
        db_table = "post"
        indexes = [
            models.Index(
                fields=["club", "status", "is_pinned"],
                name="post_club_status_pin_idx",
            ),
            models.Index(
                fields=["author"],
                name="post_author_idx",
            ),
        ]

    def __str__(self):
        return f"{self.title}（{self.club.name}）"


# ── S11：帖子回复 ────────────────────────────────────────────


class Reply(models.Model):

    """帖子回复 —— 只直接回复帖子，不支持多层回复。"""

    class Status(models.TextChoices):
        NORMAL = "正常", "正常"
        DELETED = "已删除", "已删除"

    id = models.BigAutoField(primary_key=True)
    content = models.TextField()
    post = models.ForeignKey(
        Post,
        on_delete=models.PROTECT,
        related_name="replies",
        db_column="post_id",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="replies",
        db_column="author_id",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NORMAL,
    )

    class Meta:
        db_table = "reply"
        indexes = [
            models.Index(
                fields=["post", "status"],
                name="reply_post_status_idx",
            ),
            models.Index(
                fields=["author"],
                name="reply_author_idx",
            ),
        ]

    def __str__(self):
        return f"回复 #{self.id} → 帖子 #{self.post_id}"
