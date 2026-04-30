import hashlib
import os
from django.db import migrations
from django.core.files.storage import default_storage


def _sha256_of_file(file_field) -> str:
    if not file_field:
        return ""
    name = file_field.name
    if not name or not default_storage.exists(name):
        return ""
    h = hashlib.sha256()
    with default_storage.open(name, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _manifest_of(hashes):
    sorted_hashes = sorted(h for h in hashes if h)
    if not sorted_hashes:
        return None
    return hashlib.sha256("".join(sorted_hashes).encode("ascii")).hexdigest()


def backfill(apps, schema_editor):
    EvidenceRevision = apps.get_model("core", "EvidenceRevision")
    EvidenceFile = apps.get_model("core", "EvidenceFile")

    for rev in EvidenceRevision.objects.iterator():
        # Migrate single attachment → first EvidenceFile
        if rev.attachment and rev.attachment.name:
            already = EvidenceFile.objects.filter(revision=rev).exists()
            if not already:
                size = 0
                try:
                    if default_storage.exists(rev.attachment.name):
                        size = default_storage.size(rev.attachment.name)
                except Exception:
                    size = 0
                EvidenceFile.objects.create(
                    revision=rev,
                    folder=rev.folder,
                    file=rev.attachment.name,
                    original_name=os.path.basename(rev.attachment.name),
                    sha256=rev.attachment_hash or _sha256_of_file(rev.attachment),
                    size=size,
                    ordering=0,
                )

        # Recompute manifest hash from any (possibly newly-created) files
        hashes = list(
            EvidenceFile.objects.filter(revision=rev).values_list("sha256", flat=True)
        )
        manifest = _manifest_of(hashes)
        if rev.manifest_hash != manifest:
            rev.manifest_hash = manifest
            rev.save(update_fields=["manifest_hash"])

        # Carry the parent evidence's status onto every revision (we have no
        # historical per-revision status to draw from). Reviewer fields stay null.
        new_status = rev.evidence.status if rev.evidence_id else "draft"
        if rev.status != new_status:
            rev.status = new_status
            rev.save(update_fields=["status"])


def reverse_backfill(apps, schema_editor):
    EvidenceFile = apps.get_model("core", "EvidenceFile")
    EvidenceFile.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0168_add_evidence_files_and_revision_lifecycle"),
    ]

    operations = [
        migrations.RunPython(backfill, reverse_backfill),
    ]
