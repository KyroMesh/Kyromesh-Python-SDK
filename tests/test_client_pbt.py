"""Property-based tests for Kyromesh SDK client using Hypothesis.

This module tests the SDK against the REST API schema using property-based testing.
It verifies that SDK requests match the REST API schema exactly for all valid inputs.

Satisfies: Req 9 CP 9.1 (SDK Consistency)
"""

import json
from typing import Any, Dict, List, Optional
from uuid import uuid4

import pytest
import respx
import httpx
from hypothesis import given, strategies as st, assume, settings, HealthCheck

from kyromesh import Kyromesh
from kyromesh.exceptions import (
    KyromeshError,
    AuthError,
    QuotaExceededError,
    GuardBlockedError,
)
from kyromesh.models import Job, Batch, Usage


# ============================================================================
# Hypothesis Strategies for Valid Job Inputs
# ============================================================================

def task_strategy() -> st.SearchStrategy[str]:
    """Generate valid task names."""
    return st.sampled_from([
        "summarize",
        "classify",
        "generate",
        "translate",
        "extract",
        "analyze",
        "transform",
    ])


def input_strategy() -> st.SearchStrategy[Dict[str, Any]]:
    """Generate valid job input dictionaries."""
    # Simple text-based inputs
    text_input = st.fixed_dictionaries({
        "text": st.text(min_size=1, max_size=1000)
    })
    
    # Nested JSON inputs
    nested_input = st.fixed_dictionaries({
        "data": st.fixed_dictionaries({
            "content": st.text(min_size=1, max_size=500)
        }),
        "metadata": st.just({"source": "test"}),
    })
    
    # Array inputs
    array_input = st.fixed_dictionaries({
        "items": st.just([
            {"id": 1, "value": "item1"},
            {"id": 2, "value": "item2"},
        ]),
    })
    
    return st.one_of(text_input, nested_input, array_input)


def provider_strategy() -> st.SearchStrategy[Optional[str]]:
    """Generate valid provider names or None."""
    return st.one_of(
        st.none(),
        st.sampled_from(["openai", "bedrock", "grok"]),
    )


def model_strategy() -> st.SearchStrategy[Optional[str]]:
    """Generate valid model names or None."""
    return st.one_of(
        st.none(),
        st.sampled_from([
            "gpt-4",
            "gpt-3.5-turbo",
            "claude-3",
            "llama-2",
        ]),
    )


def timeout_strategy() -> st.SearchStrategy[int]:
    """Generate valid timeout values."""
    return st.integers(min_value=1, max_value=3600)


def webhook_url_strategy() -> st.SearchStrategy[Optional[str]]:
    """Generate valid webhook URLs or None."""
    return st.one_of(
        st.none(),
        st.just("https://example.com/webhook"),
        st.just("https://api.example.com/callbacks/kyromesh"),
    )


def guardrails_strategy() -> st.SearchStrategy[Optional[List[str]]]:
    """Generate valid guardrails lists or None."""
    guardrail_options = st.lists(
        st.sampled_from(["pii", "injection", "toxicity"]),
        min_size=0,
        max_size=3,
        unique=True,
    )
    return st.one_of(st.none(), guardrail_options)


def routing_policy_strategy() -> st.SearchStrategy[str]:
    """Generate valid routing policies."""
    return st.sampled_from(["cost", "latency", "quality"])


def job_input_strategy() -> st.SearchStrategy[Dict[str, Any]]:
    """Generate complete valid job input parameters."""
    return st.fixed_dictionaries({
        "task": task_strategy(),
        "input": input_strategy(),
        "provider": provider_strategy(),
        "model": model_strategy(),
        "timeout": timeout_strategy(),
        "webhook_url": webhook_url_strategy(),
        "guardrails": guardrails_strategy(),
        "routing_policy": routing_policy_strategy(),
    })


def batch_job_strategy() -> st.SearchStrategy[Dict[str, Any]]:
    """Generate valid batch job dictionaries."""
    return st.fixed_dictionaries({
        "task": task_strategy(),
        "input": input_strategy(),
        "provider": provider_strategy(),
        "model": model_strategy(),
        "timeout": timeout_strategy(),
        "webhook_url": webhook_url_strategy(),
        "guardrails": guardrails_strategy(),
        "routing_policy": routing_policy_strategy(),
    })


