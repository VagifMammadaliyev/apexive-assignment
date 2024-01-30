from rest_framework import serializers

from fulfillment.models import CourierProfile
from core.serializers.admin import CityCompactSerializer


class CourierProfileSerializer(serializers.ModelSerializer):
    city = CityCompactSerializer(read_only=True)

    class Meta:
        model = CourierProfile
        fields = ["city"]
