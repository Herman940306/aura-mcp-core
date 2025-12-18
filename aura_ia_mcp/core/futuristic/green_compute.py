"""
Green Compute Module for Aura IA MCP.

This module implements carbon-aware job scheduling to reduce the environmental
impact of compute workloads by scheduling batch jobs during low carbon intensity
periods.

Features:
- Integration with carbon intensity APIs (Electricity Maps, WattTime)
- Intelligent job scheduling based on carbon forecasts
- Carbon budget tracking and reporting
- Location-aware scheduling (grid region optimization)
"""

from __future__ import annotations

import asyncio
import heapq
import logging
import os
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import total_ordering
from typing import Any

logger = logging.getLogger(__name__)


class JobPriority(Enum):
    """Job priority levels for scheduling."""

    CRITICAL = 0  # Must run immediately regardless of carbon
    HIGH = 1  # Run soon, slight delay acceptable
    NORMAL = 2  # Standard workload
    LOW = 3  # Can wait for optimal carbon window
    BACKGROUND = 4  # Only run during green windows


class JobState(Enum):
    """Job execution states."""

    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class CarbonIntensity:
    """Carbon intensity data point."""

    timestamp: datetime
    carbon_intensity: float  # gCO2eq/kWh
    grid_region: str
    renewable_percentage: float = 0.0
    forecast: bool = False
    source: str = "unknown"

    @property
    def is_green(self) -> bool:
        """Check if this is a 'green' period."""
        # <100 gCO2eq/kWh is considered green
        return self.carbon_intensity < 100

    @property
    def is_moderate(self) -> bool:
        """Check if this is a moderate carbon period."""
        return 100 <= self.carbon_intensity < 300

    @property
    def is_high(self) -> bool:
        """Check if this is a high carbon period."""
        return self.carbon_intensity >= 300

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "carbon_intensity": self.carbon_intensity,
            "grid_region": self.grid_region,
            "renewable_percentage": self.renewable_percentage,
            "forecast": self.forecast,
            "source": self.source,
            "classification": (
                "green"
                if self.is_green
                else ("moderate" if self.is_moderate else "high")
            ),
        }


