"""
Workflow state persistence for Integration Hub.

Provides:
- Save and resume long-running operations
- State checkpointing
- Recovery from failures
"""

import logging
import json
import pickle
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class OperationState(Enum):
    """Operation states."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass
class WorkflowCheckpoint:
    """Workflow checkpoint data."""
    checkpoint_id: str
    workflow_id: str
    timestamp: str
    state: OperationState
    data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None


class WorkflowPersistence:
    """Manages workflow state persistence."""
    
    def __init__(self, storage_dir: str = "/tmp/integration_hub/workflows"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory cache
        self._cache: Dict[str, WorkflowCheckpoint] = {}
        
        logger.info(f"Workflow persistence initialized with storage directory: {self.storage_dir}")
    
    def save_checkpoint(
        self,
        workflow_id: str,
        state: OperationState,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Save a workflow checkpoint.
        
        Args:
            workflow_id: Workflow identifier
            state: Current operation state
            data: Workflow data to persist
            metadata: Optional metadata
        
        Returns:
            Checkpoint ID
        """
        checkpoint_id = f"{workflow_id}_{datetime.now().timestamp()}"
        
        checkpoint = WorkflowCheckpoint(
            checkpoint_id=checkpoint_id,
            workflow_id=workflow_id,
            timestamp=datetime.now().isoformat(),
            state=state,
            data=data,
            metadata=metadata
        )
        
        # Save to file
        checkpoint_file = self.storage_dir / f"{checkpoint_id}.json"
        try:
            with open(checkpoint_file, 'w') as f:
                json.dump(asdict(checkpoint), f, indent=2, default=str)
            
            # Update cache
            self._cache[checkpoint_id] = checkpoint
            
            logger.info(f"Saved checkpoint: {checkpoint_id} for workflow: {workflow_id}")
            return checkpoint_id
        
        except Exception as e:
            logger.error(f"Failed to save checkpoint {checkpoint_id}: {e}")
            raise
    
    def load_checkpoint(self, checkpoint_id: str) -> Optional[WorkflowCheckpoint]:
        """
        Load a workflow checkpoint.
        
        Args:
            checkpoint_id: Checkpoint identifier
        
        Returns:
            WorkflowCheckpoint or None if not found
        """
        # Check cache first
        if checkpoint_id in self._cache:
            return self._cache[checkpoint_id]
        
        # Load from file
        checkpoint_file = self.storage_dir / f"{checkpoint_id}.json"
        if not checkpoint_file.exists():
            logger.warning(f"Checkpoint file not found: {checkpoint_file}")
            return None
        
        try:
            with open(checkpoint_file, 'r') as f:
                data = json.load(f)
            
            checkpoint = WorkflowCheckpoint(
                checkpoint_id=data['checkpoint_id'],
                workflow_id=data['workflow_id'],
                timestamp=data['timestamp'],
                state=OperationState(data['state']),
                data=data['data'],
                metadata=data.get('metadata')
            )
            
            # Update cache
            self._cache[checkpoint_id] = checkpoint
            
            logger.info(f"Loaded checkpoint: {checkpoint_id}")
            return checkpoint
        
        except Exception as e:
            logger.error(f"Failed to load checkpoint {checkpoint_id}: {e}")
            return None
    
    def load_latest_checkpoint(self, workflow_id: str) -> Optional[WorkflowCheckpoint]:
        """
        Load the latest checkpoint for a workflow.
        
        Args:
            workflow_id: Workflow identifier
        
        Returns:
            Latest WorkflowCheckpoint or None if not found
        """
        # Find all checkpoints for this workflow
        checkpoints = []
        for checkpoint_file in self.storage_dir.glob(f"{workflow_id}_*.json"):
            try:
                with open(checkpoint_file, 'r') as f:
                    data = json.load(f)
                    checkpoints.append((data['timestamp'], checkpoint_file.stem))
            except Exception as e:
                logger.warning(f"Failed to read checkpoint file {checkpoint_file}: {e}")
        
        if not checkpoints:
            return None
        
        # Sort by timestamp (descending) and get the latest
        checkpoints.sort(key=lambda x: x[0], reverse=True)
        latest_checkpoint_id = checkpoints[0][1]
        
        return self.load_checkpoint(latest_checkpoint_id)
    
    def list_checkpoints(self, workflow_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List checkpoints.
        
        Args:
            workflow_id: Optional workflow ID to filter by
        
        Returns:
            List of checkpoint summaries
        """
        checkpoints = []
        
        for checkpoint_file in self.storage_dir.glob("*.json"):
            if workflow_id and not checkpoint_file.stem.startswith(workflow_id):
                continue
            
            try:
                with open(checkpoint_file, 'r') as f:
                    data = json.load(f)
                    checkpoints.append({
                        'checkpoint_id': data['checkpoint_id'],
                        'workflow_id': data['workflow_id'],
                        'timestamp': data['timestamp'],
                        'state': data['state']
                    })
            except Exception as e:
                logger.warning(f"Failed to read checkpoint file {checkpoint_file}: {e}")
        
        # Sort by timestamp (descending)
        checkpoints.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return checkpoints
    
    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """
        Delete a checkpoint.
        
        Args:
            checkpoint_id: Checkpoint identifier
        
        Returns:
            True if deleted, False otherwise
        """
        # Remove from cache
        if checkpoint_id in self._cache:
            del self._cache[checkpoint_id]
        
        # Delete file
        checkpoint_file = self.storage_dir / f"{checkpoint_id}.json"
        if checkpoint_file.exists():
            try:
                checkpoint_file.unlink()
                logger.info(f"Deleted checkpoint: {checkpoint_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete checkpoint {checkpoint_id}: {e}")
                return False
        
        return False
    
    def delete_workflow_checkpoints(self, workflow_id: str) -> int:
        """
        Delete all checkpoints for a workflow.
        
        Args:
            workflow_id: Workflow identifier
        
        Returns:
            Number of checkpoints deleted
        """
        deleted_count = 0
        
        for checkpoint_file in self.storage_dir.glob(f"{workflow_id}_*.json"):
            try:
                # Remove from cache
                checkpoint_id = checkpoint_file.stem
                if checkpoint_id in self._cache:
                    del self._cache[checkpoint_id]
                
                # Delete file
                checkpoint_file.unlink()
                deleted_count += 1
                logger.info(f"Deleted checkpoint: {checkpoint_id}")
            
            except Exception as e:
                logger.error(f"Failed to delete checkpoint {checkpoint_file}: {e}")
        
        logger.info(f"Deleted {deleted_count} checkpoints for workflow: {workflow_id}")
        return deleted_count
    
    def cleanup_old_checkpoints(self, max_age_hours: int = 24) -> int:
        """
        Clean up old checkpoints.
        
        Args:
            max_age_hours: Maximum age in hours
        
        Returns:
            Number of checkpoints deleted
        """
        deleted_count = 0
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
        
        for checkpoint_file in self.storage_dir.glob("*.json"):
            try:
                # Parse timestamp from checkpoint ID
                checkpoint_id = checkpoint_file.stem
                timestamp_str = checkpoint_id.split('_')[-1]
                timestamp = float(timestamp_str)
                
                if timestamp < cutoff_time:
                    # Remove from cache
                    if checkpoint_id in self._cache:
                        del self._cache[checkpoint_id]
                    
                    # Delete file
                    checkpoint_file.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted old checkpoint: {checkpoint_id}")
            
            except Exception as e:
                logger.warning(f"Failed to process checkpoint file {checkpoint_file}: {e}")
        
        logger.info(f"Cleaned up {deleted_count} old checkpoints")
        return deleted_count