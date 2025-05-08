# views.py

from rest_framework import generics
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.serializers import ModelSerializer
from django.shortcuts import redirect


# views.py


