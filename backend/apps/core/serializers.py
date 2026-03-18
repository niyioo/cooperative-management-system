from rest_framework import serializers
from django.utils.timesince import timesince
from .models import SystemSetting, Notification

class SystemSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSetting
        fields = '__all__'

class NotificationSerializer(serializers.ModelSerializer):
    # ✅ Added helper fields for the Frontend
    time_ago = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ['id', 'type', 'title', 'message', 'is_read', 'created_at', 'time_ago']
        read_only_fields = ['id', 'user', 'created_at', 'time_ago']

    def get_time_ago(self, obj):
        return f"{timesince(obj.created_at).split(',')[0]} ago"