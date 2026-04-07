"""Unit tests for Kyromesh SDK client with respx mocked HTTP."""

import pytest
import respx
import httpx
from uuid import uuid4
from kyromesh import Kyromesh
from kyromesh.exceptions import (
    KyromeshError,
    AuthError,
    QuotaExceededError,
    GuardBlockedError,
    ProviderError,
    TimeoutError,
)
from kyromesh.models import Job, Batch, Usage


class TestKyromeshInit:
    """Test Kyromesh client initialization."""
    
    def test_init_valid_api_key_live(self):
        """Test initialization with valid live API key."""
        kyro = Kyromesh(api_key="km_live_test123")
        assert kyro.api_key == "km_live_test123"
        assert kyro.base_url == "https://api.kyromesh.com"
        kyro.close()
    
    def test_init_valid_api_key_test(self):
        """Test initialization with valid test API key."""
        kyro = Kyromesh(api_key="km_test_test123")
        assert kyro.api_key == "km_test_test123"
        kyro.close()
    
    def test_init_custom_base_url(self):
        """Test initialization with custom base URL."""
        kyro = Kyromesh(
            api_key="km_live_test123",
            base_url="https://custom.example.com"
        )
        assert kyro.base_url == "https://custom.example.com"
        kyro.close()
    
    def test_init_invalid_api_key_empty(self):
        """Test initialization with empty API key."""
        with pytest.raises(ValueError, match="api_key must be a non-empty string"):
            Kyromesh(api_key="")
    
    def test_init_invalid_api_key_wrong_prefix(self):
        """Test initialization with wrong API key prefix."""
        with pytest.raises(ValueError, match="api_key must start with"):
            Kyromesh(api_key="invalid_key_123")
    
    def test_init_invalid_api_key_none(self):
        """Test initialization with None API key."""
        with pytest.raises(ValueError, match="api_key must be a non-empty string"):
            Kyromesh(api_key=None)
    
    def test_context_manager(self):
        """Test context manager usage."""
        with Kyromesh(api_key="km_live_test123") as kyro:
            assert kyro.api_key == "km_live_test123"


