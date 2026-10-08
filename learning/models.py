from django.db import models


class Student(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

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

    def __str__(self):
        return f"{self.student.name} - {self.started_at}"

class Question(models.Model):
    text = models.TextField()
    answer = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

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

    def __str__(self):
        return f"{self.question.text} - {self.is_correct}"