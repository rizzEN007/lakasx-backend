from unittest import result

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .services.placement import analyze_placement
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

    @action(detail=True, methods=["get"])
    def analyze(self, request, pk=None):
        result = analyze_placement(pk)
        return Response(result)
     
class PlacementAttemptViewSet(viewsets.ModelViewSet):
    queryset = PlacementAttempt.objects.all()
    serializer_class = PlacementAttemptSerializer   