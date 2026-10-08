from rest_framework import viewsets
from .models import(
      Student, 
      Level, 
      Topic,
      PracticeSession, 
      Question, 
      QuestionAttempt,
      PlacementAssessment,
      PlacementAttempt
    )
from .serializers import( 
    QuestionSerializer, 
    StudentSerializer, 
    LevelSerializer,
    TopicSerializer,
    PracticeSessionSerializer, 
    QuestionAttemptSerializer,
    PlacementAssessmentSerializer,
    PlacementAttemptSerializer,
)


class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer

class LevelViewSet(viewsets.ModelViewSet):
    queryset = Level.objects.all()
    serializer_class = LevelSerializer 

class TopicViewSet(viewsets.ModelViewSet):
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer  

class PracticeSessionViewSet(viewsets.ModelViewSet):
    queryset = PracticeSession.objects.all()
    serializer_class = PracticeSessionSerializer

class QuestionViewSet(viewsets.ModelViewSet):
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer

class QuestionAttemptViewSet(viewsets.ModelViewSet):
    queryset = QuestionAttempt.objects.all()
    serializer_class = QuestionAttemptSerializer    

class PlacementAssessmentViewSet(viewsets.ModelViewSet):
    queryset = PlacementAssessment.objects.all()
    serializer_class = PlacementAssessmentSerializer    
class PlacementAttemptViewSet(viewsets.ModelViewSet):
    queryset = PlacementAttempt.objects.all()
    serializer_class = PlacementAttemptSerializer   