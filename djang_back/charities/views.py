from rest_framework import status, generics
from rest_framework.decorators import api_view
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Benefactor, Charity
from accounts.permissions import IsCharityOwner, IsBenefactor
from charities.models import Task
from charities.serializers import (
    TaskSerializer, CharitySerializer, BenefactorSerializer
)


class BenefactorRegistration(APIView):
    permission_classes = (IsAuthenticated,)
    queryset = Benefactor.objects.all()

    def post(self, request):
        serializer = BenefactorSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=self.request.user)
        return Response(status=status.HTTP_201_CREATED)


class CharityRegistration(APIView):
    permission_classes = (IsAuthenticated,)
    queryset = Charity.objects.all()

    def post(self, request):
        serializer = CharitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=self.request.user)
        return Response(status=status.HTTP_201_CREATED)


class Tasks(generics.ListCreateAPIView):
    serializer_class = TaskSerializer

    def get_queryset(self):
        return Task.objects.all_related_tasks_to_user(self.request.user)

    def post(self, request, *args, **kwargs):
        data = {
            **request.data,
            "charity_id": request.user.charity.id
        }
        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            self.permission_classes = [IsAuthenticated, ]
        else:
            self.permission_classes = [IsCharityOwner, ]

        return [permission() for permission in self.permission_classes]

    def filter_queryset(self, queryset):
        filter_lookups = {}
        for name, value in Task.filtering_lookups:
            param = self.request.GET.get(value)
            if param:
                filter_lookups[name] = param
        exclude_lookups = {}
        for name, value in Task.excluding_lookups:
            param = self.request.GET.get(value)
            if param:
                exclude_lookups[name] = param

        return queryset.filter(**filter_lookups).exclude(**exclude_lookups)


class TaskRequest(APIView):

    def get(self, request, task_id):
        task = get_object_or_404(Task, id=task_id)
        if self.request.user.is_benefactor:
            if task.state != "P":
                return Response(data={'detail': 'This task is not pending.'}, status=status.HTTP_404_NOT_FOUND)
            else:
                task.state = "W"
                task.assigned_benefactor = Benefactor.objects.get(user=self.request.user)
                task.save()
                return Response(data={'detail': 'Request sent.'}, status=status.HTTP_200_OK)
        else:
            return Response({'detail': 'Request sent.'}, status=status.HTTP_403_FORBIDDEN)


class TaskResponse(APIView):

    def post(self, request, task_id):
        task = get_object_or_404(Task, id=task_id)
        if self.request.user.is_charity:
            res = request.data["response"]
            if res != "R" and res != "A":
                return Response(data={'detail': 'Required field ("A" for accepted / "R" for rejected)'},
                                status=status.HTTP_400_BAD_REQUEST)
            elif task.state != "W":
                return Response(data={'detail': 'This task is not waiting.'},
                                status=status.HTTP_404_NOT_FOUND)
            elif res == "A":
                task.state = "A"
                task.save()
                return Response(data={'detail': 'Response sent.'},
                                status=status.HTTP_200_OK)
            elif res == "R":
                task.state = "P"
                task.assigned_benefactor = None
                task.save()
                return Response(data={'detail': 'Response sent.'},
                                status=status.HTTP_200_OK)
        else:
            return Response({'detail': 'Request sent.'}, status=status.HTTP_403_FORBIDDEN)


class DoneTask(APIView):

    def post(self, request, task_id):
        task = get_object_or_404(Task, id=task_id)
        if self.request.user.is_charity:
            if task.state != "A":
                return Response(data={'detail': 'Task is not assigned yet.'},
                                status=status.HTTP_404_NOT_FOUND)
            else:
                task.state = "D"
                task.save()
                return Response(data={'detail': 'Task has been done successfully.'},
                                status=status.HTTP_200_OK)
        else:
            return Response({'detail': 'Request sent.'}, status=status.HTTP_403_FORBIDDEN)
