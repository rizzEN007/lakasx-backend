from django.db import models
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone

# 0 = Kindergarten, 1-12 = Grade 1-12
GRADE_VALIDATORS = [MinValueValidator(0), MaxValueValidator(12)]

class Student(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    school = models.ForeignKey(
        "School",
        on_delete=models.PROTECT,
        related_name="students",
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="student_profile",
    )
    grade = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=GRADE_VALIDATORS,
    )
    total_xp = models.PositiveIntegerField(default=0)
    coin_balance = models.PositiveIntegerField(default=0)
    streak_count = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_goal_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["school","email"],
                name="unique_student_email_per_school",
            ),
        ]

    def __str__(self):
        return self.name

class Level(models.Model):
    name = models.CharField(max_length=50)
    order = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return self.name

class Topic(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name

class PracticeSession(models.Model):
    student = models.ForeignKey(
        Student, 
        on_delete=models.CASCADE,
        related_name="practice_sessions",
        )
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    last_activity_at = models.DateTimeField(default=timezone.now)
    current_question = models.ForeignKey(
        "Question",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    served_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student"],
                condition=models.Q(ended_at__isnull=True),
                name="one_open_session_per_student",
            ),
        ]

    def __str__(self):
        return f"{self.student.name} - {self.started_at}"

class Question(models.Model):
    level = models.ForeignKey(
        Level,
        on_delete=models.PROTECT,
        related_name="questions",
        null=True,
        blank=True, 
    )
    topic = models.ForeignKey(
        Topic,
        on_delete=models.PROTECT,
        related_name="questions",
        null=True,
        blank=True,
    )
    text = models.TextField()
    answer = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    grade = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=GRADE_VALIDATORS,
    )
    

    class Meta:
        indexes = [models.Index(fields=["grade", "topic"])]

    def __str__(self):
        return self.text

class QuestionAttempt(models.Model):
    question = models.ForeignKey(
        Question, 
        on_delete=models.CASCADE,
        related_name="attempts",
        )
    practice_session = models.ForeignKey(
        PracticeSession, 
        on_delete=models.CASCADE,
        related_name="question_attempts",
        )
    answer_given = models.TextField()
    attempted_at = models.DateTimeField(auto_now_add=True)
    is_correct = models.BooleanField(default=False)
    time_taken_seconds = models.PositiveIntegerField(null=True, blank=True)
    is_first_try = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.question.text} - {self.is_correct}"

class PlacementAssessment(models.Model):
    student = models.ForeignKey(
        Student, 
        on_delete=models.CASCADE,
        related_name="placement_assessments",
        )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    assigned_level = models.ForeignKey(
        Level,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="placement_students",
    )
    def __str__(self):
        return f"{self.student.name} - Placement Assessment"
    
class PlacementAttempt(models.Model):

    assessment = models.ForeignKey(
        PlacementAssessment, 
        on_delete=models.CASCADE,
        related_name="attempts",
        )
    
    question = models.ForeignKey(
        Question, 
        on_delete=models.PROTECT,
        related_name="placement_attempts",
        )
    answer_given = models.TextField()
    attempted_at = models.DateTimeField(auto_now_add=True)
    is_correct = models.BooleanField(default=False)

    class Meta:
            constraints = [
                models.UniqueConstraint(
                    fields=["assessment", "question"],
                    name="unique_placement_attempt_per_question",
                ),
            ]

    def __str__(self):
        return f"{self.question.text} - {self.is_correct}"

class School(models.Model):
    name = models.CharField(max_length=150)
    code = models.SlugField(max_length=50, unique=True)
    contact_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class SchoolMembership(models.Model):

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "School Administrator"
        TEACHER = "TEACHER", "Teacher"
        STUDENT = "STUDENT", "Student"
        PARENT = "PARENT", "Parent"

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="school_memberships",
    )
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["school", "user"],
                name="unique_user_membership_per_school",
            ),
        ]

    def __str__(self):
        return f"{self.user} — {self.school} ({self.role})"


class Classroom(models.Model):
    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="classrooms",
    )
    name = models.CharField(max_length=100)
    grade_level = models.CharField(max_length=30, blank=True)
    academic_year = models.CharField(max_length=20, blank=True)
    teachers = models.ManyToManyField(
        SchoolMembership,
        related_name="teaching_classrooms",
        blank=True,
    )
    students = models.ManyToManyField(
        SchoolMembership,
        related_name="enrolled_classrooms",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["school", "name", "academic_year"],
                name="unique_classroom_per_school_year",
            ),
        ]

    def __str__(self):
        return f"{self.school.name} — {self.name}" 