# ============================================================================
# Property-Based Tests for run_job
# ============================================================================

class TestRunJobPBT:
    """Property-based tests for run_job method."""
    
    @given(job_input_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_run_job_request_schema_matches_api(self, job_params):
        """
        Property: For all valid job inputs, the SDK request payload matches
        the REST API schema exactly.
        
        Satisfies: Req 9 CP 9.1 (SDK Consistency)
        """
        job_id = str(uuid4())
        
        with respx.mock:
            # Mock the API response
            respx.post("https://api.kyromesh.com/api/v1/jobs").mock(
                return_value=httpx.Response(
                    201,
                    json={
                        "id": job_id,
                        "status": "pending",
                        "input": job_params["input"],
                    }
                )
            )
            
            kyro = Kyromesh(api_key="km_live_test123")
            
            # Submit job with all parameters
            job = kyro.run_job(
                task=job_params["task"],
                input=job_params["input"],
                provider=job_params["provider"],
                model=job_params["model"],
                timeout=job_params["timeout"],
                webhook_url=job_params["webhook_url"],
                guardrails=job_params["guardrails"],
                routing_policy=job_params["routing_policy"],
            )
            
            # Verify the request was made
            assert len(respx.calls) == 1
            request = respx.calls[0].request
            
            # Parse request payload
            request_payload = json.loads(request.content)
            
            # Verify required fields are present
            assert "task" in request_payload
            assert "input" in request_payload
            assert "timeout_seconds" in request_payload
            assert "routing_policy" in request_payload
            
            # Verify required field values match input
            assert request_payload["task"] == job_params["task"]
            assert request_payload["input"] == job_params["input"]
            assert request_payload["timeout_seconds"] == job_params["timeout"]
            assert request_payload["routing_policy"] == job_params["routing_policy"]
            
            # Verify optional fields are included when provided
            if job_params["provider"]:
                assert request_payload["preferred_provider"] == job_params["provider"]
            
            if job_params["model"]:
                assert request_payload["model"] == job_params["model"]
            
            if job_params["webhook_url"]:
                assert request_payload["webhook_url"] == job_params["webhook_url"]
            
            if job_params["guardrails"]:
                assert request_payload["guardrails"] == job_params["guardrails"]
            
            # Verify response is properly parsed
            assert job.id == job_id
            assert job.status == "pending"
            assert job.input == job_params["input"]
            
            kyro.close()
    
    @given(job_input_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_run_job_response_parsing_consistency(self, job_params):
        """
        Property: For all valid API responses, the SDK parses the response
        consistently and returns a Job object with all fields correctly mapped.
        
        Satisfies: Req 9 CP 9.1 (SDK Consistency)
        """
        job_id = str(uuid4())
        input_tokens = 150
        output_tokens = 75
        cost = 0.0125
        
        with respx.mock:
            # Mock the API response with all fields
            respx.post("https://api.kyromesh.com/api/v1/jobs").mock(
                return_value=httpx.Response(
                    201,
                    json={
                        "id": job_id,
                        "status": "pending",
                        "input": job_params["input"],
                        "output": None,
                        "error": None,
                        "provider": job_params["provider"],
                        "model": job_params["model"],
                        "cost": cost,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "retry_count": 0,
                    }
                )
            )
            
            kyro = Kyromesh(api_key="km_live_test123")
            job = kyro.run_job(
                task=job_params["task"],
                input=job_params["input"],
                provider=job_params["provider"],
                model=job_params["model"],
                timeout=job_params["timeout"],
                webhook_url=job_params["webhook_url"],
                guardrails=job_params["guardrails"],
                routing_policy=job_params["routing_policy"],
            )
            
            # Verify all fields are correctly parsed
            assert job.id == job_id
            assert job.status == "pending"
            assert job.input == job_params["input"]
            assert job.output is None
            assert job.error is None
            assert job.provider == job_params["provider"]
            assert job.model == job_params["model"]
            assert job.cost == cost
            assert job.input_tokens == input_tokens
            assert job.output_tokens == output_tokens
            assert job.retry_count == 0
            
            kyro.close()
    
    @given(st.data())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_run_job_error_responses_mapped_correctly(self, data):
        """
        Property: For all error responses from the API, the SDK maps them
        to the correct exception type.
        
        Satisfies: Req 9 CP 9.3 (Error Handling)
        """
        job_params = data.draw(job_input_strategy())
        
        with respx.mock:
            # Test 401 Unauthorized
            respx.post("https://api.kyromesh.com/api/v1/jobs").mock(
                return_value=httpx.Response(401, json={"error": "Unauthorized"})
            )
            
            kyro = Kyromesh(api_key="km_live_invalid")
            with pytest.raises(AuthError):
                kyro.run_job(
                    task=job_params["task"],
                    input=job_params["input"],
                )
            kyro.close()
        
        with respx.mock:
            # Test 429 Quota Exceeded
            respx.post("https://api.kyromesh.com/api/v1/jobs").mock(
                return_value=httpx.Response(
                    429,
                    json={"error": "Quota exceeded"},
                    headers={"Retry-After": "60"}
                )
            )
            
            kyro = Kyromesh(api_key="km_live_test123")
            with pytest.raises(QuotaExceededError) as exc_info:
                kyro.run_job(
                    task=job_params["task"],
                    input=job_params["input"],
                )
            assert exc_info.value.retry_after == 60
            kyro.close()
        
        with respx.mock:
            # Test 400 Guard Blocked
            respx.post("https://api.kyromesh.com/api/v1/jobs").mock(
                return_value=httpx.Response(
                    400,
                    json={
                        "error": "PII detected in input",
                        "code": "guard_pii_blocked"
                    }
                )
            )
            
            kyro = Kyromesh(api_key="km_live_test123")
            with pytest.raises(GuardBlockedError):
                kyro.run_job(
                    task=job_params["task"],
                    input=job_params["input"],
                )
            kyro.close()


# ============================================================================
# Property-Based Tests for submit_batch
# ============================================================================

class TestSubmitBatchPBT:
    """Property-based tests for submit_batch method."""
    
    @given(st.lists(batch_job_strategy(), min_size=1, max_size=100))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_submit_batch_request_schema_matches_api(self, batch_jobs):
        """
        Property: For all valid batch job inputs, the SDK request payload
        matches the REST API schema exactly.
        
        Satisfies: Req 9 CP 9.1 (SDK Consistency)
        """
        batch_id = str(uuid4())
        job_ids = [str(uuid4()) for _ in batch_jobs]
        
        with respx.mock:
            # Mock the API response
            respx.post("https://api.kyromesh.com/api/v1/batches").mock(
                return_value=httpx.Response(
                    201,
                    json={
                        "id": batch_id,
                        "status": "processing",
                        "total_jobs": len(batch_jobs),
                        "done_jobs": 0,
                        "failed_jobs": 0,
                        "job_ids": job_ids,
                    }
                )
            )
            
            kyro = Kyromesh(api_key="km_live_test123")
            batch = kyro.submit_batch(jobs=batch_jobs)
            
            # Verify the request was made
            assert len(respx.calls) == 1
            request = respx.calls[0].request
            
            # Parse request payload
            request_payload = json.loads(request.content)
            
            # Verify required fields are present
            assert "jobs" in request_payload
            assert isinstance(request_payload["jobs"], list)
            assert len(request_payload["jobs"]) == len(batch_jobs)
            
            # Verify each job in the batch matches the input
            for i, job_input in enumerate(batch_jobs):
                request_job = request_payload["jobs"][i]
                assert request_job["task"] == job_input["task"]
                assert request_job["input"] == job_input["input"]
            
            # Verify response is properly parsed
            assert batch.id == batch_id
            assert batch.status == "processing"
            assert batch.total_jobs == len(batch_jobs)
            assert len(batch.job_ids) == len(batch_jobs)
            
            kyro.close()
    
    @given(st.lists(batch_job_strategy(), min_size=1, max_size=50))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_submit_batch_response_parsing_consistency(self, batch_jobs):
        """
        Property: For all valid batch API responses, the SDK parses the response
        consistently and returns a Batch object with all fields correctly mapped.
        
        Satisfies: Req 9 CP 9.1 (SDK Consistency)
        """
        batch_id = str(uuid4())
        job_ids = [str(uuid4()) for _ in batch_jobs]
        
        with respx.mock:
            # Mock the API response with all fields
            respx.post("https://api.kyromesh.com/api/v1/batches").mock(
                return_value=httpx.Response(
                    201,
                    json={
                        "id": batch_id,
                        "status": "processing",
                        "total_jobs": len(batch_jobs),
                        "done_jobs": 0,
                        "failed_jobs": 0,
                        "job_ids": job_ids,
                        "created_at": "2024-01-01T00:00:00Z",
                    }
                )
            )
            
            kyro = Kyromesh(api_key="km_live_test123")
            batch = kyro.submit_batch(jobs=batch_jobs)
            
            # Verify all fields are correctly parsed
            assert batch.id == batch_id
            assert batch.status == "processing"
            assert batch.total_jobs == len(batch_jobs)
            assert batch.done_jobs == 0
            assert batch.failed_jobs == 0
            assert batch.job_ids == job_ids
            assert batch.created_at == "2024-01-01T00:00:00Z"
            
            kyro.close()


# ============================================================================
# Property-Based Tests for get_job_status
# ============================================================================

class TestGetJobStatusPBT:
    """Property-based tests for get_job_status method."""
    
    @given(st.data())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_get_job_status_response_parsing_consistency(self, data):
        """
        Property: For all valid job status responses, the SDK parses the response
        consistently and returns a Job object with all fields correctly mapped.
        
        Satisfies: Req 9 CP 9.1 (SDK Consistency)
        """
        job_id = str(uuid4())
        status = data.draw(st.sampled_from(["pending", "running", "completed", "failed"]))
        input_data = data.draw(input_strategy())
        
        # Build response based on status
        response_data = {
            "id": job_id,
            "status": status,
            "input": input_data,
        }
        
        # Add optional fields for completed jobs
        if status == "completed":
            response_data.update({
                "output": {"result": "success"},
                "cost": 0.05,
                "input_tokens": 100,
                "output_tokens": 50,
                "execution_ms": 1500,
            })
        elif status == "failed":
            response_data.update({
                "error": "Provider timeout",
                "execution_ms": 30000,
            })
        
        with respx.mock:
            respx.get(f"https://api.kyromesh.com/api/v1/jobs/{job_id}").mock(
                return_value=httpx.Response(200, json=response_data)
            )
            
            kyro = Kyromesh(api_key="km_live_test123")
            job = kyro.get_job_status(job_id)
            
            # Verify all fields are correctly parsed
            assert job.id == job_id
            assert job.status == status
            assert job.input == input_data
            
            if status == "completed":
                assert job.output == {"result": "success"}
                assert job.cost == 0.05
                assert job.input_tokens == 100
                assert job.output_tokens == 50
                assert job.execution_ms == 1500
                assert job.is_completed()
                assert job.is_successful()
            elif status == "failed":
                assert job.error == "Provider timeout"
                assert job.execution_ms == 30000
                assert job.is_completed()
                assert not job.is_successful()
            else:
                assert not job.is_completed()
            
            kyro.close()


# ============================================================================
# Property-Based Tests for get_usage
# ============================================================================

class TestGetUsagePBT:
    """Property-based tests for get_usage method."""
    
    @given(st.data())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_get_usage_response_parsing_consistency(self, data):
        """
        Property: For all valid usage responses, the SDK parses the response
        consistently and returns a Usage object with all fields correctly mapped.
        
        Satisfies: Req 9 CP 9.1 (SDK Consistency)
        """
        jobs_limit = data.draw(st.integers(min_value=100, max_value=100000))
        jobs_used = data.draw(st.integers(min_value=0, max_value=jobs_limit + 1000))
        jobs_remaining = max(0, jobs_limit - jobs_used)
        overage_jobs = max(0, jobs_used - jobs_limit)
        total_cost = data.draw(st.floats(min_value=0, max_value=10000))
        tier = data.draw(st.sampled_from(["free", "starter", "pro", "team"]))
        overage_rate = data.draw(st.floats(min_value=0, max_value=1))
        
        with respx.mock:
            respx.get("https://api.kyromesh.com/api/v1/usage").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "jobs_used": jobs_used,
                        "jobs_limit": jobs_limit,
                        "jobs_remaining": jobs_remaining,
                        "overage_jobs": overage_jobs,
                        "total_cost": total_cost,
                        "tier": tier,
                        "overage_rate": overage_rate,
                    }
                )
            )
            
            kyro = Kyromesh(api_key="km_live_test123")
            usage = kyro.get_usage()
            
            # Verify all fields are correctly parsed
            assert usage.jobs_used == jobs_used
            assert usage.jobs_limit == jobs_limit
            assert usage.jobs_remaining == jobs_remaining
            assert usage.overage_jobs == overage_jobs
            assert usage.total_cost == total_cost
            assert usage.tier == tier
            assert usage.overage_rate == overage_rate
            
            # Verify calculated properties
            expected_percentage = (jobs_used / jobs_limit * 100) if jobs_limit > 0 else 0
            assert usage.usage_percentage() == expected_percentage
            
            kyro.close()


