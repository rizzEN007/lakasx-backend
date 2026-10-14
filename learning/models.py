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
    