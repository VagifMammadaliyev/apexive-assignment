from rest_framework import serializers

from core.serializers.admin import CountryCompactSerializer
from fulfillment.serializers.admin.customers import CustomerReadSerializer
from fulfillment.models import ShoppingAssistantProfile


class ShoppingAssistantProfileReadSerializer(serializers.ModelSerializer):
    user = CustomerReadSerializer(read_only=True)
    countries = CountryCompactSerializer(many=True, read_only=True)

    class Meta:
        model = ShoppingAssistantProfile
        fields = ["id", "user", "countries"]


class ShoppingAssistantProfileWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShoppingAssistantProfile
        fields = ["countries"]

    def to_representation(self, instance):
        return ShoppingAssistantProfileReadSerializer(instance).data
