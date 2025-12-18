"""
Aura IA Debate Scheduler

Manages scheduled debates:
- Cron-like scheduling (every 6 hours)
- Background task management
- Auto-selection of topics and models
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from .engine import get_debate_engine

logger = logging.getLogger(__name__)


class DebateScheduler:
    """Schedules and runs automated debates."""

    def __init__(self, interval_hours: int = 6):
        self.interval_hours = interval_hours
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._last_run: Optional[datetime] = None

    async def start(self) -> None:
        """Start the scheduler background task."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info(
            f"🕰️ Debate Scheduler started (Interval: {self.interval_hours}h)"
        )

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Debate Scheduler stopped")

    async def _scheduler_loop(self) -> None:
        """Main scheduling loop."""
        while self._running:
            try:
                # Calculate time to next run
                now = datetime.now()
                if self._last_run is None:
                    # First run: Wait 1 minute to let system stabilize, then run
                    next_run = now + timedelta(minutes=1)
                else:
                    next_run = self._last_run + timedelta(
                        hours=self.interval_hours
                    )

                wait_seconds = (next_run - now).total_seconds()

                if wait_seconds > 0:
                    logger.debug(
                        f"Next debate scheduled for {next_run.strftime('%H:%M:%S')}"
                    )
                    await asyncio.sleep(
                        min(60, wait_seconds)
                    )  # Check cancellation every 60s

                    # Re-check time
                    if datetime.now() < next_run:
                        continue

                # Run scheduled debate
                await self.run_scheduled_debate()
                self._last_run = datetime.now()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in debate scheduler: {e}")
                await asyncio.sleep(60)  # Retry delay

    async def run_scheduled_debate(self) -> None:
        """Execute a scheduled debate."""
        logger.info("🤖 Starting scheduled debate...")
        try:
            engine = await get_debate_engine()

            # Start debate with random topic/models (defaults)
            result = await engine.run_debate()

            logger.info(f"✅ Scheduled debate completed: {result.debate_id}")
            logger.info(f"   Topic: {result.topic}")
            logger.info(f"   Winner: {result.winner or 'Tie'}")

        except Exception as e:
            logger.error(f"❌ Scheduled debate failed: {e}")


# Singleton
_scheduler: Optional[DebateScheduler] = None


async def get_scheduler() -> DebateScheduler:
    """Get scheduler singleton."""
    global _scheduler
    if _scheduler is None:
        _scheduler = DebateScheduler()
    return _scheduler