class TestRunJob:
    """Test run_job method."""
    
    @respx.mock
    def test_run_job_success(self, respx_mock):
        """Test successful job submission."""
        job_id = str(uuid4())
        respx_mock.post("https://api.kyromesh.com/api/v1/jobs").mock(
            return_value=httpx.Response(
                201,
                json={
                    "id": job_id,
                    "status": "pending",
                    "input": {"text": "test"},
                }
            )
        )
        
        kyro = Kyromesh(api_key="km_live_test123")
        job = kyro.run_job(task="summarize", input={"text": "test"})
        
        assert job.id == job_id
        assert job.status == "pending"
        assert job.input == {"text": "test"}
        kyro.close()
    
    @respx.mock
    def test_run_job_with_all_parameters(self, respx_mock):
        """Test job submission with all optional parameters."""
        job_id = str(uuid4())
        respx_mock.post("https://api.kyromesh.com/api/v1/jobs").mock(
            return_value=httpx.Response(
                201,
                json={
                    "id": job_id,
                    "status": "pending",
                    "input": {"text": "test"},
                }
            )
        )
        
        kyro = Kyromesh(api_key="km_live_test123")
        job = kyro.run_job(
            task="summarize",
            input={"text": "test"},
            provider="openai",
            model="gpt-4",
            timeout=600,
            webhook_url="https://example.com/webhook",
            guardrails=["pii", "injection"],
            routing_policy="quality",
        )
        
        assert job.id == job_id
        assert job.status == "pending"
        
        # Verify request payload
        request = respx_mock.calls.last.request
        assert request.method == "POST"
        assert "Bearer km_live_test123" in request.headers["Authorization"]
        kyro.close()
    
    @respx.mock
    def test_run_job_auth_error_401(self, respx_mock):
        """Test job submission with 401 authentication error."""
        respx_mock.post("https://api.kyromesh.com/api/v1/jobs").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )
        
        kyro = Kyromesh(api_key="km_live_invalid")
        with pytest.raises(AuthError):
            kyro.run_job(task="summarize", input={"text": "test"})
        kyro.close()
    
    @respx.mock
    def test_run_job_quota_exceeded_429(self, respx_mock):
        """Test job submission with 429 quota exceeded error."""
        respx_mock.post("https://api.kyromesh.com/api/v1/jobs").mock(
            return_value=httpx.Response(
                429,
                json={"error": "Quota exceeded"},
                headers={"Retry-After": "60"}
            )
        )
        
        kyro = Kyromesh(api_key="km_live_test123")
        with pytest.raises(QuotaExceededError) as exc_info:
            kyro.run_job(task="summarize", input={"text": "test"})
        
        assert exc_info.value.retry_after == 60
        kyro.close()
    
    @respx.mock
    def test_run_job_guard_blocked_pii(self, respx_mock):
        """Test job submission blocked by Guard (PII detected)."""
        respx_mock.post("https://api.kyromesh.com/api/v1/jobs").mock(
            return_value=httpx.Response(
                400,
                json={
                    "error": "PII detected in input",
                    "code": "guard_pii_blocked"
                }
            )
        )
        
        kyro = Kyromesh(api_key="km_live_test123")
        with pytest.raises(GuardBlockedError) as exc_info:
            kyro.run_job(task="summarize", input={"text": "test@example.com"})
        
        assert "PII" in exc_info.value.message
        kyro.close()
    
    @respx.mock
    def test_run_job_guard_blocked_injection(self, respx_mock):
        """Test job submission blocked by Guard (injection detected)."""
        respx_mock.post("https://api.kyromesh.com/api/v1/jobs").mock(
            return_value=httpx.Response(
                400,
                json={
                    "error": "Prompt injection detected",
                    "code": "guard_injection_blocked"
                }
            )
        )
        
        kyro = Kyromesh(api_key="km_live_test123")
        with pytest.raises(GuardBlockedError):
            kyro.run_job(task="summarize", input={"text": "ignore previous"})
        kyro.close()
    
    @respx.mock
    def test_run_job_provider_error_500(self, respx_mock):
        """Test job submission with 500 server error."""
        respx_mock.post("https://api.kyromesh.com/api/v1/jobs").mock(
            return_value=httpx.Response(500, json={"error": "Internal server error"})
        )
        
        kyro = Kyromesh(api_key="km_live_test123")
        with pytest.raises(ProviderError):
            kyro.run_job(task="summarize", input={"text": "test"})
        kyro.close()
    
    @respx.mock
    def test_run_job_invalid_response_json(self, respx_mock):
        """Test job submission with invalid JSON response."""
        respx_mock.post("https://api.kyromesh.com/api/v1/jobs").mock(
            return_value=httpx.Response(201, text="invalid json")
        )
        
        kyro = Kyromesh(api_key="km_live_test123")
        with pytest.raises(KyromeshError, match="Failed to parse response"):
            kyro.run_job(task="summarize", input={"text": "test"})
        kyro.close()
    
    def test_run_job_invalid_task(self):
        """Test job submission with invalid task parameter."""
        kyro = Kyromesh(api_key="km_live_test123")
        with pytest.raises(ValueError, match="task must be a non-empty string"):
            kyro.run_job(task="", input={"text": "test"})
        kyro.close()
    
    def test_run_job_invalid_input(self):
        """Test job submission with invalid input parameter."""
        kyro = Kyromesh(api_key="km_live_test123")
        with pytest.raises(ValueError, match="input must be a dictionary"):
            kyro.run_job(task="summarize", input="not a dict")
        kyro.close()
    
    def test_run_job_invalid_timeout(self):
        """Test job submission with invalid timeout."""
        kyro = Kyromesh(api_key="km_live_test123")
        with pytest.raises(ValueError, match="timeout must be a positive integer"):
            kyro.run_job(task="summarize", input={"text": "test"}, timeout=0)
        kyro.close()
    
    def test_run_job_invalid_routing_policy(self):
        """Test job submission with invalid routing policy."""
        kyro = Kyromesh(api_key="km_live_test123")
        with pytest.raises(ValueError, match="routing_policy must be"):
            kyro.run_job(
                task="summarize",
                input={"text": "test"},
                routing_policy="invalid"
            )
        kyro.close()


