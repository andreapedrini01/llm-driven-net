"""ChatGPT API client for LLM Integration Module."""

import time
import logging
from typing import Optional, Dict, Any, Callable, List
from datetime import datetime, timedelta
from dataclasses import dataclass
import asyncio
from collections import deque

from openai import AsyncOpenAI, OpenAIError, RateLimitError, APITimeoutError, APIConnectionError
from pydantic import BaseModel

from src.config import get_settings
from src.utils.logging import chatgpt_usage_logger, set_correlation_id, get_correlation_id


logger = logging.getLogger(__name__)


@dataclass
class ChatGPTResponse:
    """Response from ChatGPT API."""
    content: str
    model: str
    tokens_used: int
    latency: float
    finish_reason: str
    timestamp: datetime


@dataclass
class RateLimitInfo:
    """Rate limit information."""
    remaining_requests: int
    reset_time: datetime
    is_throttled: bool


@dataclass
class BudgetAlert:
    """Budget alert information."""
    alert_type: str  # 'warning' or 'critical'
    current_cost: float
    threshold: float
    message: str
    timestamp: datetime


class ChatGPTConfig(BaseModel):
    """Configuration for ChatGPT API client."""
    api_key: str
    model: str = "gpt-4-turbo"
    max_tokens: int = 2000
    temperature: float = 0.1
    rate_limit_rpm: int = 60
    timeout: int = 30
    max_retries: int = 3
    budget_warning_threshold: float = 10.0  # USD
    budget_critical_threshold: float = 50.0  # USD
    max_queue_size: int = 100


