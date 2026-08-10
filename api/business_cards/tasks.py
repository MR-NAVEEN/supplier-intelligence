from celery import shared_task

from api.jobs.models import Job


@shared_task
def process_business_card_ocr(job_id, business_card_id):
    from api.business_cards.models import BusinessCard

    job = Job.objects.get(pk=job_id)
    card = BusinessCard.objects.get(pk=business_card_id)
    job.status = Job.STATUS_RUNNING
    job.progress = 50
    job.save(update_fields=['status', 'progress', 'updated_at'])

    card.extracted_data = {
        'name': 'Stub Contact',
        'company_name': 'Stub Company Pvt Ltd',
        'email': 'contact@stub.example',
        'phone': '+91-9000000000',
        'title': 'Sales Manager',
    }
    card.status = BusinessCard.STATUS_EXTRACTED
    card.save(update_fields=['extracted_data', 'status', 'updated_at'])

    job.status = Job.STATUS_COMPLETED
    job.progress = 100
    job.result = card.extracted_data
    job.save(update_fields=['status', 'progress', 'result', 'updated_at'])