class TestGetJobStatus:
    """Test get_job_status method."""
    
    @respx.mock
    def test_get_job_status_pending(self, respx_mock):
        """Test retrieving pending job status."""
        job_id = str(uuid4())
        respx_mock.get(f"https://api.kyromesh.com/api/v1/jobs/{job_id}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": job_id,
                    "status": "pending",
                    "input": {"text": "test"},
                }
            )
        )
        
        kyro = Kyromesh(api_key="km_live_test123")
        job = kyro.get_job_status(job_id)
        
        assert job.id == job_id
        assert job.status == "pending"
        assert not job.is_completed()
        kyro.close()
    
    @respx.mock
    def test_get_job_status_completed(self, respx_mock):
        """Test retrieving completed job status."""
        job_id = str(uuid4())
        respx_mock.get(f"https://api.kyromesh.com/api/v1/jobs/{job_id}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": job_id,
                    "status": "completed",
                    "input": {"text": "test"},
                    "output": {"summary": "result"},
                    "cost": 0.05,
                    "input_tokens": 100,
                    "output_tokens": 50,
                }
            )
        )
        
        kyro = Kyromesh(api_key="km_live_test123")
        job = kyro.get_job_status(job_id)
        
        assert job.id == job_id
        assert job.status == "completed"
        assert job.is_completed()
        assert job.is_successful()
        assert job.output == {"summary": "result"}
        assert job.cost == 0.05
        assert job.input_tokens == 100
        assert job.output_tokens == 50
        kyro.close()
    
    @respx.mock
    def test_get_job_status_failed(self, respx_mock):
        """Test retrieving failed job status."""
        job_id = str(uuid4())
        respx_mock.get(f"https://api.kyromesh.com/api/v1/jobs/{job_id}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": job_id,
                    "status": "failed",
                    "input": {"text": "test"},
                    "error": "Provider timeout",
                }
            )
        )
        
        kyro = Kyromesh(api_key="km_live_test123")
        job = kyro.get_job_status(job_id)
        
        assert job.status == "failed"
        assert job.is_completed()
        assert not job.is_successful()
        assert job.error == "Provider timeout"
        kyro.close()
    
    @respx.mock
    def test_get_job_status_not_found_404(self, respx_mock):
        """Test retrieving non-existent job (404)."""
        job_id = str(uuid4())
        respx_mock.get(f"https://api.kyromesh.com/api/v1/jobs/{job_id}").mock(
            return_value=httpx.Response(404, json={"error": "Job not found"})
        )
        
        kyro = Kyromesh(api_key="km_live_test123")
        with pytest.raises(KyromeshError, match="Job not found"):
            kyro.get_job_status(job_id)
        kyro.close()
    
    @respx.mock
    def test_get_job_status_auth_error_401(self, respx_mock):
        """Test retrieving job with authentication error."""
        job_id = str(uuid4())
        respx_mock.get(f"https://api.kyromesh.com/api/v1/jobs/{job_id}").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )
        
        kyro = Kyromesh(api_key="km_live_invalid")
        with pytest.raises(AuthError):
            kyro.get_job_status(job_id)
        kyro.close()
    
    @respx.mock
    def test_get_job_status_server_error_500(self, respx_mock):
        """Test retrieving job with server error."""
        job_id = str(uuid4())
        respx_mock.get(f"https://api.kyromesh.com/api/v1/jobs/{job_id}").mock(
            return_value=httpx.Response(500, json={"error": "Internal server error"})
        )
        
        kyro = Kyromesh(api_key="km_live_test123")
        with pytest.raises(KyromeshError, match="Server error"):
            kyro.get_job_status(job_id)
        kyro.close()
    
    def test_get_job_status_invalid_job_id(self):
        """Test retrieving job with invalid job_id."""
        kyro = Kyromesh(api_key="km_live_test123")
        with pytest.raises(ValueError, match="job_id must be a non-empty string"):
            kyro.get_job_status("")
        kyro.close()


