import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from vault.models import Blob, UserFile

TMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class FileVaultTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def upload(self, user, name="a.txt", content=b"hello", ctype="text/plain"):
        f = SimpleUploadedFile(name, content, content_type=ctype)
        return self.client.post("/api/files/", {"file": f}, format="multipart", headers={"UserId": user})

    def test_requires_user_header(self):
        res = self.client.get("/api/files/")
        self.assertEqual(res.status_code, 400)

    def test_upload_and_list(self):
        res = self.upload("u1")
        self.assertEqual(res.status_code, 201)
        self.assertFalse(res.data["deduplicated"])
        listing = self.client.get("/api/files/", headers={"UserId": "u1"})
        self.assertEqual(len(listing.data), 1)
        self.assertEqual(listing.data[0]["original_filename"], "a.txt")

    def test_missing_file_rejected(self):
        res = self.client.post("/api/files/", {}, format="multipart", headers={"UserId": "u1"})
        self.assertEqual(res.status_code, 400)

    def test_identical_content_is_stored_once(self):
        first = self.upload("u1", "one.txt", b"same bytes")
        second = self.upload("u2", "two.txt", b"same bytes")
        self.assertFalse(first.data["deduplicated"])
        self.assertTrue(second.data["deduplicated"])
        self.assertEqual(Blob.objects.count(), 1)
        self.assertEqual(Blob.objects.get().ref_count, 2)
        self.assertEqual(UserFile.objects.count(), 2)

    def test_same_user_duplicate_upload_also_deduplicated(self):
        self.upload("u1", "x.txt", b"data")
        res = self.upload("u1", "y.txt", b"data")
        self.assertTrue(res.data["deduplicated"])
        self.assertEqual(Blob.objects.count(), 1)

    def test_different_content_not_deduplicated(self):
        self.upload("u1", "a.txt", b"aaa")
        self.upload("u1", "b.txt", b"bbb")
        self.assertEqual(Blob.objects.count(), 2)

    def test_delete_keeps_blob_until_last_reference(self):
        a = self.upload("u1", "a.txt", b"shared").data["id"]
        b = self.upload("u2", "b.txt", b"shared").data["id"]

        self.assertEqual(self.client.delete(f"/api/files/{a}/", headers={"UserId": "u1"}).status_code, 204)
        self.assertEqual(Blob.objects.count(), 1)
        self.assertEqual(Blob.objects.get().ref_count, 1)

        self.assertEqual(self.client.delete(f"/api/files/{b}/", headers={"UserId": "u2"}).status_code, 204)
        self.assertEqual(Blob.objects.count(), 0)

    def test_users_cannot_access_each_others_files(self):
        fid = self.upload("u1").data["id"]
        for method in (self.client.get, self.client.delete):
            res = method(f"/api/files/{fid}/", headers={"UserId": "u2"})
            self.assertEqual(res.status_code, 404)
        res = self.client.get(f"/api/files/{fid}/download/", headers={"UserId": "u2"})
        self.assertEqual(res.status_code, 404)

    def test_download_returns_original_bytes_and_name(self):
        fid = self.upload("u1", "report.txt", b"payload").data["id"]
        res = self.client.get(f"/api/files/{fid}/download/", headers={"UserId": "u1"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(b"".join(res.streaming_content), b"payload")
        self.assertIn("report.txt", res["Content-Disposition"])