# ============================================================================
# Integration Property-Based Tests
# ============================================================================

class TestSDKIntegrationPBT:
    """Integration property-based tests for SDK consistency."""
    
    @given(job_input_strategy())
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_run_job_then_get_status_consistency(self, job_params):
        """
        Property: Submitting a job and then retrieving its status returns
        consistent data across both calls.
        
        Satisfies: Req 9 CP 9.1 (SDK Consistency)
        """
        job_id = str(uuid4())
        
        with respx.mock:
            # Mock run_job response
            respx.post("https://api.kyromesh.com/api/v1/jobs").mock(
                return_value=httpx.Response(
                    201,
                    json={
                        "id": job_id,
                        "status": "pending",
                        "input": job_params["input"],
                    }
                )
            )
            
            # Mock get_job_status response
            respx.get(f"https://api.kyromesh.com/api/v1/jobs/{job_id}").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "id": job_id,
                        "status": "pending",
                        "input": job_params["input"],
                    }
                )
            )
            
            kyro = Kyromesh(api_key="km_live_test123")
            
            # Submit job
            submitted_job = kyro.run_job(
                task=job_params["task"],
                input=job_params["input"],
                provider=job_params["provider"],
                model=job_params["model"],
                timeout=job_params["timeout"],
                webhook_url=job_params["webhook_url"],
                guardrails=job_params["guardrails"],
                routing_policy=job_params["routing_policy"],
            )
            
            # Retrieve job status
            retrieved_job = kyro.get_job_status(submitted_job.id)
            
            # Verify consistency
            assert submitted_job.id == retrieved_job.id
            assert submitted_job.status == retrieved_job.status
            assert submitted_job.input == retrieved_job.input
            
            kyro.close()
    
    @given(st.lists(batch_job_strategy(), min_size=1, max_size=50))
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_submit_batch_then_get_status_consistency(self, batch_jobs):
        """
        Property: Submitting a batch and then retrieving its status returns
        consistent data across both calls.
        
        Satisfies: Req 9 CP 9.1 (SDK Consistency)
        """
        batch_id = str(uuid4())
        job_ids = [str(uuid4()) for _ in batch_jobs]
        
        with respx.mock:
            # Mock submit_batch response
            respx.post("https://api.kyromesh.com/api/v1/batches").mock(
                return_value=httpx.Response(
                    201,
                    json={
                        "id": batch_id,
                        "status": "processing",
                        "total_jobs": len(batch_jobs),
                        "done_jobs": 0,
                        "failed_jobs": 0,
                        "job_ids": job_ids,
                    }
                )
            )
            
            # Mock get_batch_status response
            respx.get(f"https://api.kyromesh.com/api/v1/batches/{batch_id}").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "id": batch_id,
                        "status": "processing",
                        "total_jobs": len(batch_jobs),
                        "done_jobs": 0,
                        "failed_jobs": 0,
                        "job_ids": job_ids,
                    }
                )
            )
            
            kyro = Kyromesh(api_key="km_live_test123")
            
            # Submit batch
            submitted_batch = kyro.submit_batch(jobs=batch_jobs)
            
            # Retrieve batch status
            retrieved_batch = kyro.get_batch_status(submitted_batch.id)
            
            # Verify consistency
            assert submitted_batch.id == retrieved_batch.id
            assert submitted_batch.status == retrieved_batch.status
            assert submitted_batch.total_jobs == retrieved_batch.total_jobs
            assert submitted_batch.done_jobs == retrieved_batch.done_jobs
            assert submitted_batch.failed_jobs == retrieved_batch.failed_jobs
            assert submitted_batch.job_ids == retrieved_batch.job_ids
            
            kyro.close()

