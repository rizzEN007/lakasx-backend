from django.db import models


class Student(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

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