from rest_framework.viewsets import ModelViewSet
from .models import Restaurant, Table
from .serializers import RestaurantSerializer, TableSerializer
from config.permissions import IsManagerOrAdmin

class RestaurantViewSet(ModelViewSet):
    queryset = Restaurant.objects.all()
    serializer_class = RestaurantSerializer
    permission_classes = [IsManagerOrAdmin]


class TableViewSet(ModelViewSet):
    queryset = Table.objects.all()
    serializer_class = TableSerializer
    permission_classes = [IsManagerOrAdmin]

