from workers.celery_app import celery_app
from services.pipeline_service import execute_pipeline_run


@celery_app.task(name="pipeline.execute_run", bind=True, max_retries=0)
def execute_pipeline_run_task(self, run_id: str, requirements_text: str, additional_context: dict | None = None):
    execute_pipeline_run(run_id, requirements_text, additional_context or {})
