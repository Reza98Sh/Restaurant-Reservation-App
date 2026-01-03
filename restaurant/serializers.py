from rest_framework import serializers
from .models import Restaurant, Table


class TableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Table
        fields = '__all__'


class RestaurantSerializer(serializers.ModelSerializer):
    tables = TableSerializer(many=True, read_only=True)
    
    class Meta:
        model = Restaurant
        fields = '__all__'
