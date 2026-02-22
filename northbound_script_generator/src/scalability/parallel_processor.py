"""Parallel processing for multiple network actions."""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from src.models.action_models import NetworkAction


class ProcessingMode(str, Enum):
    """Processing modes for parallel execution."""
    SEQUENTIAL = "sequential"
    THREADED = "threaded"
    PROCESS = "process"
    ASYNC = "async"


@dataclass
class ProcessingResult:
    """Result of processing an action."""
    action_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    worker_id: Optional[str] = None


class ParallelActionProcessor:
    """
    Parallel processor for network actions.
    
    Features:
    - Multiple processing modes (threaded, process, async)
    - Configurable worker pool size
    - Error handling and retry
    - Progress tracking
    - Performance metrics
    """
    
    def __init__(
        self,
        mode: ProcessingMode = ProcessingMode.THREADED,
        max_workers: int = 10,
        timeout_per_action: float = 300.0
    ):
        self.logger = logging.getLogger("ParallelActionProcessor")
        self.mode = mode
        self.max_workers = max_workers
        self.timeout_per_action = timeout_per_action
        
        # Executor
        self.executor: Optional[Any] = None
        
        # Statistics
        self.stats = {
            "total_processed": 0,
            "successful": 0,
            "failed": 0,
            "total_time": 0.0,
            "avg_time_per_action": 0.0,
            "max_time": 0.0,
            "min_time": float('inf')
        }
        
        self.logger.info(f"ParallelActionProcessor initialized with mode: {mode}")
    
    def _create_executor(self):
        """Create executor based on processing mode."""
        if self.mode == ProcessingMode.THREADED:
            return ThreadPoolExecutor(max_workers=self.max_workers)
        elif self.mode == ProcessingMode.PROCESS:
            return ProcessPoolExecutor(max_workers=self.max_workers)
        else:
            return None
    
    def process_actions(
        self,
        actions: List[NetworkAction],
        processor: Callable[[NetworkAction], Any],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[ProcessingResult]:
        """
        Process multiple actions in parallel.
        
        Args:
            actions: List of actions to process
            processor: Function to process each action
            progress_callback: Optional callback for progress updates (completed, total)
        
        Returns:
            List of processing results
        """
        if not actions:
            return []
        
        start_time = time.time()
        
        if self.mode == ProcessingMode.SEQUENTIAL:
            results = self._process_sequential(actions, processor, progress_callback)
        elif self.mode == ProcessingMode.ASYNC:
            results = self._process_async(actions, processor, progress_callback)
        else:
            results = self._process_parallel(actions, processor, progress_callback)
        
        total_time = time.time() - start_time
        
        # Update statistics
        self._update_stats(results, total_time)
        
        self.logger.info(
            f"Processed {len(actions)} actions in {total_time:.2f}s "
            f"({len([r for r in results if r.success])} successful)"
        )
        
        return results
    
    def _process_sequential(
        self,
        actions: List[NetworkAction],
        processor: Callable[[NetworkAction], Any],
        progress_callback: Optional[Callable[[int, int], None]]
    ) -> List[ProcessingResult]:
        """Process actions sequentially."""
        results = []
        
        for i, action in enumerate(actions):
            result = self._process_single_action(action, processor)
            results.append(result)
            
            if progress_callback:
                progress_callback(i + 1, len(actions))
        
        return results
    
    def _process_parallel(
        self,
        actions: List[NetworkAction],
        processor: Callable[[NetworkAction], Any],
        progress_callback: Optional[Callable[[int, int], None]]
    ) -> List[ProcessingResult]:
        """Process actions in parallel using thread/process pool."""
        results = []
        completed = 0
        
        with self._create_executor() as executor:
            # Submit all tasks
            future_to_action = {
                executor.submit(self._process_single_action, action, processor): action
                for action in actions
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_action, timeout=self.timeout_per_action * len(actions)):
                try:
                    result = future.result(timeout=self.timeout_per_action)
                    results.append(result)
                    completed += 1
                    
                    if progress_callback:
                        progress_callback(completed, len(actions))
                
                except Exception as e:
                    action = future_to_action[future]
                    self.logger.error(f"Error processing action {action.id}: {e}")
                    
                    results.append(ProcessingResult(
                        action_id=action.id,
                        success=False,
                        error=str(e)
                    ))
                    completed += 1
                    
                    if progress_callback:
                        progress_callback(completed, len(actions))
        
        return results
    
    def _process_async(
        self,
        actions: List[NetworkAction],
        processor: Callable[[NetworkAction], Any],
        progress_callback: Optional[Callable[[int, int], None]]
    ) -> List[ProcessingResult]:
        """Process actions asynchronously."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self._process_async_impl(actions, processor, progress_callback)
        )
    
    async def _process_async_impl(
        self,
        actions: List[NetworkAction],
        processor: Callable[[NetworkAction], Any],
        progress_callback: Optional[Callable[[int, int], None]]
    ) -> List[ProcessingResult]:
        """Async implementation of action processing."""
        tasks = []
        
        for action in actions:
            task = asyncio.create_task(
                self._process_single_action_async(action, processor)
            )
            tasks.append(task)
        
        results = []
        completed = 0
        
        for coro in asyncio.as_completed(tasks):
            try:
                result = await coro
                results.append(result)
                completed += 1
                
                if progress_callback:
                    progress_callback(completed, len(actions))
            
            except Exception as e:
                self.logger.error(f"Error in async processing: {e}")
                completed += 1
                
                if progress_callback:
                    progress_callback(completed, len(actions))
        
        return results
    
    def _process_single_action(
        self,
        action: NetworkAction,
        processor: Callable[[NetworkAction], Any]
    ) -> ProcessingResult:
        """Process a single action."""
        start_time = time.time()
        
        try:
            result = processor(action)
            execution_time = time.time() - start_time
            
            return ProcessingResult(
                action_id=action.id,
                success=True,
                result=result,
                execution_time=execution_time
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            
            self.logger.error(f"Error processing action {action.id}: {e}")
            
            return ProcessingResult(
                action_id=action.id,
                success=False,
                error=str(e),
                execution_time=execution_time
            )
    
    async def _process_single_action_async(
        self,
        action: NetworkAction,
        processor: Callable[[NetworkAction], Any]
    ) -> ProcessingResult:
        """Process a single action asynchronously."""
        start_time = time.time()
        
        try:
            # Run processor in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, processor, action)
            
            execution_time = time.time() - start_time
            
            return ProcessingResult(
                action_id=action.id,
                success=True,
                result=result,
                execution_time=execution_time
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            
            self.logger.error(f"Error processing action {action.id}: {e}")
            
            return ProcessingResult(
                action_id=action.id,
                success=False,
                error=str(e),
                execution_time=execution_time
            )
    
    def _update_stats(self, results: List[ProcessingResult], total_time: float):
        """Update processing statistics."""
        self.stats["total_processed"] += len(results)
        self.stats["successful"] += sum(1 for r in results if r.success)
        self.stats["failed"] += sum(1 for r in results if not r.success)
        self.stats["total_time"] += total_time
        
        if results:
            execution_times = [r.execution_time for r in results if r.execution_time > 0]
            
            if execution_times:
                self.stats["avg_time_per_action"] = sum(execution_times) / len(execution_times)
                self.stats["max_time"] = max(self.stats["max_time"], max(execution_times))
                self.stats["min_time"] = min(self.stats["min_time"], min(execution_times))
    
    def process_batch_with_priority(
        self,
        actions: List[NetworkAction],
        processor: Callable[[NetworkAction], Any],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[ProcessingResult]:
        """
        Process actions with priority ordering.
        
        Higher priority actions are processed first.
        
        Args:
            actions: List of actions to process
            processor: Function to process each action
            progress_callback: Optional callback for progress updates
        
        Returns:
            List of processing results
        """
        # Sort by priority (higher priority first)
        sorted_actions = sorted(actions, key=lambda a: a.priority, reverse=True)
        
        return self.process_actions(sorted_actions, processor, progress_callback)
    
    def process_with_dependencies(
        self,
        actions: List[NetworkAction],
        processor: Callable[[NetworkAction], Any],
        dependencies: Dict[str, List[str]],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[ProcessingResult]:
        """
        Process actions respecting dependencies.
        
        Args:
            actions: List of actions to process
            processor: Function to process each action
            dependencies: Dict mapping action_id to list of dependency action_ids
            progress_callback: Optional callback for progress updates
        
        Returns:
            List of processing results
        """
        results = []
        completed_actions = set()
        remaining_actions = {action.id: action for action in actions}
        
        total = len(actions)
        completed = 0
        
        while remaining_actions:
            # Find actions with satisfied dependencies
            ready_actions = []
            
            for action_id, action in remaining_actions.items():
                deps = dependencies.get(action_id, [])
                
                if all(dep in completed_actions for dep in deps):
                    ready_actions.append(action)
            
            if not ready_actions:
                # Circular dependency or missing dependency
                self.logger.error("Circular dependency or missing dependency detected")
                
                # Process remaining actions anyway
                ready_actions = list(remaining_actions.values())
            
            # Process ready actions
            batch_results = self.process_actions(ready_actions, processor)
            results.extend(batch_results)
            
            # Update completed actions
            for result in batch_results:
                if result.success:
                    completed_actions.add(result.action_id)
                
                if result.action_id in remaining_actions:
                    del remaining_actions[result.action_id]
                
                completed += 1
                
                if progress_callback:
                    progress_callback(completed, total)
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        stats = self.stats.copy()
        
        if stats["min_time"] == float('inf'):
            stats["min_time"] = 0.0
        
        return {
            "mode": self.mode.value,
            "max_workers": self.max_workers,
            **stats
        }
    
    def reset_stats(self):
        """Reset processing statistics."""
        self.stats = {
            "total_processed": 0,
            "successful": 0,
            "failed": 0,
            "total_time": 0.0,
            "avg_time_per_action": 0.0,
            "max_time": 0.0,
            "min_time": float('inf')
        }
        
        self.logger.info("Reset processing statistics")