class ChatGPTClient:
    """Client for interacting with ChatGPT API."""
    
    def __init__(self, config: Optional[ChatGPTConfig] = None):
        """Initialize ChatGPT client.
        
        Args:
            config: Configuration for the client. If None, uses settings from config.
        """
        settings = get_settings()
        
        if config is None:
            api_key = settings.openai_api_key
            if not api_key:
                raise ValueError("OpenAI API key not configured")
            
            config = ChatGPTConfig(
                api_key=api_key,
                model=settings.openai_model,
                max_tokens=settings.openai_max_tokens,
                temperature=settings.openai_temperature,
                timeout=30,
                max_retries=3
            )
        
        self.config = config
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            timeout=config.timeout,
            max_retries=0  # We handle retries manually
        )
        
        # Rate limiting tracking
        self._request_times: List[datetime] = []
        self._rate_limit_info = RateLimitInfo(
            remaining_requests=config.rate_limit_rpm,
            reset_time=datetime.now() + timedelta(minutes=1),
            is_throttled=False
        )
        
        # Request queue for rate limit management
        self._request_queue: deque = deque()
        self._queue_lock = asyncio.Lock()
        self._processing_queue = False
        
        # Health monitoring
        self._last_successful_request: Optional[datetime] = None
        self._consecutive_failures = 0
        self._total_requests = 0
        self._total_tokens = 0
        self._total_cost = 0.0
        
        # Budget tracking and alerts
        self._budget_alerts: List[BudgetAlert] = []
        self._warning_threshold_reached = False
        self._critical_threshold_reached = False
        self._alert_callbacks: List[Callable[[BudgetAlert], None]] = []
        
        logger.info(f"ChatGPT client initialized with model: {config.model}")
    
    async def generate_response(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        system_message: Optional[str] = None
    ) -> ChatGPTResponse:
        """Generate a response from ChatGPT API.
        
        Args:
            prompt: The user prompt to send to ChatGPT
            context: Optional context dictionary to include in the prompt
            system_message: Optional system message to set behavior
            
        Returns:
            ChatGPTResponse with the generated content and metadata
            
        Raises:
            OpenAIError: If API request fails after retries
        """
        start_time = time.time()
        request_id = get_correlation_id() or set_correlation_id()
        
        # Check rate limits before making request
        await self._check_rate_limit()
        
        # Build messages
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        # Add context to prompt if provided
        full_prompt = prompt
        if context:
            context_str = self._format_context(context)
            full_prompt = f"{context_str}\n\n{prompt}"
        
        messages.append({"role": "user", "content": full_prompt})
        
        # Estimate prompt tokens (rough estimate)
        estimated_prompt_tokens = len(full_prompt.split()) * 1.3
        
        # Log API request
        chatgpt_usage_logger.log_api_request(
            request_id=request_id,
            model=self.config.model,
            prompt_tokens=int(estimated_prompt_tokens),
            correlation_id=request_id
        )
        
        # Attempt request with retry logic
        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                response = await self._make_request(messages)
                
                # Track successful request
                self._last_successful_request = datetime.now()
                self._consecutive_failures = 0
                self._total_requests += 1
                
                latency = time.time() - start_time
                
                # Extract response data
                choice = response.choices[0]
                content = choice.message.content
                finish_reason = choice.finish_reason
                
                # Track token usage
                tokens_used = response.usage.total_tokens
                prompt_tokens = response.usage.prompt_tokens
                completion_tokens = response.usage.completion_tokens
                self._total_tokens += tokens_used
                
                # Estimate cost (approximate rates for GPT-4-turbo)
                cost = self._estimate_cost(prompt_tokens, completion_tokens)
                self._total_cost += cost
                
                # Log API response
                chatgpt_usage_logger.log_api_response(
                    request_id=request_id,
                    model=response.model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=tokens_used,
                    latency_ms=latency * 1000,
                    estimated_cost=cost,
                    success=True,
                    correlation_id=request_id,
                    finish_reason=finish_reason
                )
                
                # Check budget thresholds and trigger alerts
                self._check_budget_thresholds()
                
                logger.info(
                    f"ChatGPT request successful: {tokens_used} tokens, "
                    f"{latency:.2f}s latency, ${cost:.4f} cost"
                )
                
                return ChatGPTResponse(
                    content=content,
                    model=response.model,
                    tokens_used=tokens_used,
                    latency=latency,
                    finish_reason=finish_reason,
                    timestamp=datetime.now()
                )
                
            except RateLimitError as e:
                last_error = e
                self._consecutive_failures += 1
                wait_time = self._calculate_backoff(attempt)
                
                # Log rate limit error
                chatgpt_usage_logger.log_api_error(
                    request_id=request_id,
                    model=self.config.model,
                    error_type="RateLimitError",
                    error_message=str(e),
                    retry_attempt=attempt + 1,
                    correlation_id=request_id,
                    wait_time=wait_time
                )
                
                logger.warning(
                    f"Rate limit hit (attempt {attempt + 1}/{self.config.max_retries}), "
                    f"waiting {wait_time}s"
                )
                await asyncio.sleep(wait_time)
                
            except APITimeoutError as e:
                last_error = e
                self._consecutive_failures += 1
                wait_time = self._calculate_backoff(attempt)
                
                # Log timeout error
                chatgpt_usage_logger.log_api_error(
                    request_id=request_id,
                    model=self.config.model,
                    error_type="APITimeoutError",
                    error_message=str(e),
                    retry_attempt=attempt + 1,
                    correlation_id=request_id,
                    wait_time=wait_time
                )
                
                logger.warning(
                    f"Request timeout (attempt {attempt + 1}/{self.config.max_retries}), "
                    f"waiting {wait_time}s"
                )
                await asyncio.sleep(wait_time)
                
            except APIConnectionError as e:
                last_error = e
                self._consecutive_failures += 1
                wait_time = self._calculate_backoff(attempt)
                
                # Log connection error
                chatgpt_usage_logger.log_api_error(
                    request_id=request_id,
                    model=self.config.model,
                    error_type="APIConnectionError",
                    error_message=str(e),
                    retry_attempt=attempt + 1,
                    correlation_id=request_id,
                    wait_time=wait_time
                )
                
                logger.warning(
                    f"Connection error (attempt {attempt + 1}/{self.config.max_retries}), "
                    f"waiting {wait_time}s"
                )
                await asyncio.sleep(wait_time)
                
            except OpenAIError as e:
                last_error = e
                self._consecutive_failures += 1
                
                # Log general API error
                chatgpt_usage_logger.log_api_error(
                    request_id=request_id,
                    model=self.config.model,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    retry_attempt=attempt + 1,
                    correlation_id=request_id
                )
                
                logger.error(f"OpenAI API error: {str(e)}")
                # Don't retry on other errors
                break
        
        # All retries exhausted - log final failure
        chatgpt_usage_logger.log_api_response(
            request_id=request_id,
            model=self.config.model,
            prompt_tokens=int(estimated_prompt_tokens),
            completion_tokens=0,
            total_tokens=int(estimated_prompt_tokens),
            latency_ms=(time.time() - start_time) * 1000,
            estimated_cost=0.0,
            success=False,
            correlation_id=request_id,
            error=str(last_error)
        )
        
        logger.error(
            f"ChatGPT request failed after {self.config.max_retries} attempts: {last_error}"
        )
        raise last_error
    
    async def _make_request(self, messages: list) -> Any:
        """Make the actual API request.
        
        Args:
            messages: List of message dictionaries
            
        Returns:
            API response object
        """
        response = await self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature
        )
        return response
    
    async def _check_rate_limit(self) -> None:
        """Check and enforce rate limits."""
        now = datetime.now()
        
        # Remove requests older than 1 minute
        self._request_times = [
            t for t in self._request_times
            if now - t < timedelta(minutes=1)
        ]
        
        # Check if we're at the limit
        if len(self._request_times) >= self.config.rate_limit_rpm:
            # Calculate wait time until oldest request expires
            oldest = min(self._request_times)
            wait_until = oldest + timedelta(minutes=1)
            wait_seconds = (wait_until - now).total_seconds()
            
            if wait_seconds > 0:
                logger.warning(f"Rate limit reached, waiting {wait_seconds:.1f}s")
                self._rate_limit_info.is_throttled = True
                
                # Log rate limit status
                chatgpt_usage_logger.log_rate_limit(
                    model=self.config.model,
                    remaining_requests=0,
                    reset_time=wait_until,
                    is_throttled=True,
                    wait_seconds=wait_seconds
                )
                
                await asyncio.sleep(wait_seconds)
                self._rate_limit_info.is_throttled = False
        
        # Track this request
        self._request_times.append(now)
        self._rate_limit_info.remaining_requests = (
            self.config.rate_limit_rpm - len(self._request_times)
        )
        self._rate_limit_info.reset_time = now + timedelta(minutes=1)
        
        # Log rate limit status periodically
        if len(self._request_times) % 10 == 0:
            chatgpt_usage_logger.log_rate_limit(
                model=self.config.model,
                remaining_requests=self._rate_limit_info.remaining_requests,
                reset_time=self._rate_limit_info.reset_time,
                is_throttled=False
            )
    
    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff wait time.
        
        Args:
            attempt: Current attempt number (0-indexed)
            
        Returns:
            Wait time in seconds
        """
        base_wait = 1.0
        max_wait = 60.0
        wait_time = min(base_wait * (2 ** attempt), max_wait)
        return wait_time
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context dictionary into a string.
        
        Args:
            context: Context dictionary
            
        Returns:
            Formatted context string
        """
        lines = ["Context:"]
        for key, value in context.items():
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)
    
    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost of API request.
        
        Args:
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            
        Returns:
            Estimated cost in USD
        """
        # Approximate rates (as of 2024)
        rates = {
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015}
        }
        
        # Get rates for current model
        model_key = self.config.model
        if "gpt-4-turbo" in model_key:
            model_key = "gpt-4-turbo"
        elif "gpt-4" in model_key:
            model_key = "gpt-4"
        elif "gpt-3.5" in model_key:
            model_key = "gpt-3.5-turbo"
        else:
            model_key = "gpt-4-turbo"  # Default
        
        rate = rates.get(model_key, rates["gpt-4-turbo"])
        
        # Calculate cost (rates are per 1K tokens)
        input_cost = (prompt_tokens / 1000) * rate["input"]
        output_cost = (completion_tokens / 1000) * rate["output"]
        
        return input_cost + output_cost
    
    def _check_budget_thresholds(self) -> None:
        """Check if budget thresholds have been exceeded and trigger alerts."""
        # Check warning threshold
        if (not self._warning_threshold_reached and 
            self._total_cost >= self.config.budget_warning_threshold):
            self._warning_threshold_reached = True
            alert = BudgetAlert(
                alert_type="warning",
                current_cost=self._total_cost,
                threshold=self.config.budget_warning_threshold,
                message=f"Budget warning: ${self._total_cost:.2f} spent (threshold: ${self.config.budget_warning_threshold:.2f})",
                timestamp=datetime.now()
            )
            self._budget_alerts.append(alert)
            logger.warning(alert.message)
            
            # Log budget alert
            chatgpt_usage_logger.log_budget_alert(
                alert_type="warning",
                current_cost=self._total_cost,
                threshold=self.config.budget_warning_threshold,
                message=alert.message
            )
            
            self._trigger_alert_callbacks(alert)
        
        # Check critical threshold
        if (not self._critical_threshold_reached and 
            self._total_cost >= self.config.budget_critical_threshold):
            self._critical_threshold_reached = True
            alert = BudgetAlert(
                alert_type="critical",
                current_cost=self._total_cost,
                threshold=self.config.budget_critical_threshold,
                message=f"CRITICAL: Budget exceeded ${self._total_cost:.2f} (threshold: ${self.config.budget_critical_threshold:.2f})",
                timestamp=datetime.now()
            )
            self._budget_alerts.append(alert)
            logger.critical(alert.message)
            
            # Log budget alert
            chatgpt_usage_logger.log_budget_alert(
                alert_type="critical",
                current_cost=self._total_cost,
                threshold=self.config.budget_critical_threshold,
                message=alert.message
            )
            
            self._trigger_alert_callbacks(alert)
    
    def _trigger_alert_callbacks(self, alert: BudgetAlert) -> None:
        """Trigger all registered alert callbacks.
        
        Args:
            alert: The budget alert to send to callbacks
        """
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")
    
    def register_alert_callback(self, callback: Callable[[BudgetAlert], None]) -> None:
        """Register a callback to be called when budget alerts are triggered.
        
        Args:
            callback: Function to call with BudgetAlert when thresholds are exceeded
        """
        self._alert_callbacks.append(callback)
    
    async def enqueue_request(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        system_message: Optional[str] = None,
        priority: int = 0
    ) -> ChatGPTResponse:
        """Enqueue a request to be processed with rate limiting.
        
        This method adds the request to a queue and processes it when rate limits allow.
        Higher priority requests are processed first.
        
        Args:
            prompt: The user prompt to send to ChatGPT
            context: Optional context dictionary to include in the prompt
            system_message: Optional system message to set behavior
            priority: Priority level (higher = more important, default 0)
            
        Returns:
            ChatGPTResponse with the generated content and metadata
            
        Raises:
            ValueError: If queue is full
            OpenAIError: If API request fails after retries
        """
        async with self._queue_lock:
            if len(self._request_queue) >= self.config.max_queue_size:
                raise ValueError(f"Request queue is full (max: {self.config.max_queue_size})")
            
            # Create a future to return the result
            future = asyncio.Future()
            
            # Add to queue with priority
            self._request_queue.append({
                'future': future,
                'prompt': prompt,
                'context': context,
                'system_message': system_message,
                'priority': priority,
                'enqueued_at': datetime.now()
            })
            
            # Sort queue by priority (higher first)
            self._request_queue = deque(
                sorted(self._request_queue, key=lambda x: x['priority'], reverse=True)
            )
            
            logger.info(f"Request enqueued (priority: {priority}, queue size: {len(self._request_queue)})")
        
        # Start processing queue if not already running
        if not self._processing_queue:
            asyncio.create_task(self._process_queue())
        
        # Wait for result
        return await future
    
    async def _process_queue(self) -> None:
        """Process queued requests with rate limiting."""
        if self._processing_queue:
            return
        
        self._processing_queue = True
        
        try:
            while True:
                async with self._queue_lock:
                    if not self._request_queue:
                        break
                    
                    request = self._request_queue.popleft()
                
                try:
                    # Process the request
                    response = await self.generate_response(
                        prompt=request['prompt'],
                        context=request['context'],
                        system_message=request['system_message']
                    )
                    
                    # Set the result
                    if not request['future'].done():
                        request['future'].set_result(response)
                    
                    wait_time = (datetime.now() - request['enqueued_at']).total_seconds()
                    logger.info(f"Queued request processed (waited: {wait_time:.1f}s)")
                    
                except Exception as e:
                    # Set the exception
                    if not request['future'].done():
                        request['future'].set_exception(e)
                    logger.error(f"Error processing queued request: {e}")
        
        finally:
            self._processing_queue = False
    
    def get_queue_size(self) -> int:
        """Get current size of the request queue.
        
        Returns:
            Number of requests in queue
        """
        return len(self._request_queue)
    
    def get_budget_alerts(self) -> List[BudgetAlert]:
        """Get all budget alerts that have been triggered.
        
        Returns:
            List of BudgetAlert objects
        """
        return self._budget_alerts.copy()
    
    def reset_budget_tracking(self) -> None:
        """Reset budget tracking counters and alerts.
        
        This should be called at the start of a new billing period.
        """
        self._total_cost = 0.0
        self._total_tokens = 0
        self._budget_alerts.clear()
        self._warning_threshold_reached = False
        self._critical_threshold_reached = False
        logger.info("Budget tracking reset")
    
    def is_available(self) -> bool:
        """Check if the API is available.
        
        Returns:
            True if API is likely available, False otherwise
        """
        # Consider unavailable if too many consecutive failures
        if self._consecutive_failures >= 5:
            return False
        
        # Consider unavailable if last successful request was too long ago
        if self._last_successful_request:
            time_since_success = datetime.now() - self._last_successful_request
            if time_since_success > timedelta(minutes=5):
                return False
        
        return True
    
    def get_latency(self) -> float:
        """Get average latency of recent requests.
        
        Returns:
            Average latency in seconds, or 0 if no data
        """
        # This is a simplified version
        # In production, you'd track latencies in a rolling window
        return 0.0
    
    def get_rate_limit_status(self) -> RateLimitInfo:
        """Get current rate limit status.
        
        Returns:
            RateLimitInfo with current status
        """
        return self._rate_limit_info
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics.
        
        Returns:
            Dictionary with usage statistics
        """
        return {
            "total_requests": self._total_requests,
            "total_tokens": self._total_tokens,
            "total_cost": self._total_cost,
            "consecutive_failures": self._consecutive_failures,
            "last_successful_request": self._last_successful_request,
            "is_available": self.is_available(),
            "queue_size": self.get_queue_size(),
            "budget_alerts": len(self._budget_alerts),
            "warning_threshold_reached": self._warning_threshold_reached,
            "critical_threshold_reached": self._critical_threshold_reached,
            "rate_limit_info": {
                "remaining_requests": self._rate_limit_info.remaining_requests,
                "reset_time": self._rate_limit_info.reset_time,
                "is_throttled": self._rate_limit_info.is_throttled
            }
        }
