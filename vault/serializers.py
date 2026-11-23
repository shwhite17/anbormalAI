from rest_framework import serializers

from .models import UserFile


class UserFileSerializer(serializers.ModelSerializer):
    sha256 = serializers.CharField(source="blob.sha256", read_only=True)

    class Meta:
        model = UserFile
        fields = ["id", "original_filename", "file_type", "size", "sha256", "uploaded_at"]