class XPEvent(models.Model):
    class Reason(models.TextChoices):
        CORRECT_ANSWER = "CORRECT_ANSWER", "Correct answer"
        FIRST_TRY_BONUS = "FIRST_TRY_BONUS", "First-try bonus"
        SESSION_COMPLETE = "SESSION_COMPLETE", "Session completed"

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="xp_events",
    )
    amount = models.PositiveIntegerField()
    reason = models.CharField(max_length=20, choices=Reason.choices)
    practice_session = models.ForeignKey(
        PracticeSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="xp_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["student", "created_at"])]

    def __str__(self):
        return f"{self.student.name} +{self.amount} ({self.reason})"

class DailyActivity(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="daily_activity",
    )
    date = models.DateField()
    questions_answered = models.PositiveIntegerField(default=0)
    xp_earned = models.PositiveIntegerField(default=0)
    goal_met = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "date"],
                name="unique_daily_activity_per_student_day",
            ),
        ]

    def __str__(self):
        return f"{self.student.name} {self.date}"

class GuardianLink(models.Model):
    class Relationship(models.TextChoices):
        PRIMARY = "PRIMARY", "Primary guardian"
        SECONDARY = "SECONDARY", "Secondary guardian (view-only)"

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="guardian_links",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="guardian_links",
    )
    relationship = models.CharField(max_length=10, choices=Relationship.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "user"],
                name="unique_guardian_per_student",
            ),
            models.UniqueConstraint(
                fields=["student"],
                condition=models.Q(relationship="PRIMARY"),
                name="one_primary_guardian_per_student",
            ),
            models.UniqueConstraint(
                fields=["student"],
                condition=models.Q(relationship="SECONDARY"),
                name="one_secondary_guardian_per_student",
            ),
        ]

    def __str__(self):
        return f"{self.user} → {self.student.name} ({self.relationship})"

class StoreItem(models.Model):
    class Slot(models.TextChoices):
        HAT = "HAT", "Hat"
        OUTFIT = "OUTFIT", "Outfit"
        BACKGROUND = "BACKGROUND", "Background"

    name = models.CharField(max_length=100)
    slot = models.CharField(max_length=12, choices=Slot.choices)
    price = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    asset_key = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price__gt=0),
                name="store_item_price_positive",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.slot}, {self.price})"


class CoinTransaction(models.Model):
    class Reason(models.TextChoices):
        CORRECT_ANSWER = "CORRECT_ANSWER", "Correct answer"
        FIRST_TRY_BONUS = "FIRST_TRY_BONUS", "First-try bonus"
        SESSION_COMPLETE = "SESSION_COMPLETE", "Session completed"
        DAILY_GOAL = "DAILY_GOAL", "Daily goal met"
        STREAK_MILESTONE = "STREAK_MILESTONE", "Streak milestone"
        PURCHASE = "PURCHASE", "Store purchase"

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="coin_transactions",
    )
    amount = models.IntegerField()  # positive = earned, negative = spent
    balance_after = models.PositiveIntegerField()
    reason = models.CharField(max_length=20, choices=Reason.choices)
    practice_session = models.ForeignKey(
        "PracticeSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coin_transactions",
    )
    store_item = models.ForeignKey(
        StoreItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchases",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["student", "created_at"])]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(amount=0),
                name="coin_transaction_amount_nonzero",
            ),
        ]

    def __str__(self):
        return f"{self.student.name} {self.amount:+d} ({self.reason})"


class StudentItem(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="owned_items",
    )
    item = models.ForeignKey(
        StoreItem,
        on_delete=models.PROTECT,
        related_name="owners",
    )
    slot = models.CharField(max_length=12, choices=StoreItem.Slot.choices)
    equipped = models.BooleanField(default=False)
    acquired_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "item"],
                name="unique_item_per_student",
            ),
            models.UniqueConstraint(
                fields=["student", "slot"],
                condition=models.Q(equipped=True),
                name="one_equipped_item_per_slot",
            ),
        ]

    def __str__(self):
        return f"{self.student.name}: {self.item.name}"