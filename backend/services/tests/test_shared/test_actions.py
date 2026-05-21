"""
Tests for actions module - Strategy pattern implementation.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from dataclasses import dataclass

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from services.shared.actions import (
    ActionRegistry,
    BaseAction,
    ActionResult,
    ReindexDocumentsAction,
    IncreaseTopKAction,
    LowerConfidenceThresholdAction,
    IncreaseChunkOverlapAction,
    action_registry
)


class TestActionResult:
    """Tests for ActionResult dataclass."""
    
    def test_create_success(self):
        """Test creating successful action result."""
        result = ActionResult(
            success=True,
            message="Action completed successfully",
            data={"key": "value"}
        )
        
        assert result.success is True
        assert result.message == "Action completed successfully"
        assert result.data == {"key": "value"}
    
    def test_create_failure(self):
        """Test creating failed action result."""
        result = ActionResult(
            success=False,
            message="Action failed",
            error_code="VALIDATION_ERROR"
        )
        
        assert result.success is False
        assert result.error_code == "VALIDATION_ERROR"
    
    def test_to_dict(self):
        """Test converting result to dictionary."""
        result = ActionResult(
            success=True,
            message="Done",
            data={"items": [1, 2, 3]},
            error_code=None
        )
        
        data = result.to_dict()
        
        assert data["success"] is True
        assert data["message"] == "Done"
        assert data["data"]["items"] == [1, 2, 3]


class TestActionRegistry:
    """Tests for ActionRegistry class."""
    
    def test_register_action(self):
        """Test registering an action."""
        registry = ActionRegistry()
        
        @registry.register("test_action")
        class TestAction(BaseAction):
            def execute(self, *args, **kwargs):
                return ActionResult(success=True, message="Test")
            
            def validate(self, *args, **kwargs):
                return True
        
        assert "test_action" in registry.list_actions()
    
    def test_get_registered_action(self):
        """Test getting a registered action."""
        registry = ActionRegistry()
        
        @registry.register("my_action")
        class MyAction(BaseAction):
            def execute(self, *args, **kwargs):
                return ActionResult(success=True, message="My action")
            
            def validate(self, *args, **kwargs):
                return True
        
        action = registry.get("my_action")
        
        assert action is not None
        assert isinstance(action, MyAction)
    
    def test_get_unregistered_action(self):
        """Test getting an unregistered action returns None."""
        registry = ActionRegistry()
        
        action = registry.get("nonexistent_action")
        
        assert action is None
    
    def test_list_actions(self):
        """Test listing all registered actions."""
        registry = ActionRegistry(register_defaults=False)
        
        @registry.register("action_a")
        class ActionA(BaseAction):
            def execute(self, *args, **kwargs):
                pass
            def validate(self, *args, **kwargs):
                return True
        
        @registry.register("action_b")
        class ActionB(BaseAction):
            def execute(self, *args, **kwargs):
                pass
            def validate(self, *args, **kwargs):
                return True
        
        actions = registry.list_actions()
        
        assert "action_a" in actions
        assert "action_b" in actions
        assert len(actions) == 2
    
    def test_register_duplicate_action(self):
        """Test registering duplicate action overwrites."""
        registry = ActionRegistry()
        
        @registry.register("same_name")
        class FirstAction(BaseAction):
            def execute(self, *args, **kwargs):
                return ActionResult(success=True, message="First")
            def validate(self, *args, **kwargs):
                return True
        
        @registry.register("same_name")
        class SecondAction(BaseAction):
            def execute(self, *args, **kwargs):
                return ActionResult(success=True, message="Second")
            def validate(self, *args, **kwargs):
                return True
        
        action = registry.get("same_name")
        result = action.execute()
        
        assert result.message == "Second"


class TestReindexDocumentsAction:
    """Tests for ReindexDocumentsAction."""
    
    def test_validate_valid_input(self):
        """Test validation with valid input."""
        action = ReindexDocumentsAction()
        
        is_valid = action.validate(document_ids=[1, 2, 3])
        
        assert is_valid is True
    
    def test_validate_empty_document_ids(self):
        """Test validation with empty document IDs."""
        action = ReindexDocumentsAction()
        
        is_valid = action.validate(document_ids=[])
        
        assert is_valid is False
    
    def test_validate_missing_document_ids(self):
        """Test validation with missing document IDs."""
        action = ReindexDocumentsAction()
        
        is_valid = action.validate()
        
        assert is_valid is False
    
    def test_execute_mocked(self, mock_qdrant_client: MagicMock):
        """Test execution with mocked dependencies."""
        action = ReindexDocumentsAction()
        action.vector_store = mock_qdrant_client
        
        with patch.object(action, '_get_documents') as mock_get:
            mock_get.return_value = [
                {"id": 1, "text": "Document 1"},
                {"id": 2, "text": "Document 2"}
            ]
            
            result = action.execute(document_ids=[1, 2])
        
        assert result.success is True
        assert "reindexed" in result.message.lower()


class TestIncreaseTopKAction:
    """Tests for IncreaseTopKAction."""
    
    def test_validate_valid_increment(self):
        """Test validation with valid increment."""
        action = IncreaseTopKAction()
        
        is_valid = action.validate(current_top_k=3, increment=2)
        
        assert is_valid is True
    
    def test_validate_too_large_top_k(self):
        """Test validation rejects too large top_k."""
        action = IncreaseTopKAction(max_top_k=10)
        
        is_valid = action.validate(current_top_k=8, increment=5)
        
        assert is_valid is False
    
    def test_validate_negative_increment(self):
        """Test validation rejects negative increment."""
        action = IncreaseTopKAction()
        
        is_valid = action.validate(current_top_k=5, increment=-2)
        
        assert is_valid is False
    
    def test_execute_success(self):
        """Test successful execution."""
        action = IncreaseTopKAction()
        
        result = action.execute(current_top_k=3, increment=2)
        
        assert result.success is True
        assert result.data["new_top_k"] == 5
    
    def test_execute_caps_at_max(self):
        """Test execution caps at maximum."""
        action = IncreaseTopKAction(max_top_k=10)
        
        result = action.execute(current_top_k=8, increment=5)
        
        assert result.data["new_top_k"] == 10


class TestLowerConfidenceThresholdAction:
    """Tests for LowerConfidenceThresholdAction."""
    
    def test_validate_valid_decrement(self):
        """Test validation with valid decrement."""
        action = LowerConfidenceThresholdAction()
        
        is_valid = action.validate(current_threshold=0.7, decrement=0.1)
        
        assert is_valid is True
    
    def test_validate_below_minimum(self):
        """Test validation rejects below minimum."""
        action = LowerConfidenceThresholdAction(min_threshold=0.3)
        
        is_valid = action.validate(current_threshold=0.35, decrement=0.1)
        
        assert is_valid is False
    
    def test_validate_negative_decrement(self):
        """Test validation rejects negative decrement."""
        action = LowerConfidenceThresholdAction()
        
        is_valid = action.validate(current_threshold=0.7, decrement=-0.1)
        
        assert is_valid is False
    
    def test_execute_success(self):
        """Test successful execution."""
        action = LowerConfidenceThresholdAction()
        
        result = action.execute(current_threshold=0.7, decrement=0.1)
        
        assert result.success is True
        assert abs(result.data["new_threshold"] - 0.6) < 0.001
    
    def test_execute_clamps_at_minimum(self):
        """Test execution clamps at minimum threshold."""
        action = LowerConfidenceThresholdAction(min_threshold=0.3)
        
        result = action.execute(current_threshold=0.35, decrement=0.2)
        
        assert abs(result.data["new_threshold"] - 0.3) < 0.001


class TestIncreaseChunkOverlapAction:
    """Tests for IncreaseChunkOverlapAction."""
    
    def test_validate_valid_overlap(self):
        """Test validation with valid overlap."""
        action = IncreaseChunkOverlapAction()
        
        is_valid = action.validate(current_overlap=50, increment=25, chunk_size=500)
        
        assert is_valid is True
    
    def test_validate_overlap_exceeds_chunk_size(self):
        """Test validation rejects overlap exceeding chunk size."""
        action = IncreaseChunkOverlapAction()
        
        is_valid = action.validate(current_overlap=400, increment=200, chunk_size=500)
        
        assert is_valid is False
    
    def test_execute_success(self):
        """Test successful execution."""
        action = IncreaseChunkOverlapAction()
        
        result = action.execute(current_overlap=50, increment=25, chunk_size=500)
        
        assert result.success is True
        assert result.data["new_overlap"] == 75


class TestGlobalActionRegistry:
    """Tests for the global action registry."""
    
    def test_global_registry_exists(self):
        """Test global registry is available."""
        assert action_registry is not None
        assert isinstance(action_registry, ActionRegistry)
    
    def test_global_registry_has_default_actions(self):
        """Test global registry has default actions registered."""
        actions = action_registry.list_actions()
        
        # These should be registered by default
        assert "reindex_documents" in actions
        assert "increase_top_k" in actions
        assert "lower_confidence_threshold" in actions
        assert "increase_chunk_overlap" in actions


class TestBaseAction:
    """Tests for BaseAction abstract class."""
    
    def test_cannot_instantiate_directly(self):
        """Test BaseAction cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseAction()
    
    def test_subclass_must_implement_execute(self):
        """Test subclass must implement execute method."""
        with pytest.raises(TypeError):
            class IncompleteAction(BaseAction):
                def validate(self, *args, **kwargs):
                    return True
            
            IncompleteAction()
    
    def test_subclass_must_implement_validate(self):
        """Test subclass must implement validate method."""
        with pytest.raises(TypeError):
            class IncompleteAction(BaseAction):
                def execute(self, *args, **kwargs):
                    pass
            
            IncompleteAction()
    
    def test_complete_subclass_works(self):
        """Test complete subclass can be instantiated."""
        class CompleteAction(BaseAction):
            def execute(self, *args, **kwargs):
                return ActionResult(success=True, message="Done")
            
            def validate(self, *args, **kwargs):
                return True
        
        action = CompleteAction()
        result = action.execute()
        
        assert result.success is True
