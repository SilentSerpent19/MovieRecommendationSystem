from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from rest_framework import generics, permissions, status, views, viewsets
from rest_framework.response import Response

from .forms import RecommendationForm
from .models import CuratedList, Watchlist
from .recommender import recommend
from .serializers import (
    CuratedListSerializer,
    MovieSerializer,
    RegisterSerializer,
    UserSerializer,
    WatchlistSerializer,
)


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

class LoginView(views.APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return Response({'success': True})
        return Response({'success': False, 'error': 'Invalid credentials'}, status=400)

class ProfileView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_object(self):
        return self.request.user

class MovieRecommendationView(views.APIView):
    """GET /api/recommend/?genre=&era=&rating=&mood=&k= -> ranked movies with reasons."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        form = RecommendationForm(request.query_params)
        if not form.is_valid():
            return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)
        k = min(max(int(request.query_params.get('k', 10)), 1), 50)
        result = recommend(request.user, form.to_filters(), k=k, session_key=request.session.session_key or '')
        return Response({
            'request_id': result.request_id,
            'strategy': result.strategy,
            'model_version': result.model_version,
            'relaxed_filters': result.relaxed,
            'results': [{'movie': MovieSerializer(r.movie).data, 'score': r.score, 'reason': r.reason}
                        for r in result.items],
        })


class WatchlistViewSet(viewsets.ModelViewSet):
    serializer_class = WatchlistSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        return Watchlist.objects.filter(user=self.request.user)
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class CuratedListViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CuratedList.objects.filter(is_active=True)
    serializer_class = CuratedListSerializer
    permission_classes = [permissions.IsAuthenticated]