class TestWaitForJob:
    """Test wait_for_job method."""
    
    @respx.mock
    def test_wait_for_job_completes_immediately(self, respx_mock):
        """Test waiting for job that completes immediately."""
        job_id = str(uuid4())
        respx_mock.get(f"https://api.kyromesh.com/api/v1/jobs/{job_id}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": job_id,
                    "status": "completed",
                    "input": {"text": "test"},
                    "output": {"summary": "result"},
                }
            )
        )
        
        kyro = Kyromesh(api_key="km_live_test123")
        job = kyro.wait_for_job(job_id, timeout=10, poll_interval=1)
        
        assert job.status == "completed"
        assert job.output == {"summary": "result"}
        kyro.close()
    
    @respx.mock
    def test_wait_for_job_timeout(self, respx_mock):
        """Test waiting for job that times out."""
        job_id = str(uuid4())
        respx_mock.get(f"https://api.kyromesh.com/api/v1/jobs/{job_id}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": job_id,
                    "status": "running",
                    "input": {"text": "test"},
                }
            )
        )
        
        kyro = Kyromesh(api_key="km_live_test123")
        with pytest.raises(TimeoutError) as exc_info:
            kyro.wait_for_job(job_id, timeout=1, poll_interval=0.5)
        
        assert exc_info.value.timeout_seconds == 1
        kyro.close()
    
    def test_wait_for_job_invalid_job_id(self):
        """Test waiting for job with invalid job_id."""
        kyro = Kyromesh(api_key="km_live_test123")
        with pytest.raises(ValueError, match="job_id must be a non-empty string"):
            kyro.wait_for_job("", timeout=10)
        kyro.close()
    
    def test_wait_for_job_invalid_timeout(self):
        """Test waiting for job with invalid timeout."""
        kyro = Kyromesh(api_key="km_live_test123")
        with pytest.raises(ValueError, match="timeout must be a positive integer"):
            kyro.wait_for_job(str(uuid4()), timeout=0)
        kyro.close()
    
    def test_wait_for_job_invalid_poll_interval(self):
        """Test waiting for job with invalid poll_interval."""
        kyro = Kyromesh(api_key="km_live_test123")
        with pytest.raises(ValueError, match="poll_interval must be a positive integer"):
            kyro.wait_for_job(str(uuid4()), timeout=10, poll_interval=0)
        kyro.close()


