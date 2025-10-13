"""Tool execution approval management (human-in-the-loop)."""

import asyncio
import logging
from typing import Dict, Optional, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ApprovalRequest:
    """Represents a pending tool execution approval request."""

    def __init__(self, request_id: str, session_id: str, tool_calls: list):
        self.request_id = request_id
        self.session_id = session_id
        self.tool_calls = tool_calls
        self.created_at = datetime.utcnow()
        self.status = "pending"  # pending, approved, rejected, timeout
        self.approved_tools: list = []
        self.rejected_tools: list = []
        self._event = asyncio.Event()

    async def wait_for_decision(self, timeout: int = 300) -> str:
        """
        Wait for user approval/rejection decision.

        Args:
            timeout: Maximum time to wait in seconds (default: 5 minutes)

        Returns:
            Status: "approved", "rejected", or "timeout"
        """
        try:
            await asyncio.wait_for(self._event.wait(), timeout=timeout)
            return self.status
        except asyncio.TimeoutError:
            self.status = "timeout"
            logger.warning(f"Approval request {self.request_id} timed out after {timeout}s")
            return "timeout"

    def approve(self, tool_ids: Optional[list] = None):
        """
        Approve tool execution.

        Args:
            tool_ids: List of specific tool IDs to approve (None = approve all)
        """
        if tool_ids is None:
            # Approve all tools
            self.approved_tools = [tc["id"] for tc in self.tool_calls]
        else:
            self.approved_tools = tool_ids

        self.status = "approved"
        self._event.set()
        logger.info(f"Approval request {self.request_id} approved ({len(self.approved_tools)} tools)")

    def reject(self, tool_ids: Optional[list] = None, reason: Optional[str] = None):
        """
        Reject tool execution.

        Args:
            tool_ids: List of specific tool IDs to reject (None = reject all)
            reason: Optional rejection reason
        """
        if tool_ids is None:
            # Reject all tools
            self.rejected_tools = [tc["id"] for tc in self.tool_calls]
        else:
            self.rejected_tools = tool_ids

        self.status = "rejected"
        self._event.set()
        logger.info(f"Approval request {self.request_id} rejected ({len(self.rejected_tools)} tools)")

    def is_tool_approved(self, tool_id: str) -> bool:
        """Check if a specific tool was approved."""
        return tool_id in self.approved_tools

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "status": self.status,
            "tool_calls": self.tool_calls,
            "created_at": self.created_at.isoformat(),
            "approved_tools": self.approved_tools,
            "rejected_tools": self.rejected_tools
        }


class ApprovalManager:
    """Manages tool execution approval requests across sessions."""

    def __init__(self, cleanup_interval: int = 600):
        """
        Initialize approval manager.

        Args:
            cleanup_interval: Interval for cleaning up expired requests (seconds)
        """
        self._requests: Dict[str, ApprovalRequest] = {}
        self._cleanup_interval = cleanup_interval
        self._cleanup_task: Optional[asyncio.Task] = None

    def start_cleanup_task(self):
        """Start background task to clean up expired requests."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Approval manager cleanup task started")

    async def _cleanup_loop(self):
        """Background task to periodically clean up expired requests."""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup task error: {e}")

    def _cleanup_expired(self):
        """Remove expired approval requests (older than 10 minutes)."""
        cutoff_time = datetime.utcnow() - timedelta(minutes=10)
        expired_ids = [
            req_id for req_id, req in self._requests.items()
            if req.created_at < cutoff_time
        ]

        for req_id in expired_ids:
            del self._requests[req_id]

        if expired_ids:
            logger.info(f"Cleaned up {len(expired_ids)} expired approval requests")

    def create_request(self, request_id: str, session_id: str, tool_calls: list) -> ApprovalRequest:
        """
        Create a new approval request.

        Args:
            request_id: Unique request identifier
            session_id: Session identifier
            tool_calls: List of tool calls to approve

        Returns:
            ApprovalRequest object
        """
        request = ApprovalRequest(request_id, session_id, tool_calls)
        self._requests[request_id] = request
        logger.info(f"Created approval request {request_id} for session {session_id} ({len(tool_calls)} tools)")
        return request

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get an approval request by ID."""
        return self._requests.get(request_id)

    def remove_request(self, request_id: str):
        """Remove an approval request."""
        if request_id in self._requests:
            del self._requests[request_id]
            logger.debug(f"Removed approval request {request_id}")

    def get_pending_requests(self, session_id: Optional[str] = None) -> list:
        """
        Get all pending requests, optionally filtered by session.

        Args:
            session_id: Optional session ID filter

        Returns:
            List of pending ApprovalRequest objects
        """
        requests = [
            req for req in self._requests.values()
            if req.status == "pending"
        ]

        if session_id:
            requests = [req for req in requests if req.session_id == session_id]

        return requests

    async def stop_cleanup_task(self):
        """Stop the cleanup background task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("Approval manager cleanup task stopped")


# Global approval manager instance
_approval_manager: Optional[ApprovalManager] = None


def get_approval_manager() -> ApprovalManager:
    """Get or create the global approval manager instance."""
    global _approval_manager
    if _approval_manager is None:
        _approval_manager = ApprovalManager()
        _approval_manager.start_cleanup_task()
    return _approval_manager
