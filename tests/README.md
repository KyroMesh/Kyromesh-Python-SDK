# Kyromesh Python SDK Tests

This directory contains comprehensive unit tests for the Kyromesh Python SDK using `respx` for mocking HTTP requests.

## Test Coverage

### TestKyromeshInit
- Valid API key initialization (live and test keys)
- Custom base URL configuration
- Invalid API key validation (empty, wrong prefix, None)
- Context manager usage

### TestRunJob
- Successful job submission (201 response)
- Job submission with all optional parameters
- Authentication error (401)
- Quota exceeded error (429) with Retry-After header
- Guard blocked errors:
  - PII detection (400 with guard_pii_blocked code)
  - Prompt injection detection (400 with guard_injection_blocked code)
- Provider error (500)
- Invalid JSON response parsing
- Parameter validation:
  - Invalid task (empty string)
  - Invalid input (non-dict)
  - Invalid timeout (zero or negative)
  - Invalid routing_policy (not in cost/latency/quality)

### TestGetJobStatus
- Retrieve pending job status
- Retrieve completed job status with output, cost, and token counts
- Retrieve failed job status with error message
- Job not found error (404)
- Authentication error (401)
- Server error (500)
- Parameter validation (invalid job_id)

### TestWaitForJob
- Wait for job that completes immediately
- Wait for job that times out
- Parameter validation:
  - Invalid job_id
  - Invalid timeout
  - Invalid poll_interval

### TestSubmitBatch
- Successful batch submission (201 response)
- Batch submission with optional job parameters
- Authentication error (401)
- Quota exceeded error (429)
- Invalid request error (400)
- Server error (500)
- Parameter validation:
  - Empty jobs list
  - Too many jobs (>1000)
  - Invalid jobs type (non-list)
  - Job missing task field
  - Job missing input field

### TestGetBatchStatus
- Retrieve batch status while processing
- Retrieve completed batch status
- Batch not found error (404)
- Authentication error (401)
- Parameter validation (invalid batch_id)

### TestGetUsage
- Successful usage retrieval
- Usage retrieval with exceeded quota
- Authentication error (401)
- Server error (500)

### TestExceptionHierarchy
- AuthError properties and inheritance
- QuotaExceededError properties (jobs_remaining, retry_after)
- GuardBlockedError properties (block_reason)
- ProviderError properties (provider, status_code)
- TimeoutError properties (timeout_seconds)

### TestModelProperties
- Job.is_completed() for all status values
- Job.is_successful() for completed/failed states
- Batch.is_completed() for processing/completed states
- Batch.progress_percentage() calculation
- Usage.usage_percentage() calculation

## Running Tests

### Run all tests
```bash
pytest packages/sdk-python/tests/
```

### Run unit tests only (mocked HTTP)
```bash
pytest packages/sdk-python/tests/test_client.py -v
```

### Run integration tests only (requires local docker-compose stack)
```bash
pytest packages/sdk-python/tests/test_integration.py -v
```

### Run specific test class
```bash
pytest packages/sdk-python/tests/test_client.py::TestRunJob
```

### Run specific test
```bash
pytest packages/sdk-python/tests/test_client.py::TestRunJob::test_run_job_success
```

### Run with coverage
```bash
pytest packages/sdk-python/tests/ --cov=kyromesh --cov-report=html
```

### Run with verbose output
```bash
pytest packages/sdk-python/tests/ -v
```

### Run integration tests with custom configuration
```bash
KYROMESH_API_URL=http://localhost:8080 \
KYROMESH_API_KEY=km_live_test_integration \
KYROMESH_INTEGRATION_TIMEOUT=60 \
KYROMESH_POLL_INTERVAL=2 \
pytest packages/sdk-python/tests/test_integration.py -v
```

## Test Design

### HTTP Mocking with respx
All unit tests use `respx` to mock HTTP requests. This allows:
- Testing without making real API calls
- Simulating various HTTP status codes and responses
- Verifying request payloads and headers
- Testing error handling paths

### Integration Tests
Integration tests in `test_integration.py` validate the SDK against a running local Kyromesh stack:
- **Full Job Lifecycle**: Job submission, status polling, completion, result retrieval
- **Quota Enforcement**: Quota checking, overage handling, usage tracking
- **Guard Blocking**: PII detection, injection detection, toxicity detection
- **Batch Processing**: Batch submission, status tracking, independent job processing
- **Error Handling**: Invalid API keys, timeouts, nonexistent resources
- **Multi-Tenant Isolation**: Workspace data isolation, RLS enforcement
- **Token and Cost Tracking**: Token usage capture, cost calculation

#### Prerequisites for Integration Tests
1. Local docker-compose stack running:
   ```bash
   docker-compose up
   ```

2. Services accessible at:
   - API: http://localhost:8080
   - Guard: http://localhost:8081
   - Router: http://localhost:8082
   - Subscription: http://localhost:8084
   - Worker: http://localhost:8085

3. PostgreSQL and Redis running

4. Test workspace and API key created in the database

#### Integration Test Configuration
Environment variables:
- `KYROMESH_API_URL`: API base URL (default: http://localhost:8080)
- `KYROMESH_API_KEY`: Test API key (default: km_live_test_integration)
- `KYROMESH_INTEGRATION_TIMEOUT`: Max wait time for job completion (default: 60 seconds)
- `KYROMESH_POLL_INTERVAL`: Interval between status polls (default: 2 seconds)

### Exception Testing
Tests verify that:
- Correct exception types are raised for each error condition
- Exception properties contain expected values
- Exception hierarchy is correct (all inherit from KyromeshError)

### Parameter Validation
Tests verify that:
- Invalid parameters raise ValueError with descriptive messages
- Valid parameters are accepted
- Default values are applied correctly

### Response Parsing
Tests verify that:
- Successful responses are parsed correctly
- Response data is mapped to model objects
- Invalid JSON responses raise appropriate errors
- Missing required fields are handled

## Correctness Properties Validated

### CP 9.1 - SDK Consistency
Tests verify that SDK behavior matches the REST API:
- Request payloads match API schema
- Response parsing matches API response format
- Error handling matches API error responses

### CP 9.3 - Error Handling
Tests verify that:
- All API errors are properly caught and re-raised as Python exceptions
- Exception types match error conditions
- Exception properties contain relevant error details
- Authentication errors are distinguished from other errors

### Integration Test Coverage

#### Full Job Lifecycle (test_integration.py::TestFullJobLifecycle)
- **test_job_submission_and_completion**: Validates Req 1 AC 1.1-1.4, 1.6, 1.8, CP 1.1-1.3
- **test_job_status_polling**: Validates Req 1 AC 1.6, CP 1.2-1.3
- **test_job_with_webhook**: Validates Req 1 AC 1.7, Req 17 AC 17.1
- **test_job_with_guardrails**: Validates Req 1 AC 1.1, Req 3/4/5 AC 3.1-3.4
- **test_job_with_explicit_provider**: Validates Req 2 AC 2.7, 2.1
- **test_job_with_routing_policy**: Validates Req 2 AC 2.2-2.5

#### Quota Enforcement (test_integration.py::TestQuotaEnforcement)
- **test_quota_exceeded_rejection**: Validates Req 7 AC 7.2, 7.4, CP 7.2
- **test_usage_tracking**: Validates Req 7 AC 7.6, CP 7.1

#### Guard Blocking (test_integration.py::TestGuardBlocking)
- **test_pii_detection_and_blocking**: Validates Req 3 AC 3.1, 3.4, CP 3.3
- **test_pii_redaction_with_warn_policy**: Validates Req 3 AC 3.3, CP 3.2
- **test_injection_detection_and_blocking**: Validates Req 4 AC 4.1, 4.3, CP 4.2
- **test_toxicity_detection_and_blocking**: Validates Req 5 AC 5.1, 5.3, CP 5.2
- **test_multiple_guardrails**: Validates Req 3/4/5 AC 3.1, 4.1, 5.1

#### Batch Processing (test_integration.py::TestBatchProcessing)
- **test_batch_submission_and_completion**: Validates Req 16 AC 16.1-16.3, 16.5
- **test_batch_with_mixed_parameters**: Validates Req 16 AC 16.1, 16.5

#### Error Handling (test_integration.py::TestErrorHandling)
- **test_invalid_api_key**: Validates Req 12 AC 12.7
- **test_job_timeout_enforcement**: Validates Req 1 AC 1.8
- **test_nonexistent_job_retrieval**: Validates Req 10 AC 10.6, 10.9

#### Multi-Tenant Isolation (test_integration.py::TestMultiTenantIsolation)
- **test_workspace_isolation**: Validates Req 11 AC 11.2-11.3, CP 11.1

#### Token and Cost Tracking (test_integration.py::TestTokenAndCostTracking)
- **test_token_usage_tracking**: Validates Req 14 AC 14.1, 14.4
- **test_cost_calculation**: Validates Req 14 AC 14.2, 14.4

## Dependencies

- `pytest>=7.0.0` - Test framework
- `respx>=0.20.0` - HTTP mocking library
- `httpx>=0.24.0` - HTTP client (used by SDK)
- `hypothesis>=6.70.0` - Property-based testing (for future PBT tests)
