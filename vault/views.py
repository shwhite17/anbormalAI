from django.conf import settings
from django.http import FileResponse
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import UserFile
from .serializers import UserFileSerializer


def get_user_id(request) -> str:
    """Identify the caller from the `UserId` header (stand-in for real auth)."""
    user_id = request.headers.get("UserId", "").strip()
    if not user_id:
        raise ValidationError({"detail": "UserId header is required."})
    return user_id


class FileListCreateView(APIView):
    parser_classes = [MultiPartParser]

    def get(self, request):
        user_id = get_user_id(request)
        qs = UserFile.objects.filter(user_id=user_id).select_related("blob")
        return Response(UserFileSerializer(qs, many=True).data)

    def post(self, request):
        user_id = get_user_id(request)
        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": "No file was submitted."})
        if upload.size > settings.VAULT_MAX_UPLOAD_BYTES:
            return Response(
                {"detail": "File too large."}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            )

        user_file, duplicate = services.store_file(user_id, upload)
        data = UserFileSerializer(user_file).data
        data["deduplicated"] = duplicate
        return Response(data, status=status.HTTP_201_CREATED)


class FileDetailView(APIView):
    def _get(self, request, pk) -> UserFile:
        user_id = get_user_id(request)
        try:
            return UserFile.objects.select_related("blob").get(pk=pk, user_id=user_id)
        except UserFile.DoesNotExist:
            from rest_framework.exceptions import NotFound

            raise NotFound("File not found.")

    def get(self, request, pk):
        return Response(UserFileSerializer(self._get(request, pk)).data)

    def delete(self, request, pk):
        services.delete_user_file(self._get(request, pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


class FileDownloadView(FileDetailView):
    def get(self, request, pk):
        user_file = self._get(request, pk)
        return FileResponse(
            user_file.blob.file.open("rb"),
            as_attachment=True,
            filename=user_file.original_filename,
            content_type=user_file.file_type,
        )
