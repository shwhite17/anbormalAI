from django.db import models


class Blob(models.Model):
    """One physical copy of file content, shared by every UserFile with the same hash."""

    sha256 = models.CharField(max_length=64, unique=True)
    file = models.FileField(upload_to="blobs/")
    size = models.PositiveBigIntegerField()
    ref_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sha256[:12]} (refs={self.ref_count})"


class UserFile(models.Model):
    """A user's logical file. Points at a shared Blob."""

    user_id = models.CharField(max_length=64, db_index=True)
    original_filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=127)
    size = models.PositiveBigIntegerField()
    blob = models.ForeignKey(Blob, on_delete=models.PROTECT, related_name="user_files")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at", "-id"]

    def __str__(self):
        return f"{self.user_id}:{self.original_filename}"
