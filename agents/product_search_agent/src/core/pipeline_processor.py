"""
Pipeline Processor: Async queue-based concurrent pipeline for product search.

This module implements Solution 2: Pipeline Processing with Async Queues.
It allows multiple search requests to be processed concurrently through
different pipeline stages, maximizing throughput and resource utilization.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, Callable, Awaitable
from dataclasses import dataclass
from enum import Enum
import uuid
from datetime import datetime

from shared.logging import setup_logger
from src.api.models import (
    ProductSearchRequest, ProductWithPrice, ExtractedUrlInfo, 
    IdentifiedPageCandidate, BraveSearchResult
)

logger = setup_logger("pipeline_processor")

class PipelineStage(Enum):
    """Pipeline stages for concurrent processing."""
    QUERY_GENERATION = "query_generation"
    URL_EXTRACTION = "url_extraction" 
    PAGE_IDENTIFICATION = "page_identification"
    PRICE_EXTRACTION = "price_extraction"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class PipelineJob:
    """Represents a job flowing through the pipeline."""
    job_id: str
    request: ProductSearchRequest
    stage: PipelineStage
    created_at: datetime
    stage_start_time: float
    
    # Stage outputs
    search_results: Optional[List[BraveSearchResult]] = None
    extracted_urls: Optional[List[ExtractedUrlInfo]] = None
    identified_pages: Optional[List[IdentifiedPageCandidate]] = None
    final_products: Optional[List[ProductWithPrice]] = None
    
    # Error handling
    error: Optional[str] = None
    retry_count: int = 0
    
    def update_stage(self, new_stage: PipelineStage) -> None:
        """Update job stage and timing."""
        self.stage = new_stage
        self.stage_start_time = time.time()

@dataclass
class PipelineMetrics:
    """Pipeline performance metrics."""
    jobs_processed: int = 0
    jobs_completed: int = 0
    jobs_failed: int = 0
    avg_processing_time: float = 0.0
    stage_times: Dict[PipelineStage, float] = None
    
    def __post_init__(self):
        if self.stage_times is None:
            self.stage_times = {stage: 0.0 for stage in PipelineStage}

class PipelineProcessor:
    """
    High-performance async pipeline processor for concurrent product searches.
    
    Features:
    - Concurrent processing of multiple search requests
    - Queue-based stage communication
    - Load balancing across pipeline stages
    - Real-time metrics and monitoring
    - Graceful error handling and retries
    """
    
    def __init__(self, 
                 max_concurrent_jobs: int = 5,
                 queue_size: int = 100,
                 max_retries: int = 2,
                 stage_timeout: int = 60,
                 max_completed_jobs: int = 50):
        """
        Initialize pipeline processor.
        
        Args:
            max_concurrent_jobs: Maximum concurrent jobs in pipeline
            queue_size: Maximum queue size for each stage
            max_retries: Maximum retry attempts for failed jobs
            stage_timeout: Timeout in seconds for each stage
            max_completed_jobs: Maximum completed jobs to keep in memory (triggers cleanup)
        """
        self.max_concurrent_jobs = max_concurrent_jobs
        self.queue_size = queue_size
        self.max_retries = max_retries
        self.stage_timeout = stage_timeout
        self.max_completed_jobs = max_completed_jobs
        
        # Pipeline queues
        self.queues: Dict[PipelineStage, asyncio.Queue] = {
            PipelineStage.QUERY_GENERATION: asyncio.Queue(maxsize=queue_size),
            PipelineStage.URL_EXTRACTION: asyncio.Queue(maxsize=queue_size),
            PipelineStage.PAGE_IDENTIFICATION: asyncio.Queue(maxsize=queue_size),
            PipelineStage.PRICE_EXTRACTION: asyncio.Queue(maxsize=queue_size),
        }
        
        # Results tracking
        self.active_jobs: Dict[str, PipelineJob] = {}
        self.completed_jobs: Dict[str, PipelineJob] = {}
        self.metrics = PipelineMetrics()
        
        # Pipeline control
        self.running = False
        self.stage_workers: Dict[PipelineStage, List[asyncio.Task]] = {}
        
        # Stage processors (will be injected)
        self.stage_processors: Dict[PipelineStage, Callable] = {}
        
        logger.info(f"PipelineProcessor initialized: max_jobs={max_concurrent_jobs}, "
                   f"queue_size={queue_size}, stage_timeout={stage_timeout}s")
    
    def register_stage_processor(self, stage: PipelineStage, processor: Callable) -> None:
        """Register a processor function for a pipeline stage."""
        self.stage_processors[stage] = processor
        logger.debug(f"Registered processor for stage: {stage.value}")
    
    async def start_pipeline(self) -> None:
        """Start the pipeline with worker tasks for each stage."""
        if self.running:
            logger.warning("Pipeline is already running")
            return
        
        self.running = True
        logger.info("🚀 Starting pipeline processor")
        
        # Start workers for each stage
        for stage in [PipelineStage.QUERY_GENERATION, PipelineStage.URL_EXTRACTION, 
                     PipelineStage.PAGE_IDENTIFICATION, PipelineStage.PRICE_EXTRACTION]:
            workers = []
            # Create multiple workers per stage for concurrency
            worker_count = 2 if stage == PipelineStage.PRICE_EXTRACTION else 1
            
            for i in range(worker_count):
                worker_name = f"{stage.value}_worker_{i}"
                worker_task = asyncio.create_task(
                    self._stage_worker(stage, worker_name),
                    name=worker_name
                )
                workers.append(worker_task)
            
            self.stage_workers[stage] = workers
            logger.debug(f"Started {worker_count} workers for {stage.value}")
    
    async def stop_pipeline(self) -> None:
        """Stop the pipeline and clean up workers."""
        if not self.running:
            return
        
        logger.info("Stopping pipeline processor")
        self.running = False
        
        # Cancel all workers
        for stage, workers in self.stage_workers.items():
            for worker in workers:
                worker.cancel()
                try:
                    await worker
                except asyncio.CancelledError:
                    pass
        
        self.stage_workers.clear()
        logger.info("Pipeline processor stopped")
    
    async def submit_search(self, request: ProductSearchRequest) -> str:
        """
        Submit a search request to the pipeline.
        
        Args:
            request: Product search request
            
        Returns:
            str: Job ID for tracking
        """
        job_id = str(uuid.uuid4())
        job = PipelineJob(
            job_id=job_id,
            request=request,
            stage=PipelineStage.QUERY_GENERATION,
            created_at=datetime.now(),
            stage_start_time=time.time()
        )
        
        self.active_jobs[job_id] = job
        
        # Add to first stage queue
        try:
            await asyncio.wait_for(
                self.queues[PipelineStage.QUERY_GENERATION].put(job),
                timeout=5.0
            )
            logger.info(f"Submitted search job {job_id} for query: '{request.query}'")
            self.metrics.jobs_processed += 1
            return job_id
            
        except asyncio.TimeoutError:
            del self.active_jobs[job_id]
            raise Exception("Pipeline queue is full - too many concurrent requests")
    
    async def get_result(self, job_id: str, timeout: int = 120) -> Optional[PipelineJob]:
        """
        Get the result of a submitted job.
        
        Args:
            job_id: Job ID to retrieve
            timeout: Maximum wait time in seconds
            
        Returns:
            PipelineJob with results or None if timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Check if job completed
            if job_id in self.completed_jobs:
                job = self.completed_jobs[job_id]
                logger.info(f"Job {job_id} completed with stage: {job.stage.value}")
                return job
            
            # Check if job failed
            if job_id in self.active_jobs:
                job = self.active_jobs[job_id]
                if job.stage in [PipelineStage.FAILED, PipelineStage.COMPLETED]:
                    self.completed_jobs[job_id] = self.active_jobs.pop(job_id)
                    return job
            
            await asyncio.sleep(0.1)
        
        logger.warning(f"Job {job_id} timed out after {timeout}s")
        return None
    
    async def _stage_worker(self, stage: PipelineStage, worker_name: str) -> None:
        """Worker task for processing jobs in a specific stage."""
        logger.debug(f"Started {worker_name} for {stage.value}")
        
        while self.running:
            try:
                # Get job from queue
                job = await asyncio.wait_for(
                    self.queues[stage].get(),
                    timeout=1.0
                )
                
                # Process job
                await self._process_job_stage(job, stage)
                
            except asyncio.TimeoutError:
                # Normal timeout - continue loop
                continue
            except Exception as e:
                logger.error(f"Error in {worker_name}: {e}")
                await asyncio.sleep(1.0)
    
    async def _process_job_stage(self, job: PipelineJob, stage: PipelineStage) -> None:
        """Process a job through a specific pipeline stage."""
        stage_start = time.time()
        
        try:
            logger.debug(f"Processing job {job.job_id} in stage {stage.value}")
            
            # Get stage processor
            processor = self.stage_processors.get(stage)
            if not processor:
                raise Exception(f"No processor registered for stage {stage.value}")
            
            # Process with timeout
            result = await asyncio.wait_for(
                processor(job),
                timeout=self.stage_timeout
            )
            
            # Update job with results and move to next stage
            await self._update_job_stage(job, stage, result)
            
            # Track timing
            stage_time = time.time() - stage_start
            self.metrics.stage_times[stage] = (
                self.metrics.stage_times[stage] + stage_time
            ) / 2  # Moving average
            
        except asyncio.TimeoutError:
            logger.error(f"Job {job.job_id} timed out in stage {stage.value}")
            await self._handle_job_error(job, f"Timeout in {stage.value}")
            
        except Exception as e:
            logger.error(f"Job {job.job_id} failed in stage {stage.value}: {e}")
            await self._handle_job_error(job, str(e))
    
    async def _update_job_stage(self, job: PipelineJob, current_stage: PipelineStage, result: Any) -> None:
        """Update job with stage results and move to next stage."""
        
        # Update job with stage results
        if current_stage == PipelineStage.QUERY_GENERATION:
            job.search_results = result
            next_stage = PipelineStage.URL_EXTRACTION
            
        elif current_stage == PipelineStage.URL_EXTRACTION:
            job.extracted_urls = result
            next_stage = PipelineStage.PAGE_IDENTIFICATION
            
        elif current_stage == PipelineStage.PAGE_IDENTIFICATION:
            job.identified_pages = result
            next_stage = PipelineStage.PRICE_EXTRACTION
            
        elif current_stage == PipelineStage.PRICE_EXTRACTION:
            job.final_products = result
            next_stage = PipelineStage.COMPLETED
            
        else:
            raise Exception(f"Unknown stage: {current_stage}")
        
        # Move job to next stage
        job.update_stage(next_stage)
        
        if next_stage == PipelineStage.COMPLETED:
            # Job completed successfully
            self.completed_jobs[job.job_id] = self.active_jobs.pop(job.job_id)
            self.metrics.jobs_completed += 1
            
            total_time = time.time() - job.created_at.timestamp()
            self.metrics.avg_processing_time = (
                self.metrics.avg_processing_time + total_time
            ) / 2  # Moving average
            
            logger.info(f"Job {job.job_id} completed successfully in {total_time:.2f}s")
            
            # Clean up old completed jobs to prevent memory leak
            await self._cleanup_completed_jobs()
        else:
            # Add to next stage queue
            await self.queues[next_stage].put(job)
    
    async def _handle_job_error(self, job: PipelineJob, error_message: str) -> None:
        """Handle job error with retry logic."""
        job.error = error_message
        job.retry_count += 1
        
        if job.retry_count <= self.max_retries:
            logger.info(f"Retrying job {job.job_id} (attempt {job.retry_count}/{self.max_retries})")
            # Reset to beginning of current stage
            await self.queues[job.stage].put(job)
        else:
            logger.error(f"Job {job.job_id} failed permanently after {self.max_retries} retries")
            job.update_stage(PipelineStage.FAILED)
            self.completed_jobs[job.job_id] = self.active_jobs.pop(job.job_id)
            self.metrics.jobs_failed += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current pipeline performance metrics."""
        queue_sizes = {
            stage.value: queue.qsize() 
            for stage, queue in self.queues.items()
        }
        
        return {
            "jobs_processed": self.metrics.jobs_processed,
            "jobs_completed": self.metrics.jobs_completed,
            "jobs_failed": self.metrics.jobs_failed,
            "jobs_active": len(self.active_jobs),
            "avg_processing_time": round(self.metrics.avg_processing_time, 2),
            "queue_sizes": queue_sizes,
            "stage_avg_times": {
                stage.value: round(time_val, 2) 
                for stage, time_val in self.metrics.stage_times.items()
            },
            "pipeline_running": self.running
        }
    
    async def _cleanup_completed_jobs(self) -> None:
        """
        Clean up old completed jobs to prevent memory leaks.
        
        Keeps only the most recent completed jobs up to max_completed_jobs limit.
        This prevents the pipeline from accumulating completed job data indefinitely.
        """
        if len(self.completed_jobs) > self.max_completed_jobs:
            # Sort by completion time (job creation time + processing time)
            jobs_by_time = sorted(
                self.completed_jobs.items(),
                key=lambda x: x[1].created_at,
                reverse=True  # Most recent first
            )
            
            # Keep only the most recent jobs
            jobs_to_keep = dict(jobs_by_time[:self.max_completed_jobs])
            jobs_to_remove = len(self.completed_jobs) - len(jobs_to_keep)
            
            # Update completed_jobs dict
            self.completed_jobs = jobs_to_keep
            
            logger.info(f"Cleaned up {jobs_to_remove} old completed jobs (kept {len(jobs_to_keep)} most recent)")
    
    async def __aenter__(self) -> 'PipelineProcessor':
        """Async context manager entry."""
        await self.start_pipeline()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop_pipeline()