class TestSubmitBatch:
    """Test submit_batch method."""
    
    @respx.mock
    def test_submit_batch_success(self, respx_mock):
        """Test successful batch submission."""
        batch_id = str(uuid4())
        job_ids = [str(uuid4()) for _ in range(3)]
        
        respx_mock.post("https://api.kyromesh.com/api/v1/batches").mock(
            return_value=httpx.Response(
                201,
                json={
                    "id": batch_id,
                    "status": "processing",
                    "total_jobs": 3,
                    "done_jobs": 0,
                    "failed_jobs": 0,
                    "job_ids": job_ids,
                }
            )
        )
        
        kyro = Kyromesh(api_key="km_live_test123")
        batch = kyro.submit_batch(jobs=[
            {"task": "summarize", "input": {"text": "doc1"}},
            {"task": "classify", "input": {"text": "doc2"}},
            {"task": "generate", "input": {"text": "doc3"}},
        ])
        
        assert batch.id == batch_id
        assert batch.status == "processing"
        assert batch.total_jobs == 3
        assert batch.job_ids == job_ids
        kyro.close()
    
    @respx.mock
    def test_submit_batch_with_optional_params(self, respx_mock):
        """Test batch submission with optional job parameters."""
        batch_id = str(uuid4())
        respx_mock.post("https://api.kyromesh.com/api/v1/batches").mock(
            return_value=httpx.Response(
                201,
                json={
                    "id": batch_id,
                    "status": "processing",
                    "total_jobs": 1,
                    "done_jobs": 0,
                    "failed_jobs": 0,
                    "job_ids": [str(uuid4())],
                }
            )
        )
        
        kyro = Kyromesh(api_key="km_live_test123")
        batch = kyro.submit_batch(jobs=[
            {
                "task": "summarize",
                "input": {"text": "doc"},
                "provider": "openai",
                "model": "gpt-4",
                "timeout": 600,
                "webhook_url": "https://example.com/webhook",
                "guardrails": ["pii"],
                "routing_policy": "quality",
            }
        ])
        
        assert batch.id == batch_id
        kyro.close()
    
    @respx.mock
    def test_submit_batch_auth_error_401(self, respx_mock):
        """Test batch submission with authentication error."""
        respx_mock.post("https://api.kyromesh.com/api/v1/batches").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )
        
        kyro = Kyromesh(api_key="km_live_invalid")
        with pytest.raises(AuthError):
            kyro.submit_batch(jobs=[
                {"task": "summarize", "input": {"text": "doc"}},
            ])
        kyro.close()
    
    @respx.mock
    def test_submit_batch_quota_exceeded_429(self, respx_mock):
        """Test batch submission with quota exceeded."""
        respx_mock.post("https://api.kyromesh.com/api/v1/batches").mock(
            return_value=httpx.Response(
                429,
                json={"error": "Quota exceeded"},
                headers={"Retry-After": "120"}
            )
        )
        
        kyro = Kyromesh(api_key="km_live_test123")
        with pytest.raises(QuotaExceededError):
            kyro.submit_batch(jobs=[
                {"task": "summarize", "input": {"text": "doc"}},
            ])
        kyro.close()
    
    @respx.mock
    def test_submit_batch_invalid_request_400(self, respx_mock):
        """Test batch submission with invalid request."""
        respx_mock.post("https://api.kyromesh.com/api/v1/batches").mock(
            return_value=httpx.Response(
                400,
                json={"error": "Invalid batch", "code": "bad_request"}
            )
        )
        
        kyro = Kyromesh(api_key="km_live_test123")
        with pytest.raises(KyromeshError, match="Invalid batch"):
            kyro.submit_batch(jobs=[
                {"task": "summarize", "input": {"text": "doc"}},
            ])
        kyro.close()
    
    @respx.mock
    def test_submit_batch_server_error_500(self, respx_mock):
        """Test batch submission with server error."""
        respx_mock.post("https://api.kyromesh.com/api/v1/batches").mock(
            return_value=httpx.Response(500, json={"error": "Internal server error"})
        )
        
        kyro = Kyromesh(api_key="km_live_test123")
        with pytest.raises(KyromeshError, match="Server error"):
            kyro.submit_batch(jobs=[
                {"task": "summarize", "input": {"text": "doc"}},
            ])
        kyro.close()
    
    def test_submit_batch_empty_jobs(self):
        """Test batch submission with empty jobs list."""
        kyro = Kyromesh(api_key="km_live_test123")
        with pytest.raises(ValueError, match="jobs list cannot be empty"):
            kyro.submit_batch(jobs=[])
        kyro.close()
    
    def test_submit_batch_too_many_jobs(self):
        """Test batch submission with more than 1000 jobs."""
        kyro = Kyromesh(api_key="km_live_test123")
        jobs = [
            {"task": "summarize", "input": {"text": f"doc{i}"}}
            for i in range(1001)
        ]
        with pytest.raises(ValueError, match="jobs list cannot exceed 1,000 items"):
            kyro.submit_batch(jobs=jobs)
        kyro.close()
    
    def test_submit_batch_invalid_jobs_type(self):
        """Test batch submission with invalid jobs type."""
        kyro = Kyromesh(api_key="km_live_test123")
        with pytest.raises(ValueError, match="jobs must be a list"):
            kyro.submit_batch(jobs="not a list")
        kyro.close()
    
    def test_submit_batch_job_missing_task(self):
        """Test batch submission with job missing task field."""
        kyro = Kyromesh(api_key="km_live_test123")
        with pytest.raises(ValueError, match="must have a 'task' field"):
            kyro.submit_batch(jobs=[
                {"input": {"text": "doc"}},
            ])
        kyro.close()
    
    def test_submit_batch_job_missing_input(self):
        """Test batch submission with job missing input field."""
        kyro = Kyromesh(api_key="km_live_test123")
        with pytest.raises(ValueError, match="must have an 'input' field"):
            kyro.submit_batch(jobs=[
                {"task": "summarize"},
            ])
        kyro.close()


