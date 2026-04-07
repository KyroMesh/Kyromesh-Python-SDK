"""Kyromesh client for submitting and managing AI jobs."""

from typing import Optional, Dict, Any, List
import time
import httpx
from kyromesh.models import Job, Batch, Usage
from kyromesh.exceptions import (
    AuthError,
    QuotaExceededError,
    GuardBlockedError,
    ProviderError,
    KyromeshError,
    TimeoutError,
)


class Kyromesh:
    """
    Kyromesh client for submitting and managing AI jobs.
    
    Provides a simple interface to interact with the Kyromesh API.
    
    Args:
        api_key: The API key for authentication (format: km_live_xxx or km_test_xxx)
        base_url: The base URL for the Kyromesh API (default: https://api.kyromesh.com)
    
    Example:
        >>> kyro = Kyromesh(api_key="km_live_xxx")
        >>> job = kyro.run_job(task="summarize", input={"text": "..."})
        >>> status = kyro.get_job_status(job.id)
    """
    
    DEFAULT_BASE_URL = "https://api.kyromesh.com"
    
    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
    ) -> None:
        """
        Initialize the Kyromesh client.
        
        Args:
            api_key: The API key for authentication
            base_url: The base URL for the API (defaults to https://api.kyromesh.com)
        
        Raises:
            ValueError: If api_key is empty or invalid format
        """
        if not api_key or not isinstance(api_key, str):
            raise ValueError("api_key must be a non-empty string")
        
        if not api_key.startswith(("km_live_", "km_test_")):
            raise ValueError("api_key must start with 'km_live_' or 'km_test_'")
        
        self.api_key = api_key
        self.base_url = base_url or self.DEFAULT_BASE_URL
        
        # Initialize httpx client with default headers
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "kyromesh-python-sdk/0.1.0",
            },
            timeout=30.0,
        )
    
    def __enter__(self) -> "Kyromesh":
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - closes the HTTP client."""
        self.close()
    
    def close(self) -> None:
        """Close the HTTP client session."""
        if self._client:
            self._client.close()
    
    def __del__(self) -> None:
        """Cleanup on deletion."""
        try:
            self.close()
        except Exception:
            pass
    
    def run_job(
        self,
        task: str,
        input: Dict[str, Any],
        provider: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 300,
        webhook_url: Optional[str] = None,
        guardrails: Optional[List[str]] = None,
        routing_policy: str = "cost",
    ) -> Job:
        """
        Submit an AI job for asynchronous execution.
        
        Submits a job to the Kyromesh API and returns immediately with a job ID.
        Use get_job_status() or wait_for_job() to retrieve results.
        
        Args:
            task: The task type (e.g., "summarize", "classify", "generate")
            input: Input data for the task (dict)
            provider: Optional provider override ("openai", "bedrock", "grok")
            model: Optional model override (e.g., "gpt-4", "claude-3")
            timeout: Job execution timeout in seconds (default: 300)
            webhook_url: Optional webhook URL for completion callback
            guardrails: Optional list of guardrails to apply (["pii", "injection", "toxicity"])
            routing_policy: Routing policy ("cost", "latency", "quality") (default: "cost")
        
        Returns:
            Job: Job object with id and initial status
        
        Raises:
            AuthError: If authentication fails (401)
            QuotaExceededError: If quota is exceeded (429)
            GuardBlockedError: If Guard blocks the request (400 from guard)
            ProviderError: If provider returns an error
            KyromeshError: For other API errors
            ValueError: If required parameters are invalid
        
        Example:
            >>> kyro = Kyromesh(api_key="km_live_xxx")
            >>> job = kyro.run_job(
            ...     task="summarize",
            ...     input={"text": "Long document..."},
            ...     guardrails=["pii"],
            ...     routing_policy="cost"
            ... )
            >>> print(job.id)
        """
        # Validate required parameters
        if not task or not isinstance(task, str):
            raise ValueError("task must be a non-empty string")
        
        if not isinstance(input, dict):
            raise ValueError("input must be a dictionary")
        
        if timeout <= 0:
            raise ValueError("timeout must be a positive integer")
        
        if routing_policy not in ("cost", "latency", "quality"):
            raise ValueError("routing_policy must be 'cost', 'latency', or 'quality'")
        
        if guardrails is None:
            guardrails = []
        
        # Build request payload
        payload = {
            "task": task,
            "input": input,
            "timeout_seconds": timeout,
            "routing_policy": routing_policy,
        }
        
        # Add optional fields
        if provider:
            payload["preferred_provider"] = provider
        
        if model:
            payload["model"] = model
        
        if webhook_url:
            payload["webhook_url"] = webhook_url
        
        if guardrails:
            payload["guardrails"] = guardrails
        
        # Make API request
        try:
            response = self._client.post("/api/v1/jobs", json=payload)
        except httpx.TimeoutException as e:
            raise KyromeshError(f"Request timed out: {str(e)}", "timeout_error")
        except httpx.RequestError as e:
            raise KyromeshError(f"Request failed: {str(e)}", "request_error")
        
        # Handle response status codes
        if response.status_code == 401:
            raise AuthError("Invalid or expired API key")
        
        if response.status_code == 429:
            # Quota exceeded
            try:
                error_data = response.json()
                retry_after = response.headers.get("Retry-After", "60")
                raise QuotaExceededError(
                    message=error_data.get("error", "Quota exceeded"),
                    retry_after=int(retry_after),
                )
            except (ValueError, KeyError):
                raise QuotaExceededError()
        
        if response.status_code == 400:
            # Could be guard blocked or invalid request
            try:
                error_data = response.json()
                error_msg = error_data.get("error", "Bad request")
                error_code = error_data.get("code", "")
                
                if "guard" in error_code.lower() or "pii" in error_msg.lower() or "injection" in error_msg.lower():
                    raise GuardBlockedError(
                        message=error_msg,
                        block_reason=error_code,
                    )
                else:
                    raise KyromeshError(error_msg, error_code)
            except (ValueError, KeyError):
                raise KyromeshError("Bad request", "bad_request")
        
        if response.status_code >= 500:
            raise ProviderError(
                message="Server error",
                status_code=response.status_code,
            )
        
        if response.status_code != 201:
            try:
                error_data = response.json()
                raise KyromeshError(
                    error_data.get("error", f"Unexpected status {response.status_code}"),
                    error_data.get("code", "unknown_error"),
                )
            except (ValueError, KeyError):
                raise KyromeshError(
                    f"Unexpected status {response.status_code}",
                    "unknown_error",
                )
        
        # Parse successful response
        try:
            data = response.json()
            job = Job(
                id=data["id"],
                status=data.get("status", "pending"),
                input=data.get("input", input),
                output=data.get("output"),
                error=data.get("error"),
                provider=data.get("provider"),
                model=data.get("model"),
                cost=data.get("cost"),
                input_tokens=data.get("input_tokens"),
                output_tokens=data.get("output_tokens"),
                retry_count=data.get("retry_count", 0),
            )
            return job
        except (ValueError, KeyError) as e:
            raise KyromeshError(f"Failed to parse response: {str(e)}", "parse_error")
    
    def get_job_status(self, job_id: str) -> Job:
        """
        Retrieve the status and details of a submitted job.
        
        Polls the Kyromesh API to get the current status of a job, including
        output, cost, and token usage once the job completes.
        
        Args:
            job_id: The ID of the job to retrieve
        
        Returns:
            Job: Job object with current status, output, cost, and token usage
        
        Raises:
            AuthError: If authentication fails (401)
            KyromeshError: If job not found (404) or other API errors
            ValueError: If job_id is invalid
        
        Example:
            >>> kyro = Kyromesh(api_key="km_live_xxx")
            >>> job = kyro.run_job(task="summarize", input={"text": "..."})
            >>> status = kyro.get_job_status(job.id)
            >>> print(status.status)  # "pending", "running", "completed", or "failed"
            >>> if status.is_completed():
            ...     print(status.output)
            ...     print(f"Cost: ${status.cost}")
        """
        # Validate job_id
        if not job_id or not isinstance(job_id, str):
            raise ValueError("job_id must be a non-empty string")
        
        # Make API request
        try:
            response = self._client.get(f"/api/v1/jobs/{job_id}")
        except httpx.TimeoutException as e:
            raise KyromeshError(f"Request timed out: {str(e)}", "timeout_error")
        except httpx.RequestError as e:
            raise KyromeshError(f"Request failed: {str(e)}", "request_error")
        
        # Handle response status codes
        if response.status_code == 401:
            raise AuthError("Invalid or expired API key")
        
        if response.status_code == 404:
            raise KyromeshError(f"Job not found: {job_id}", "job_not_found")
        
        if response.status_code >= 500:
            raise KyromeshError(
                "Server error",
                "server_error",
            )
        
        if response.status_code != 200:
            try:
                error_data = response.json()
                raise KyromeshError(
                    error_data.get("error", f"Unexpected status {response.status_code}"),
                    error_data.get("code", "unknown_error"),
                )
            except (ValueError, KeyError):
                raise KyromeshError(
                    f"Unexpected status {response.status_code}",
                    "unknown_error",
                )
        
        # Parse successful response
        try:
            data = response.json()
            job = Job(
                id=data["id"],
                status=data.get("status", "pending"),
                input=data.get("input", {}),
                output=data.get("output"),
                error=data.get("error"),
                provider=data.get("provider"),
                model=data.get("model"),
                cost=data.get("cost"),
                input_tokens=data.get("input_tokens"),
                output_tokens=data.get("output_tokens"),
                created_at=data.get("created_at"),
                completed_at=data.get("completed_at"),
                execution_ms=data.get("execution_ms"),
                retry_count=data.get("retry_count", 0),
            )
            return job
        except (ValueError, KeyError) as e:
            raise KyromeshError(f"Failed to parse response: {str(e)}", "parse_error")
    
    def wait_for_job(
        self,
        job_id: str,
        timeout: int = 300,
        poll_interval: int = 2,
    ) -> Job:
        """
        Wait for a job to complete with polling.
        
        Polls the job status at regular intervals until the job completes
        (either successfully or with failure) or the timeout is reached.
        
        Args:
            job_id: The ID of the job to wait for
            timeout: Maximum time to wait in seconds (default: 300)
            poll_interval: Time between status checks in seconds (default: 2)
        
        Returns:
            Job: The completed job object with output, cost, and token usage
        
        Raises:
            TimeoutError: If the job does not complete within the timeout period
            AuthError: If authentication fails (401)
            KyromeshError: If job not found (404) or other API errors
            ValueError: If parameters are invalid
        
        Example:
            >>> kyro = Kyromesh(api_key="km_live_xxx")
            >>> job = kyro.run_job(task="summarize", input={"text": "..."})
            >>> result = kyro.wait_for_job(job.id, timeout=300, poll_interval=2)
            >>> print(result.output)
            >>> print(f"Cost: ${result.cost}")
        """
        # Validate parameters
        if not job_id or not isinstance(job_id, str):
            raise ValueError("job_id must be a non-empty string")
        
        if timeout <= 0:
            raise ValueError("timeout must be a positive integer")
        
        if poll_interval <= 0:
            raise ValueError("poll_interval must be a positive integer")
        
        # Track elapsed time
        start_time = time.time()
        
        # Poll until completion or timeout
        while True:
            # Check if we've exceeded the timeout
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TimeoutError(
                    message=f"Job {job_id} did not complete within {timeout} seconds",
                    timeout_seconds=timeout,
                )
            
            # Get current job status
            job = self.get_job_status(job_id)
            
            # Check if job has completed
            if job.is_completed():
                return job
            
            # Sleep before next poll
            time.sleep(poll_interval)
    
    def submit_batch(
        self,
        jobs: List[Dict[str, Any]],
    ) -> Batch:
        """
        Submit multiple jobs as a batch for asynchronous execution.
        
        Submits a batch of up to 1,000 jobs to the Kyromesh API and returns
        immediately with a batch ID and individual job IDs. Use get_batch_status()
        to track batch progress.
        
        Args:
            jobs: List of job dictionaries, each containing:
                - task (str): The task type (e.g., "summarize", "classify")
                - input (dict): Input data for the task
                - provider (str, optional): Provider override
                - model (str, optional): Model override
                - timeout (int, optional): Execution timeout in seconds
                - webhook_url (str, optional): Webhook URL for completion callback
                - guardrails (list, optional): Guardrails to apply
                - routing_policy (str, optional): Routing policy ("cost", "latency", "quality")
        
        Returns:
            Batch: Batch object with batch_id, job_ids, and status
        
        Raises:
            AuthError: If authentication fails (401)
            QuotaExceededError: If quota is exceeded (429)
            KyromeshError: For other API errors
            ValueError: If jobs list is invalid or exceeds 1,000 items
        
        Example:
            >>> kyro = Kyromesh(api_key="km_live_xxx")
            >>> batch = kyro.submit_batch(jobs=[
            ...     {"task": "summarize", "input": {"text": "..."}},
            ...     {"task": "classify", "input": {"text": "..."}},
            ... ])
            >>> print(batch.id)
            >>> print(batch.job_ids)
        """
        # Validate jobs parameter
        if not isinstance(jobs, list):
            raise ValueError("jobs must be a list of job dictionaries")
        
        if len(jobs) == 0:
            raise ValueError("jobs list cannot be empty")
        
        if len(jobs) > 1000:
            raise ValueError("jobs list cannot exceed 1,000 items")
        
        # Validate each job in the list
        for i, job in enumerate(jobs):
            if not isinstance(job, dict):
                raise ValueError(f"Job at index {i} must be a dictionary")
            
            if "task" not in job or not job["task"]:
                raise ValueError(f"Job at index {i} must have a 'task' field")
            
            if "input" not in job or not isinstance(job["input"], dict):
                raise ValueError(f"Job at index {i} must have an 'input' field (dict)")
        
        # Build request payload
        payload = {"jobs": jobs}
        
        # Make API request
        try:
            response = self._client.post("/api/v1/batches", json=payload)
        except httpx.TimeoutException as e:
            raise KyromeshError(f"Request timed out: {str(e)}", "timeout_error")
        except httpx.RequestError as e:
            raise KyromeshError(f"Request failed: {str(e)}", "request_error")
        
        # Handle response status codes
        if response.status_code == 401:
            raise AuthError("Invalid or expired API key")
        
        if response.status_code == 429:
            # Quota exceeded
            try:
                error_data = response.json()
                retry_after = response.headers.get("Retry-After", "60")
                raise QuotaExceededError(
                    message=error_data.get("error", "Quota exceeded"),
                    retry_after=int(retry_after),
                )
            except (ValueError, KeyError):
                raise QuotaExceededError()
        
        if response.status_code == 400:
            # Invalid request
            try:
                error_data = response.json()
                raise KyromeshError(
                    error_data.get("error", "Bad request"),
                    error_data.get("code", "bad_request"),
                )
            except (ValueError, KeyError):
                raise KyromeshError("Bad request", "bad_request")
        
        if response.status_code >= 500:
            raise KyromeshError(
                "Server error",
                "server_error",
            )
        
        if response.status_code != 201:
            try:
                error_data = response.json()
                raise KyromeshError(
                    error_data.get("error", f"Unexpected status {response.status_code}"),
                    error_data.get("code", "unknown_error"),
                )
            except (ValueError, KeyError):
                raise KyromeshError(
                    f"Unexpected status {response.status_code}",
                    "unknown_error",
                )
        
        # Parse successful response
        try:
            data = response.json()
            batch = Batch(
                id=data["id"],
                status=data.get("status", "processing"),
                total_jobs=data.get("total_jobs", len(jobs)),
                done_jobs=data.get("done_jobs", 0),
                failed_jobs=data.get("failed_jobs", 0),
                job_ids=data.get("job_ids", []),
                created_at=data.get("created_at"),
            )
            return batch
        except (ValueError, KeyError) as e:
            raise KyromeshError(f"Failed to parse response: {str(e)}", "parse_error")
    
    def get_batch_status(self, batch_id: str) -> Batch:
        """
        Retrieve the status and details of a submitted batch.
        
        Polls the Kyromesh API to get the current status of a batch, including
        total jobs, completed jobs, and failed jobs counts.
        
        Args:
            batch_id: The ID of the batch to retrieve
        
        Returns:
            Batch: Batch object with current status and job counts
        
        Raises:
            AuthError: If authentication fails (401)
            KyromeshError: If batch not found (404) or other API errors
            ValueError: If batch_id is invalid
        
        Example:
            >>> kyro = Kyromesh(api_key="km_live_xxx")
            >>> batch = kyro.submit_batch(jobs=[...])
            >>> status = kyro.get_batch_status(batch.id)
            >>> print(status.status)  # "processing" or "completed"
            >>> print(f"Progress: {status.done_jobs}/{status.total_jobs}")
            >>> if status.is_completed():
            ...     print(f"Failed: {status.failed_jobs}")
        """
        # Validate batch_id
        if not batch_id or not isinstance(batch_id, str):
            raise ValueError("batch_id must be a non-empty string")
        
        # Make API request
        try:
            response = self._client.get(f"/api/v1/batches/{batch_id}")
        except httpx.TimeoutException as e:
            raise KyromeshError(f"Request timed out: {str(e)}", "timeout_error")
        except httpx.RequestError as e:
            raise KyromeshError(f"Request failed: {str(e)}", "request_error")
        
        # Handle response status codes
        if response.status_code == 401:
            raise AuthError("Invalid or expired API key")
        
        if response.status_code == 404:
            raise KyromeshError(f"Batch not found: {batch_id}", "batch_not_found")
        
        if response.status_code >= 500:
            raise KyromeshError(
                "Server error",
                "server_error",
            )
        
        if response.status_code != 200:
            try:
                error_data = response.json()
                raise KyromeshError(
                    error_data.get("error", f"Unexpected status {response.status_code}"),
                    error_data.get("code", "unknown_error"),
                )
            except (ValueError, KeyError):
                raise KyromeshError(
                    f"Unexpected status {response.status_code}",
                    "unknown_error",
                )
        
        # Parse successful response
        try:
            data = response.json()
            batch = Batch(
                id=data["id"],
                status=data.get("status", "processing"),
                total_jobs=data.get("total_jobs", 0),
                done_jobs=data.get("done_jobs", 0),
                failed_jobs=data.get("failed_jobs", 0),
                job_ids=data.get("job_ids", []),
                created_at=data.get("created_at"),
                completed_at=data.get("completed_at"),
            )
            return batch
        except (ValueError, KeyError) as e:
            raise KyromeshError(f"Failed to parse response: {str(e)}", "parse_error")
    
    def get_usage(self) -> Usage:
        """
        Retrieve usage metrics for the current workspace.
        
        Fetches the current usage statistics including jobs used, remaining quota,
        overage jobs, total cost, subscription tier, and overage rate.
        
        Returns:
            Usage: Usage object with current usage metrics
        
        Raises:
            AuthError: If authentication fails (401)
            KyromeshError: For other API errors
        
        Example:
            >>> kyro = Kyromesh(api_key="km_live_xxx")
            >>> usage = kyro.get_usage()
            >>> print(f"Jobs used: {usage.jobs_used}/{usage.jobs_limit}")
            >>> print(f"Usage: {usage.usage_percentage():.1f}%")
            >>> print(f"Total cost: ${usage.total_cost:.2f}")
            >>> print(f"Tier: {usage.tier}")
        """
        # Make API request
        try:
            response = self._client.get("/api/v1/usage")
        except httpx.TimeoutException as e:
            raise KyromeshError(f"Request timed out: {str(e)}", "timeout_error")
        except httpx.RequestError as e:
            raise KyromeshError(f"Request failed: {str(e)}", "request_error")
        
        # Handle response status codes
        if response.status_code == 401:
            raise AuthError("Invalid or expired API key")
        
        if response.status_code >= 500:
            raise KyromeshError(
                "Server error",
                "server_error",
            )
        
        if response.status_code != 200:
            try:
                error_data = response.json()
                raise KyromeshError(
                    error_data.get("error", f"Unexpected status {response.status_code}"),
                    error_data.get("code", "unknown_error"),
                )
            except (ValueError, KeyError):
                raise KyromeshError(
                    f"Unexpected status {response.status_code}",
                    "unknown_error",
                )
        
        # Parse successful response
        try:
            data = response.json()
            usage = Usage(
                jobs_used=data.get("jobs_used", 0),
                jobs_limit=data.get("jobs_limit", 0),
                jobs_remaining=data.get("jobs_remaining", 0),
                overage_jobs=data.get("overage_jobs", 0),
                total_cost=data.get("total_cost", 0.0),
                tier=data.get("tier", "free"),
                overage_rate=data.get("overage_rate", 0.0),
            )
            return usage
        except (ValueError, KeyError) as e:
            raise KyromeshError(f"Failed to parse response: {str(e)}", "parse_error")
