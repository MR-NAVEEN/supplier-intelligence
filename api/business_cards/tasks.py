from celery import shared_task

from api.jobs.models import Job
from api.ai.services.card_extract import extract_business_card
from api.ai.services.extraction import MODEL_TIERS, extract_catalogue, pdf_page_count
from api.ai.models import AIExtractionRun
from datetime import datetime




@shared_task
def process_business_card_ocr(job_id, business_card_id):
    from api.business_cards.models import BusinessCard
    job = Job.objects.get(pk=job_id)
    card = BusinessCard.objects.get(pk=business_card_id)
    model_name = MODEL_TIERS.get(AIExtractionRun.TIER_HIGH, MODEL_TIERS['high_accuracy'])
    extracted = extract_business_card(card.image.path, model_name)
    finished = datetime.now()
    result = extracted['result']
    usage = extracted['usage']

    
    job.status = Job.STATUS_RUNNING
    job.progress = 50
    job.save(update_fields=['status', 'progress', 'updated_at'])

    card.extracted_data = {
        'name': result.get('full_name') or '',
        'company_name': result.get('company') or '',
        'email': result.get('emails') or [],
        'phone': result.get('phones') or [],
        'title': result.get('job_title') or '',
    }
    card.status = BusinessCard.STATUS_EXTRACTED
    card.save(update_fields=['extracted_data', 'status', 'updated_at'])

    job.status = Job.STATUS_COMPLETED
    job.progress = 100
    job.result = card.extracted_data
    job.save(update_fields=['status', 'progress', 'result', 'updated_at'])