class TestGetBatchStatus:
    """Test get_batch_status method."""
    
    @respx.mock
    def test_get_batch_status_processing(self, respx_mock):
        """Test retrieving batch status while processing."""
        batch_id = str(uuid4())
        respx_mock.get(f"https://api.kyromesh.com/api/v1/batches/{batch_id}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": batch_id,
                    "status": "processing",
                    "total_jobs": 10,
                    "done_jobs": 3,
                    "failed_jobs": 0,
                    "job_ids": [str(uuid4()) for _ in range(10)],
                }
            )
        )
        
        kyro = Kyromesh(api_key="km_live_test123")
        batch = kyro.get_batch_status(batch_id)
        
        assert batch.id == batch_id
        assert batch.status == "processing"
        assert batch.total_jobs == 10
        assert batch.done_jobs == 3
        assert batch.failed_jobs == 0
        assert not batch.is_completed()
        kyro.close()
    
    @respx.mock
    def test_get_batch_status_completed(self, respx_mock):
        """Test retrieving completed batch status."""
        batch_id = str(uuid4())
        respx_mock.get(f"https://api.kyromesh.com/api/v1/batches/{batch_id}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": batch_id,
                    "status": "completed",
                    "total_jobs": 10,
                    "done_jobs": 9,
                    "failed_jobs": 1,
                    "job_ids": [str(uuid4()) for _ in range(10)],
                }
            )
        )
        
        kyro = Kyromesh(api_key="km_live_test123")
        batch = kyro.get_batch_status(batch_id)
        
        assert batch.status == "completed"
        assert batch.is_completed()
        assert batch.progress_percentage() == 100.0
        kyro.close()
    
    @respx.mock
    def test_get_batch_status_not_found_404(self, respx_mock):
        """Test retrieving non-existent batch (404)."""
        batch_id = str(uuid4())
        respx_mock.get(f"https://api.kyromesh.com/api/v1/batches/{batch_id}").mock(
            return_value=httpx.Response(404, json={"error": "Batch not found"})
        )
        
        kyro = Kyromesh(api_key="km_live_test123")
        with pytest.raises(KyromeshError, match="Batch not found"):
            kyro.get_batch_status(batch_id)
        kyro.close()
    
    @respx.mock
    def test_get_batch_status_auth_error_401(self, respx_mock):
        """Test retrieving batch with authentication error."""
        batch_id = str(uuid4())
        respx_mock.get(f"https://api.kyromesh.com/api/v1/batches/{batch_id}").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )
        
        kyro = Kyromesh(api_key="km_live_invalid")
        with pytest.raises(AuthError):
            kyro.get_batch_status(batch_id)
        kyro.close()
    
    def test_get_batch_status_invalid_batch_id(self):
        """Test retrieving batch with invalid batch_id."""
        kyro = Kyromesh(api_key="km_live_test123")
        with pytest.raises(ValueError, match="batch_id must be a non-empty string"):
            kyro.get_batch_status("")
        kyro.close()


class TestGetUsage:
    """Test get_usage method."""
    
    @respx.mock
    def test_get_usage_success(self, respx_mock):
        """Test successful usage retrieval."""
        respx_mock.get("https://api.kyromesh.com/api/v1/usage").mock(
            return_value=httpx.Response(
                200,
                json={
                    "jobs_used": 500,
                    "jobs_limit": 1000,
                    "jobs_remaining": 500,
                    "overage_jobs": 0,
                    "total_cost": 25.50,
                    "tier": "starter",
                    "overage_rate": 0.20,
                }
            )
        )
        
        kyro = Kyromesh(api_key="km_live_test123")
        usage = kyro.get_usage()
        
        assert usage.jobs_used == 500
        assert usage.jobs_limit == 1000
        assert usage.jobs_remaining == 500
        assert usage.overage_jobs == 0
        assert usage.total_cost == 25.50
        assert usage.tier == "starter"
        assert usage.overage_rate == 0.20
        assert usage.usage_percentage() == 50.0
        kyro.close()
    
    @respx.mock
    def test_get_usage_exceeded_quota(self, respx_mock):
        """Test usage retrieval with exceeded quota."""
        respx_mock.get("https://api.kyromesh.com/api/v1/usage").mock(
            return_value=httpx.Response(
                200,
                json={
                    "jobs_used": 1200,
                    "jobs_limit": 1000,
                    "jobs_remaining": 0,
                    "overage_jobs": 200,
                    "total_cost": 75.00,
                    "tier": "starter",
                    "overage_rate": 0.20,
                }
            )
        )
        
        kyro = Kyromesh(api_key="km_live_test123")
        usage = kyro.get_usage()
        
        assert usage.jobs_used == 1200
        assert usage.jobs_remaining == 0
        assert usage.overage_jobs == 200
        assert usage.usage_percentage() == 120.0
        kyro.close()
    
    @respx.mock
    def test_get_usage_auth_error_401(self, respx_mock):
        """Test usage retrieval with authentication error."""
        respx_mock.get("https://api.kyromesh.com/api/v1/usage").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )
        
        kyro = Kyromesh(api_key="km_live_invalid")
        with pytest.raises(AuthError):
            kyro.get_usage()
        kyro.close()
    
    @respx.mock
    def test_get_usage_server_error_500(self, respx_mock):
        """Test usage retrieval with server error."""
        respx_mock.get("https://api.kyromesh.com/api/v1/usage").mock(
            return_value=httpx.Response(500, json={"error": "Internal server error"})
        )
        
        kyro = Kyromesh(api_key="km_live_test123")
        with pytest.raises(KyromeshError, match="Server error"):
            kyro.get_usage()
        kyro.close()


