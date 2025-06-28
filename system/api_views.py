from rest_framework import generics, permissions, status, views, viewsets
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from .models import Movie, Watchlist, CuratedList, SubscriptionPlan, UserSubscription
from .serializers import UserSerializer, MovieSerializer, WatchlistSerializer, CuratedListSerializer, SubscriptionPlanSerializer, UserSubscriptionSerializer

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
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
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        genre = request.query_params.get('genre')
        era = request.query_params.get('era')
        rating = request.query_params.get('rating')
        # Use your decision tree logic here
        from .views import recommend_movies
        recs, _ = recommend_movies(genre, era, rating)
        serializer = MovieSerializer(recs, many=True)
        return Response(serializer.data)

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

class AnalyticsView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        # Stub: return sample analytics data
        return Response({'by_era': {'1980s': 12, '1990s': 19, '2000s': 7, '2010s': 14, '2020s': 9}})

class SubscriptionPlanViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SubscriptionPlan.objects.filter(is_active=True)
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [permissions.AllowAny]

class UserSubscriptionView(generics.RetrieveAPIView):
    serializer_class = UserSubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_object(self):
        return UserSubscription.objects.get(user=self.request.user) 