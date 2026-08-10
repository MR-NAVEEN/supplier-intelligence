from celery import shared_task
from django.db import transaction

from api.jobs.models import Job
from api.products.models import Product


@shared_task
def process_catalogue_ocr(job_id):
    job = Job.objects.get(pk=job_id)
    job.status = Job.STATUS_RUNNING
    job.progress = 10
    job.save(update_fields=['status', 'progress', 'updated_at'])

    from api.catalogues.models import Catalogue, CatalogueFile, OcrPage

    catalogue = Catalogue.objects.get(pk=job.entity_id)
    catalogue.status = Catalogue.STATUS_PROCESSING
    catalogue.save(update_fields=['status', 'updated_at'])

    version = catalogue.versions.order_by('-version_number').first()
    if version:
        for idx, cf in enumerate(version.files.all(), start=1):
            OcrPage.objects.get_or_create(
                catalogue_file=cf,
                page_number=1,
                defaults={
                    'text': f'Stub OCR text for {cf.filename}',
                    'blocks': [{'text': cf.filename, 'bbox': [0, 0, 100, 20]}],
                },
            )

    job.progress = 60
    job.save(update_fields=['progress', 'updated_at'])
    process_catalogue_extraction.delay(job_id)


@shared_task
def process_catalogue_extraction(job_id):
    from api.catalogues.models import Catalogue, ExtractionCandidate

    job = Job.objects.get(pk=job_id)
    catalogue = Catalogue.objects.get(pk=job.entity_id)

    ExtractionCandidate.objects.get_or_create(
        catalogue=catalogue,
        page_number=1,
        defaults={
            'raw_data': {'name': f'Extracted item from {catalogue.title}'},
            'normalized_data': {
                'name': f'Extracted item from {catalogue.title}',
                'sku': 'STUB-001',
                'price': '99.00',
            },
            'confidence': 0.88,
        },
    )

    catalogue.status = Catalogue.STATUS_REVIEW
    catalogue.save(update_fields=['status', 'updated_at'])
    job.status = Job.STATUS_COMPLETED
    job.progress = 100
    job.result = {'extractions_created': 1}
    job.save(update_fields=['status', 'progress', 'result', 'updated_at'])