class TestExceptionHierarchy:
    """Test exception hierarchy and properties."""
    
    def test_auth_error_properties(self):
        """Test AuthError properties."""
        error = AuthError("Invalid key")
        assert error.message == "Invalid key"
        assert error.code == "auth_error"
        assert isinstance(error, KyromeshError)
    
    def test_quota_exceeded_error_properties(self):
        """Test QuotaExceededError properties."""
        error = QuotaExceededError(
            message="Quota exceeded",
            jobs_remaining=100,
            retry_after=60
        )
        assert error.message == "Quota exceeded"
        assert error.code == "quota_exceeded"
        assert error.jobs_remaining == 100
        assert error.retry_after == 60
    
    def test_guard_blocked_error_properties(self):
        """Test GuardBlockedError properties."""
        error = GuardBlockedError(
            message="PII detected",
            block_reason="pii_email"
        )
        assert error.message == "PII detected"
        assert error.code == "guard_blocked"
        assert error.block_reason == "pii_email"
    
    def test_provider_error_properties(self):
        """Test ProviderError properties."""
        error = ProviderError(
            message="Provider timeout",
            provider="openai",
            status_code=503
        )
        assert error.message == "Provider timeout"
        assert error.code == "provider_error"
        assert error.provider == "openai"
        assert error.status_code == 503
    
    def test_timeout_error_properties(self):
        """Test TimeoutError properties."""
        error = TimeoutError(
            message="Job timeout",
            timeout_seconds=300
        )
        assert error.message == "Job timeout"
        assert error.code == "timeout_error"
        assert error.timeout_seconds == 300


class TestModelProperties:
    """Test model properties and methods."""
    
    def test_job_is_completed(self):
        """Test Job.is_completed() method."""
        pending_job = Job(id="1", status="pending", input={})
        running_job = Job(id="2", status="running", input={})
        completed_job = Job(id="3", status="completed", input={})
        failed_job = Job(id="4", status="failed", input={})
        
        assert not pending_job.is_completed()
        assert not running_job.is_completed()
        assert completed_job.is_completed()
        assert failed_job.is_completed()
    
    def test_job_is_successful(self):
        """Test Job.is_successful() method."""
        completed_job = Job(id="1", status="completed", input={})
        failed_job = Job(id="2", status="failed", input={})
        
        assert completed_job.is_successful()
        assert not failed_job.is_successful()
    
    def test_batch_is_completed(self):
        """Test Batch.is_completed() method."""
        processing_batch = Batch(
            id="1", status="processing", total_jobs=10,
            done_jobs=5, failed_jobs=0
        )
        completed_batch = Batch(
            id="2", status="completed", total_jobs=10,
            done_jobs=9, failed_jobs=1
        )
        
        assert not processing_batch.is_completed()
        assert completed_batch.is_completed()
    
    def test_batch_progress_percentage(self):
        """Test Batch.progress_percentage() method."""
        batch = Batch(
            id="1", status="processing", total_jobs=10,
            done_jobs=3, failed_jobs=1
        )
        assert batch.progress_percentage() == 40.0
    
    def test_usage_usage_percentage(self):
        """Test Usage.usage_percentage() method."""
        usage = Usage(
            jobs_used=500,
            jobs_limit=1000,
            jobs_remaining=500,
            overage_jobs=0,
            total_cost=25.0,
            tier="starter",
            overage_rate=0.20
        )
        assert usage.usage_percentage() == 50.0
