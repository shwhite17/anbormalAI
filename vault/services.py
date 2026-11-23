"""Storage logic: content-addressed deduplication with reference counting."""
import hashlib

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import F

from .models import Blob, UserFile


def hash_upload(uploaded_file) -> str:
    """SHA-256 of an uploaded file, streamed in chunks so big files don't fill memory."""
    digest = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
    uploaded_file.seek(0)
    return digest.hexdigest()


def store_file(user_id: str, uploaded_file) -> tuple[UserFile, bool]:
    """Save an upload for a user. Returns (user_file, was_duplicate).

    If identical content already exists (for any user) we reuse the stored
    blob and only bump its reference count.
    """
    sha = hash_upload(uploaded_file)

    with transaction.atomic():
        blob, created = Blob.objects.get_or_create(
            sha256=sha, defaults={"size": uploaded_file.size, "ref_count": 0}
        )
        if created:
            blob.file.save(f"{sha[:2]}/{sha}", uploaded_file, save=False)
            blob.save(update_fields=["file"])
        Blob.objects.filter(pk=blob.pk).update(ref_count=F("ref_count") + 1)

        user_file = UserFile.objects.create(
            user_id=user_id,
            original_filename=uploaded_file.name[:255],
            file_type=uploaded_file.content_type or "application/octet-stream",
            size=uploaded_file.size,
            blob=blob,
        )
    return user_file, not created


def delete_user_file(user_file: UserFile) -> None:
    """Delete a logical file; remove the physical blob only when nothing references it."""
    with transaction.atomic():
        blob = Blob.objects.select_for_update().get(pk=user_file.blob_id)
        user_file.delete()
        blob.ref_count = F("ref_count") - 1
        blob.save(update_fields=["ref_count"])
        blob.refresh_from_db()
        if blob.ref_count == 0:
            blob.file.delete(save=False)
            blob.delete()
