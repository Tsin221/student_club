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