@total_ordering
@dataclass
class ScheduledJob:
    """A job scheduled for carbon-aware execution."""

    id: str
    name: str
    func: Callable[..., Any]
    args: tuple = field(default_factory=tuple)
    kwargs: dict[str, Any] = field(default_factory=dict)

    # Scheduling constraints
    priority: JobPriority = JobPriority.NORMAL
    max_delay: timedelta = timedelta(hours=24)
    preferred_carbon_threshold: float = 150.0  # gCO2eq/kWh

    # Execution metadata
    state: JobState = JobState.PENDING
    scheduled_time: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: Any = None
    error: str | None = None

    # Carbon tracking
    carbon_intensity_at_execution: float | None = None
    carbon_saved_estimate: float = 0.0  # gCO2eq saved vs immediate execution

    def __lt__(self, other: ScheduledJob) -> bool:
        """Compare jobs for heap ordering."""
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        return (self.scheduled_time or datetime.max) < (
            other.scheduled_time or datetime.max
        )

    def __eq__(self, other: object) -> bool:
        """Check job equality."""
        if not isinstance(other, ScheduledJob):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        """Hash for set operations."""
        return hash(self.id)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (excluding callable)."""
        return {
            "id": self.id,
            "name": self.name,
            "priority": self.priority.name,
            "max_delay": str(self.max_delay),
            "preferred_carbon_threshold": self.preferred_carbon_threshold,
            "state": self.state.value,
            "scheduled_time": (
                self.scheduled_time.isoformat()
                if self.scheduled_time
                else None
            ),
            "started_at": (
                self.started_at.isoformat() if self.started_at else None
            ),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "error": self.error,
            "carbon_intensity_at_execution": self.carbon_intensity_at_execution,
            "carbon_saved_estimate": self.carbon_saved_estimate,
        }


class CarbonDataSource(ABC):
    """Abstract base class for carbon intensity data sources."""

    @abstractmethod
    async def get_current_intensity(self, region: str) -> CarbonIntensity:
        """Get current carbon intensity for a region."""
        pass

    @abstractmethod
    async def get_forecast(
        self, region: str, hours: int = 24
    ) -> list[CarbonIntensity]:
        """Get carbon intensity forecast."""
        pass

    @abstractmethod
    def get_supported_regions(self) -> list[str]:
        """Get list of supported regions."""
        pass


class ElectricityMapsSource(CarbonDataSource):
    """
    Carbon data from Electricity Maps API.

    https://www.electricitymaps.com/
    Provides real-time and forecast carbon intensity for many regions.
    """

    API_BASE = "https://api.electricitymap.org/v3"

    # Common regions
    REGIONS = {
        "US-CAL-CISO": "California ISO",
        "US-NY-NYIS": "New York ISO",
        "US-TEX-ERCO": "ERCOT (Texas)",
        "US-MIDA-PJM": "PJM (Mid-Atlantic)",
        "GB": "Great Britain",
        "DE": "Germany",
        "FR": "France",
        "ES": "Spain",
        "DK-DK1": "Denmark West",
        "NO-NO1": "Norway South",
        "SE-SE1": "Sweden North",
    }

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get(
            "ELECTRICITY_MAPS_API_KEY", ""
        )
        self._cache: dict[str, CarbonIntensity] = {}
        self._cache_ttl = timedelta(minutes=5)

    async def get_current_intensity(self, region: str) -> CarbonIntensity:
        """Get current carbon intensity."""
        # Check cache
        cache_key = f"current_{region}"
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if datetime.now() - cached.timestamp < self._cache_ttl:
                return cached

        # In production: Make API call
        # For now, return simulated data
        intensity = self._simulate_intensity(region, forecast=False)
        self._cache[cache_key] = intensity
        return intensity

    async def get_forecast(
        self, region: str, hours: int = 24
    ) -> list[CarbonIntensity]:
        """Get carbon intensity forecast."""
        # In production: Make API call to /carbon-intensity/forecast
        # For now, return simulated forecast
        forecast = []
        base_time = datetime.now()

        for i in range(hours):
            intensity = self._simulate_intensity(
                region,
                forecast=True,
                hours_offset=i,
            )
            intensity.timestamp = base_time + timedelta(hours=i)
            forecast.append(intensity)

        return forecast

    def get_supported_regions(self) -> list[str]:
        """Get supported regions."""
        return list(self.REGIONS.keys())

    def _simulate_intensity(
        self,
        region: str,
        forecast: bool = False,
        hours_offset: int = 0,
    ) -> CarbonIntensity:
        """Simulate carbon intensity for testing."""
        import math
        import random

        # Base intensity varies by region
        base_intensities = {
            "US-CAL-CISO": 200,
            "US-TEX-ERCO": 350,
            "GB": 180,
            "DE": 300,
            "FR": 50,  # Nuclear
            "NO-NO1": 20,  # Hydro
            "SE-SE1": 30,  # Hydro + Nuclear
        }
        base = base_intensities.get(region, 250)

        # Add time-of-day variation (solar effect)
        hour = (datetime.now().hour + hours_offset) % 24
        solar_factor = math.sin((hour - 6) * math.pi / 12) * 0.3
        if 6 <= hour <= 18:
            base *= 1 - solar_factor * 0.5  # Lower during daylight
        else:
            base *= 1 + 0.2  # Higher at night

        # Add some randomness
        variation = random.uniform(-30, 30)
        intensity = max(10, base + variation)

        # Estimate renewable percentage
        renewable = max(0, min(100, 100 - intensity * 0.3))

        return CarbonIntensity(
            timestamp=datetime.now(),
            carbon_intensity=round(intensity, 1),
            grid_region=region,
            renewable_percentage=round(renewable, 1),
            forecast=forecast,
            source="electricity_maps",
        )


class WattTimeSource(CarbonDataSource):
    """
    Carbon data from WattTime API.

    https://www.watttime.org/
    Provides real-time marginal emissions data for US grid regions.
    """

    API_BASE = "https://api2.watttime.org/v2"

    # US balancing authorities
    BALANCING_AUTHORITIES = {
        "CAISO_NORTH": "California ISO - North",
        "CAISO_SOUTH": "California ISO - South",
        "ERCOT": "Electric Reliability Council of Texas",
        "PJM": "PJM Interconnection",
        "MISO": "Midcontinent ISO",
        "NYISO": "New York ISO",
        "ISONE": "ISO New England",
        "SPP": "Southwest Power Pool",
    }

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
    ):
        self.username = username or os.environ.get("WATTTIME_USERNAME", "")
        self.password = password or os.environ.get("WATTTIME_PASSWORD", "")
        self._token: str | None = None
        self._token_expiry: datetime | None = None

    async def get_current_intensity(self, region: str) -> CarbonIntensity:
        """Get current carbon intensity (MOER - Marginal Operating Emissions Rate)."""
        # In production: Authenticate and call /index
        # For now, return simulated data
        return self._simulate_intensity(region)

    async def get_forecast(
        self, region: str, hours: int = 24
    ) -> list[CarbonIntensity]:
        """Get carbon intensity forecast."""
        # In production: Call /forecast
        forecast = []
        base_time = datetime.now()

        for i in range(hours):
            intensity = self._simulate_intensity(region, hours_offset=i)
            intensity.timestamp = base_time + timedelta(hours=i)
            intensity.forecast = True
            forecast.append(intensity)

        return forecast

    def get_supported_regions(self) -> list[str]:
        """Get supported balancing authorities."""
        return list(self.BALANCING_AUTHORITIES.keys())

    def _simulate_intensity(
        self,
        region: str,
        hours_offset: int = 0,
    ) -> CarbonIntensity:
        """Simulate MOER data for testing."""
        import random

        # MOER values in lbs CO2/MWh (convert to gCO2eq/kWh)
        base_moer = {
            "CAISO_NORTH": 400,
            "CAISO_SOUTH": 450,
            "ERCOT": 800,
            "PJM": 700,
            "MISO": 750,
            "NYISO": 500,
            "ISONE": 450,
        }
        base = base_moer.get(region, 600)

        # Time variation
        hour = (datetime.now().hour + hours_offset) % 24
        if 6 <= hour <= 18:
            base *= 0.85  # Lower during day (solar)

        # Randomness
        variation = random.uniform(-50, 50)
        moer_lbs_mwh = max(100, base + variation)

        # Convert lbs CO2/MWh to gCO2eq/kWh
        # 1 lb = 453.592 g, 1 MWh = 1000 kWh
        gco2_kwh = moer_lbs_mwh * 453.592 / 1000

        return CarbonIntensity(
            timestamp=datetime.now(),
            carbon_intensity=round(gco2_kwh, 1),
            grid_region=region,
            renewable_percentage=round(max(0, 60 - gco2_kwh / 10), 1),
            forecast=False,
            source="watttime",
        )


class CarbonBudget:
    """Track carbon budget for workloads."""

    def __init__(
        self,
        daily_budget_gco2: float = 10000.0,  # 10 kg CO2 daily budget
        monthly_budget_gco2: float = 250000.0,  # 250 kg CO2 monthly
    ):
        self.daily_budget = daily_budget_gco2
        self.monthly_budget = monthly_budget_gco2
        self._daily_usage: float = 0.0
        self._monthly_usage: float = 0.0
        self._last_daily_reset: datetime = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        self._last_monthly_reset: datetime = datetime.now().replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        self._lock = threading.RLock()  # RLock allows reentrant locking

    def record_usage(self, gco2: float) -> None:
        """Record carbon usage."""
        with self._lock:
            self._check_resets()
            self._daily_usage += gco2
            self._monthly_usage += gco2

    def _check_resets(self) -> None:
        """Check and perform daily/monthly resets."""
        now = datetime.now()

        # Daily reset
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if today > self._last_daily_reset:
            self._daily_usage = 0.0
            self._last_daily_reset = today

        # Monthly reset
        this_month = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        if this_month > self._last_monthly_reset:
            self._monthly_usage = 0.0
            self._last_monthly_reset = this_month

    @property
    def daily_remaining(self) -> float:
        """Get remaining daily budget."""
        with self._lock:
            self._check_resets()
            return max(0, self.daily_budget - self._daily_usage)

    @property
    def monthly_remaining(self) -> float:
        """Get remaining monthly budget."""
        with self._lock:
            self._check_resets()
            return max(0, self.monthly_budget - self._monthly_usage)

    @property
    def daily_usage_percentage(self) -> float:
        """Get daily usage as percentage."""
        return min(100, (self._daily_usage / self.daily_budget) * 100)

    @property
    def monthly_usage_percentage(self) -> float:
        """Get monthly usage as percentage."""
        return min(100, (self._monthly_usage / self.monthly_budget) * 100)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        with self._lock:
            self._check_resets()
            return {
                "daily": {
                    "budget": self.daily_budget,
                    "used": self._daily_usage,
                    "remaining": self.daily_remaining,
                    "percentage": self.daily_usage_percentage,
                },
                "monthly": {
                    "budget": self.monthly_budget,
                    "used": self._monthly_usage,
                    "remaining": self.monthly_remaining,
                    "percentage": self.monthly_usage_percentage,
                },
            }


class CarbonAwareScheduler:
    """
    Carbon-aware job scheduler for Aura IA.

    Schedules batch jobs to run during periods of low carbon intensity,
    reducing the environmental impact of compute workloads.

    Features:
    - Multiple carbon data sources (Electricity Maps, WattTime)
    - Priority-based scheduling
    - Carbon budget tracking
    - Deadline awareness (max_delay)
    - Optimal window detection
    """

    def __init__(
        self,
        region: str = "US-CAL-CISO",
        data_source: CarbonDataSource | None = None,
        budget: CarbonBudget | None = None,
    ):
        self.region = region
        self.data_source = data_source or ElectricityMapsSource()
        self.budget = budget or CarbonBudget()

        self._job_queue: list[ScheduledJob] = []  # Priority heap
        self._jobs: dict[str, ScheduledJob] = {}
        self._lock = threading.Lock()
        self._running = False
        self._scheduler_task: asyncio.Task | None = None

        # Statistics
        self._total_jobs: int = 0
        self._completed_jobs: int = 0
        self._total_carbon_saved: float = 0.0

    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            return

        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info(
            f"Carbon-aware scheduler started for region: {self.region}"
        )

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        logger.info("Carbon-aware scheduler stopped")

    def schedule(self, job: ScheduledJob) -> str:
        """Schedule a job for carbon-aware execution."""
        with self._lock:
            self._jobs[job.id] = job
            heapq.heappush(self._job_queue, job)
            self._total_jobs += 1

        logger.info(
            f"Scheduled job: {job.name} (priority={job.priority.name})"
        )
        return job.id

    def cancel(self, job_id: str) -> bool:
        """Cancel a scheduled job."""
        with self._lock:
            if job_id in self._jobs:
                job = self._jobs[job_id]
                if job.state in (JobState.PENDING, JobState.SCHEDULED):
                    job.state = JobState.CANCELLED
                    logger.info(f"Cancelled job: {job.name}")
                    return True
        return False

    def get_job(self, job_id: str) -> ScheduledJob | None:
        """Get job by ID."""
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(
        self,
        state: JobState | None = None,
    ) -> list[ScheduledJob]:
        """List jobs, optionally filtered by state."""
        with self._lock:
            jobs = list(self._jobs.values())
            if state:
                jobs = [j for j in jobs if j.state == state]
            return jobs

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                await self._process_jobs()
                await asyncio.sleep(60)  # Check every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(10)

    async def _process_jobs(self) -> None:
        """Process pending jobs."""
        # Get current carbon intensity
        current = await self.data_source.get_current_intensity(self.region)

        # Get forecast for optimal window detection
        forecast = await self.data_source.get_forecast(self.region, hours=24)

        with self._lock:
            jobs_to_run = []

            for job in list(self._job_queue):
                if job.state != JobState.PENDING:
                    continue

                # Check if job should run now
                should_run, reason = self._should_run_job(
                    job, current, forecast
                )

                if should_run:
                    job.state = JobState.SCHEDULED
                    job.scheduled_time = datetime.now()
                    jobs_to_run.append(job)

        # Execute jobs outside lock
        for job in jobs_to_run:
            await self._execute_job(job, current)

    def _should_run_job(
        self,
        job: ScheduledJob,
        current: CarbonIntensity,
        forecast: list[CarbonIntensity],
    ) -> tuple[bool, str]:
        """Determine if a job should run now."""
        # Critical priority always runs immediately
        if job.priority == JobPriority.CRITICAL:
            return True, "Critical priority"

        # Check deadline
        created_at = job.scheduled_time or datetime.now()
        deadline = created_at + job.max_delay
        time_remaining = deadline - datetime.now()

        if time_remaining <= timedelta(minutes=5):
            return True, "Deadline approaching"

        # Check if current carbon is below threshold
        if current.carbon_intensity <= job.preferred_carbon_threshold:
            return (
                True,
                f"Carbon below threshold ({current.carbon_intensity} <= {job.preferred_carbon_threshold})",
            )

        # For high priority, accept moderate carbon
        if job.priority == JobPriority.HIGH and current.is_moderate:
            return True, "High priority with moderate carbon"

        # Check if better window exists in forecast
        optimal_window = self._find_optimal_window(
            forecast,
            job.preferred_carbon_threshold,
            window_hours=4,
        )

        if optimal_window:
            # If optimal window is within deadline, wait
            window_start = optimal_window[0].timestamp
            if window_start < deadline:
                return False, f"Better window at {window_start}"

        # For background jobs, only run if green
        if job.priority == JobPriority.BACKGROUND:
            if current.is_green:
                return True, "Green window for background job"
            return False, "Waiting for green window"

        # Default: run if moderate or better
        if current.is_green or current.is_moderate:
            return True, "Acceptable carbon intensity"

        return False, "Waiting for lower carbon"

    def _find_optimal_window(
        self,
        forecast: list[CarbonIntensity],
        threshold: float,
        window_hours: int = 4,
    ) -> list[CarbonIntensity] | None:
        """Find optimal low-carbon window in forecast."""
        if not forecast:
            return None

        best_window = None
        best_avg = float("inf")

        for i in range(len(forecast) - window_hours + 1):
            window = forecast[i : i + window_hours]
            avg_intensity = sum(f.carbon_intensity for f in window) / len(
                window
            )

            if avg_intensity < threshold and avg_intensity < best_avg:
                best_window = window
                best_avg = avg_intensity

        return best_window

    async def _execute_job(
        self,
        job: ScheduledJob,
        carbon: CarbonIntensity,
    ) -> None:
        """Execute a job."""
        job.state = JobState.RUNNING
        job.started_at = datetime.now()
        job.carbon_intensity_at_execution = carbon.carbon_intensity

        logger.info(
            f"Executing job: {job.name} "
            f"(carbon={carbon.carbon_intensity} gCO2eq/kWh)"
        )

        try:
            # Execute the job function
            if asyncio.iscoroutinefunction(job.func):
                job.result = await job.func(*job.args, **job.kwargs)
            else:
                job.result = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: job.func(*job.args, **job.kwargs)
                )

            job.state = JobState.COMPLETED
            job.completed_at = datetime.now()

            # Calculate carbon savings (estimate)
            # Assume 1 minute runtime, 100W power draw
            runtime_hours = 1 / 60
            power_kw = 0.1
            kwh = runtime_hours * power_kw

            # Carbon used at current intensity
            carbon_used = kwh * carbon.carbon_intensity

            # Estimate carbon if run at average intensity (assume 300 gCO2eq/kWh)
            baseline = kwh * 300
            job.carbon_saved_estimate = max(0, baseline - carbon_used)

            self._total_carbon_saved += job.carbon_saved_estimate
            self._completed_jobs += 1

            # Record budget usage
            self.budget.record_usage(carbon_used)

            logger.info(
                f"Job completed: {job.name} "
                f"(carbon_saved={job.carbon_saved_estimate:.2f}g)"
            )

        except Exception as e:
            job.state = JobState.FAILED
            job.error = str(e)
            job.completed_at = datetime.now()
            logger.error(f"Job failed: {job.name} - {e}")

    async def get_current_carbon(self) -> CarbonIntensity:
        """Get current carbon intensity."""
        return await self.data_source.get_current_intensity(self.region)

    async def get_forecast(self, hours: int = 24) -> list[CarbonIntensity]:
        """Get carbon forecast."""
        return await self.data_source.get_forecast(self.region, hours)

    async def get_optimal_window(
        self,
        threshold: float = 150.0,
        hours: int = 24,
    ) -> dict[str, Any] | None:
        """Get the optimal low-carbon window in the next N hours."""
        forecast = await self.get_forecast(hours)
        window = self._find_optimal_window(forecast, threshold, window_hours=4)

        if window:
            return {
                "start": window[0].timestamp.isoformat(),
                "end": window[-1].timestamp.isoformat(),
                "avg_intensity": sum(f.carbon_intensity for f in window)
                / len(window),
                "min_intensity": min(f.carbon_intensity for f in window),
                "hours": len(window),
            }
        return None

    def get_statistics(self) -> dict[str, Any]:
        """Get scheduler statistics."""
        with self._lock:
            pending = sum(
                1 for j in self._jobs.values() if j.state == JobState.PENDING
            )
            running = sum(
                1 for j in self._jobs.values() if j.state == JobState.RUNNING
            )

            return {
                "region": self.region,
                "total_jobs": self._total_jobs,
                "completed_jobs": self._completed_jobs,
                "pending_jobs": pending,
                "running_jobs": running,
                "total_carbon_saved_g": round(self._total_carbon_saved, 2),
                "budget": self.budget.to_dict(),
            }


# Singleton instance
_carbon_scheduler: CarbonAwareScheduler | None = None


def get_carbon_scheduler(
    region: str = "US-CAL-CISO",
) -> CarbonAwareScheduler:
    """Get or create the singleton carbon scheduler."""
    global _carbon_scheduler
    if _carbon_scheduler is None:
        _carbon_scheduler = CarbonAwareScheduler(region=region)
    return _carbon_scheduler
