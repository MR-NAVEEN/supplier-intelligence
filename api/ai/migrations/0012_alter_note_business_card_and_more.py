# Generated manually to align migrations with model changes on 2026-08-20

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai", "0011_alter_aibusinesscard_image_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="note",
            name="catalogue",
        ),
        migrations.RemoveIndex(
            model_name="aiattachment",
            name="note_attach_type_idx",
        ),
        migrations.RemoveIndex(
            model_name="aiattachment",
            name="note_document_type_idx",
        ),
        migrations.RemoveIndex(
            model_name="aiattachment",
            name="note_image_type_idx",
        ),
        migrations.RemoveField(
            model_name="aiattachment",
            name="note",
        ),
        migrations.AlterField(
            model_name="note",
            name="business_card",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="notes",
                to="ai.aibusinesscard",
            ),
        ),
        migrations.AddField(
            model_name="aiattachment",
            name="business_card",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="attachments",
                to="ai.aibusinesscard",
                default=1,
            ),
            preserve_default=False,
        ),
        migrations.AddIndex(
            model_name="aiattachment",
            index=models.Index(
                fields=["business_card", "attachment_type"],
                name="note_attach_type_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="aiattachment",
            index=models.Index(
                fields=["business_card", "document_type"],
                name="note_document_type_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="aiattachment",
            index=models.Index(
                fields=["business_card", "image_type"],
                name="note_image_type_idx",
            ),
        ),
    ]
