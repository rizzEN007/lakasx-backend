from rest_framework import viewsets
from .models import  Student, PracticeSession, Question
from .serializers import QuestionSerializer, StudentSerializer, PracticeSessionSerializer


class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer

class PracticeSessionViewSet(viewsets.ModelViewSet):
    queryset = PracticeSession.objects.all()
    serializer_class = PracticeSessionSerializer

class QuestionViewSet(viewsets.ModelViewSet):
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer