# Performance Testing

## Overview

Performance tests validate that the notification service meets performance requirements under various load conditions. Using Locust, we simulate realistic user behavior and measure response times, throughput, resource usage, and system behavior under stress.

Performance testing helps:
- **Identify bottlenecks** - Find slow code paths and resource constraints
- **Establish baselines** - Set performance benchmarks for regression detection
- **Validate scalability** - Ensure system can handle growth
- **Test under stress** - Verify graceful degradation under load
- **Optimize resources** - Right-size infrastructure

## Performance Metrics

We track four key categories of metrics:

### 1. Response Time / Latency

- **p50 (median)** - 50th percentile response time
- **p95** - 95th percentile response time
- **p99** - 99th percentile response time
- **Max** - Maximum response time observed

**Targets:**
- p50: < 200ms for API endpoints
- p95: < 500ms for API endpoints
- p99: < 1000ms for API endpoints

### 2. Throughput / RPS

- **Requests per second** - Total requests handled per second
- **Successful requests** - Non-error responses per second
- **Failed requests** - Error responses per second

**Targets:**
- Minimum: 100 RPS per instance
- Target: 500 RPS per instance
- Peak: 1000 RPS per instance (burst capacity)

### 3. Resource Usage

- **CPU utilization** - Percentage of CPU used
- **Memory usage** - RAM consumption
- **Database connections** - Active connection pool usage
- **Queue depth** - Messages waiting in queue

**Targets:**
- CPU: < 70% under normal load
- Memory: < 80% of allocated memory
- DB connections: < 80% of pool size
- Queue depth: < 1000 messages

### 4. Error Rate

- **Error percentage** - Percentage of failed requests
- **Timeout rate** - Requests that timeout
- **5xx errors** - Server error rate

**Targets:**
- Error rate: < 0.1% under normal load
- Error rate: < 1% under peak load
- 5xx errors: < 0.01%

## Directory Structure

```
tests/performance/
├── __init__.py
├── locustfile_notifications.py      # Notification endpoint tests
├── locustfile_batch.py               # Batch operation tests
├── locustfile_read_heavy.py          # Read-heavy workload
├── locustfile_write_heavy.py         # Write-heavy workload
├── locustfile_stress.py              # Stress testing
├── common/
│   ├── __init__.py
│   ├── tasks.py                      # Shared task definitions
│   └── utils.py                      # Helper utilities
└── results/                          # Performance test results
    ├── baseline/
    └── regression/
```

## Writing Performance Tests

### Basic Locust Test

```python
"""Performance tests for notification endpoints."""

from locust import HttpUser, task, between
from random import randint


class NotificationUser(HttpUser):
    """Simulates a user interacting with notification endpoints."""

    # Wait 1-3 seconds between requests
    wait_time = between(1, 3)

    # Authentication token
    token = None

    def on_start(self):
        """Called when a simulated user starts."""
        # Authenticate and get token
        self.token = self._get_auth_token()

    @task(3)  # Weight: 3 (most common operation)
    def list_notifications(self):
        """Get list of notifications."""
        headers = {'Authorization': f'Bearer {self.token}'}
        with self.client.get(
            "/api/notifications/",
            headers=headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")

    @task(2)  # Weight: 2
    def get_notification_detail(self):
        """Get single notification details."""
        headers = {'Authorization': f'Bearer {self.token}'}
        notification_id = randint(1, 1000)

        with self.client.get(
            f"/api/notifications/{notification_id}/",
            headers=headers,
            catch_response=True
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")

    @task(1)  # Weight: 1 (less common)
    def create_notification(self):
        """Create a new notification."""
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
        payload = {
            'recipient': f'user{randint(1, 1000)}@example.com',
            'message': 'Performance test notification',
            'type': 'email'
        }

        with self.client.post(
            "/api/notifications/",
            json=payload,
            headers=headers,
            catch_response=True
        ) as response:
            if response.status_code == 201:
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")

    @task(1)
    def mark_as_read(self):
        """Mark notification as read."""
        headers = {'Authorization': f'Bearer {self.token}'}
        notification_id = randint(1, 1000)

        with self.client.patch(
            f"/api/notifications/{notification_id}/read/",
            headers=headers,
            catch_response=True
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")

    def _get_auth_token(self):
        """Helper to get authentication token."""
        # Implementation depends on your auth setup
        # For testing, you might use a test token
        return "test-token"
```

### Testing Different Load Patterns

```python
"""Different load pattern tests."""

from locust import HttpUser, task, between, LoadTestShape


class ReadHeavyUser(HttpUser):
    """Simulates read-heavy workload (90% reads, 10% writes)."""

    wait_time = between(0.5, 2)

    @task(9)
    def read_operations(self):
        """Read operations."""
        self.client.get("/api/notifications/")

    @task(1)
    def write_operations(self):
        """Write operations."""
        self.client.post("/api/notifications/", json={
            'recipient': 'user@example.com',
            'message': 'Test',
            'type': 'email'
        })


class WriteHeavyUser(HttpUser):
    """Simulates write-heavy workload (70% writes, 30% reads)."""

    wait_time = between(0.5, 2)

    @task(3)
    def read_operations(self):
        """Read operations."""
        self.client.get("/api/notifications/")

    @task(7)
    def write_operations(self):
        """Write operations."""
        self.client.post("/api/notifications/", json={
            'recipient': 'user@example.com',
            'message': 'Test',
            'type': 'email'
        })


class CustomLoadShape(LoadTestShape):
    """Custom load pattern that ramps up and down.

    Simulates realistic traffic patterns:
    - Ramp up over 2 minutes to 100 users
    - Stay at 100 users for 3 minutes
    - Spike to 200 users for 1 minute
    - Ramp down over 2 minutes
    """

    stages = [
        {"duration": 120, "users": 100, "spawn_rate": 2},   # Ramp up
        {"duration": 300, "users": 100, "spawn_rate": 0},   # Steady state
        {"duration": 360, "users": 200, "spawn_rate": 10},  # Spike
        {"duration": 480, "users": 50, "spawn_rate": 5},    # Ramp down
    ]

    def tick(self):
        """Override to define custom load shape."""
        run_time = self.get_run_time()

        for stage in self.stages:
            if run_time < stage["duration"]:
                tick_data = (stage["users"], stage["spawn_rate"])
                return tick_data

        return None
```

### Testing Batch Operations

```python
"""Performance tests for batch operations."""

from locust import HttpUser, task, between


class BatchOperationUser(HttpUser):
    """Tests batch notification operations."""

    wait_time = between(2, 5)

    @task
    def send_batch_notifications(self):
        """Send batch of notifications."""
        # Small batch (10 notifications)
        batch = [
            {
                'recipient': f'user{i}@example.com',
                'message': f'Batch notification {i}',
                'type': 'email'
            }
            for i in range(10)
        ]

        with self.client.post(
            "/api/notifications/batch/",
            json={'notifications': batch},
            catch_response=True
        ) as response:
            if response.status_code == 201:
                # Verify response time is reasonable for batch
                if response.elapsed.total_seconds() < 2.0:
                    response.success()
                else:
                    response.failure("Batch took too long")
            else:
                response.failure(f"Got status code {response.status_code}")

    @task
    def large_batch(self):
        """Test larger batch operations."""
        # Large batch (100 notifications)
        batch = [
            {
                'recipient': f'user{i}@example.com',
                'message': f'Large batch {i}',
                'type': 'email'
            }
            for i in range(100)
        ]

        with self.client.post(
            "/api/notifications/batch/",
            json={'notifications': batch},
            catch_response=True
        ) as response:
            if response.status_code == 201:
                # More lenient timeout for large batch
                if response.elapsed.total_seconds() < 10.0:
                    response.success()
                else:
                    response.failure("Large batch took too long")
            else:
                response.failure(f"Got status code {response.status_code}")
```

### Stress Testing

```python
"""Stress tests to find breaking points."""

from locust import HttpUser, task, between, events


class StressTestUser(HttpUser):
    """Aggressive user for stress testing."""

    # Minimal wait time for maximum load
    wait_time = between(0.1, 0.5)

    @task
    def aggressive_requests(self):
        """Make rapid requests to stress the system."""
        self.client.get("/api/notifications/")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Monitor for degradation during stress test."""
    if exception:
        print(f"Request failed: {exception}")
    elif response_time > 5000:  # 5 seconds
        print(f"Slow response detected: {response_time}ms for {name}")


@events.quitting.add_listener
def on_quitting(environment, **kwargs):
    """Summary when test completes."""
    stats = environment.stats.total
    print(f"\nStress Test Summary:")
    print(f"Total requests: {stats.num_requests}")
    print(f"Failures: {stats.num_failures}")
    print(f"Failure rate: {stats.fail_ratio * 100:.2f}%")
    print(f"Average response time: {stats.avg_response_time:.2f}ms")
    print(f"Max response time: {stats.max_response_time:.2f}ms")
```

## Running Performance Tests

### Local Performance Testing

```bash
# Run performance tests locally
poetry run test-performance

# Run specific locustfile
poetry run locust -f tests/performance/locustfile_notifications.py --host=http://localhost:8000

# Run with web UI (access at http://localhost:8089)
poetry run locust -f tests/performance/locustfile_notifications.py --host=http://localhost:8000

# Run headless (no UI) with specific parameters
poetry run locust -f tests/performance/locustfile_notifications.py \
    --host=http://localhost:8000 \
    --users 100 \
    --spawn-rate 10 \
    --run-time 5m \
    --headless

# Run and generate HTML report
poetry run locust -f tests/performance/locustfile_notifications.py \
    --host=http://localhost:8000 \
    --users 100 \
    --spawn-rate 10 \
    --run-time 5m \
    --headless \
    --html=tests/performance/results/report.html
```

### CI/CD Performance Testing

```bash
# Run baseline performance test
poetry run locust -f tests/performance/locustfile_notifications.py \
    --host=https://staging.example.com \
    --users 50 \
    --spawn-rate 5 \
    --run-time 3m \
    --headless \
    --csv=tests/performance/results/baseline

# Run regression test (compare against baseline)
poetry run python tests/performance/compare_results.py \
    --baseline tests/performance/results/baseline \
    --current tests/performance/results/current
```

## Performance Test Scenarios

### 1. Baseline Test
Establish performance baseline with normal load.

```bash
poetry run locust -f tests/performance/locustfile_notifications.py \
    --host=http://localhost:8000 \
    --users 50 \
    --spawn-rate 5 \
    --run-time 10m \
    --headless \
    --csv=results/baseline/notifications
```

**Acceptance Criteria:**
- p95 response time < 500ms
- RPS > 100
- Error rate < 0.1%

### 2. Load Test
Test with expected production load.

```bash
poetry run locust -f tests/performance/locustfile_notifications.py \
    --host=http://localhost:8000 \
    --users 200 \
    --spawn-rate 10 \
    --run-time 15m \
    --headless
```

**Acceptance Criteria:**
- p95 response time < 800ms
- RPS > 300
- Error rate < 0.5%

### 3. Stress Test
Find breaking point by increasing load until failure.

```bash
poetry run locust -f tests/performance/locustfile_stress.py \
    --host=http://localhost:8000 \
    --users 1000 \
    --spawn-rate 50 \
    --run-time 10m \
    --headless
```

**Goal:** Identify maximum capacity and failure mode.

### 4. Spike Test
Test ability to handle sudden traffic spikes.

```bash
# Use custom load shape
poetry run locust -f tests/performance/locustfile_notifications.py \
    --host=http://localhost:8000 \
    --headless
```

**Acceptance Criteria:**
- System recovers after spike
- No cascading failures
- Error rate returns to normal after spike

### 5. Endurance Test
Test stability over extended period.

```bash
poetry run locust -f tests/performance/locustfile_notifications.py \
    --host=http://localhost:8000 \
    --users 100 \
    --spawn-rate 5 \
    --run-time 2h \
    --headless
```

**Goal:** Identify memory leaks, connection leaks, degradation over time.

## Performance Regression Detection

### Comparing Results

```python
"""Compare performance results to detect regressions."""

import csv
import sys


def load_stats(csv_path):
    """Load Locust stats from CSV."""
    stats = {}
    with open(f"{csv_path}_stats.csv", 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['Name'] != 'Aggregated':
                stats[row['Name']] = {
                    'avg_response_time': float(row['Average Response Time']),
                    'p95': float(row['95%']),
                    'p99': float(row['99%']),
                    'rps': float(row['Requests/s']),
                }
    return stats


def compare_stats(baseline, current, threshold=0.1):
    """Compare current stats against baseline.

    Args:
        baseline: Baseline stats dict
        current: Current stats dict
        threshold: Acceptable regression threshold (10% by default)

    Returns:
        dict with comparison results
    """
    regressions = []

    for endpoint, base_stats in baseline.items():
        if endpoint not in current:
            continue

        curr_stats = current[endpoint]

        # Check p95 regression
        p95_increase = (
            (curr_stats['p95'] - base_stats['p95']) / base_stats['p95']
        )
        if p95_increase > threshold:
            regressions.append({
                'endpoint': endpoint,
                'metric': 'p95',
                'baseline': base_stats['p95'],
                'current': curr_stats['p95'],
                'increase': f"{p95_increase * 100:.1f}%"
            })

    return regressions


if __name__ == '__main__':
    baseline = load_stats('results/baseline/notifications')
    current = load_stats('results/current/notifications')

    regressions = compare_stats(baseline, current)

    if regressions:
        print("Performance regressions detected:")
        for reg in regressions:
            print(f"  {reg['endpoint']} - {reg['metric']}: "
                  f"{reg['baseline']}ms -> {reg['current']}ms "
                  f"(+{reg['increase']})")
        sys.exit(1)
    else:
        print("No performance regressions detected")
        sys.exit(0)
```

## Monitoring During Tests

### Resource Monitoring Script

```python
"""Monitor system resources during performance test."""

import psutil
import time
import csv


def monitor_resources(duration_seconds=300, interval_seconds=5):
    """Monitor CPU, memory, and connections.

    Args:
        duration_seconds: How long to monitor
        interval_seconds: Sampling interval
    """
    with open('resource_usage.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'timestamp', 'cpu_percent', 'memory_percent',
            'memory_mb', 'connections'
        ])

        end_time = time.time() + duration_seconds

        while time.time() < end_time:
            cpu = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            connections = len(psutil.net_connections())

            writer.writerow([
                time.time(),
                cpu,
                memory.percent,
                memory.used / (1024 * 1024),  # MB
                connections
            ])

            time.sleep(interval_seconds)


if __name__ == '__main__':
    print("Monitoring resources...")
    monitor_resources(duration_seconds=600)  # 10 minutes
```

## Best Practices

### DO

- Establish baselines before making changes
- Test with realistic data and scenarios
- Monitor resource usage during tests
- Run tests in production-like environment
- Test all critical endpoints
- Use weighted tasks to simulate real usage
- Run performance tests regularly (nightly)
- Set and enforce performance budgets

### DON'T

- Test against production
- Run tests without warm-up period
- Ignore resource metrics
- Test only happy paths
- Use unrealistic data
- Skip regression testing
- Test with inadequate infrastructure
- Ignore outliers (p99, max response time)

## CI/CD Integration

Performance tests run automatically:

- **On Pull Request**: Quick smoke test (50 users, 2 minutes)
- **On Merge to Main**: Full baseline test
- **Nightly**: Complete test suite with all scenarios
- **Pre-release**: Extended endurance and stress tests

## Performance Optimization

When performance issues are detected:

1. **Identify bottleneck** - Use profiling tools
2. **Measure baseline** - Record current performance
3. **Optimize** - Make targeted improvements
4. **Re-test** - Verify improvement
5. **Compare** - Ensure no regressions elsewhere

## Related Documentation

- [Testing Overview](./TESTING.md)
- [Unit Testing](./UNIT-TESTING.md)
- [Component Testing](./COMPONENT-TESTING.md)
- [Dependency Testing](./DEPENDENCY-TESTING.md)
- [Locust Documentation](https://docs.locust.io/)
