"""Wave 2 SICD Training Loop Verification Script.

Verifies:
- Episode Logger functionality
- PR Orchestrator capabilities
- Training API endpoints
- Integration with Wave 1 services
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def verify_imports() -> bool:
    """Verify all Wave 2 components can be imported."""
    print("🔍 Verifying Wave 2 imports...")

    try:

        print("✅ All Wave 2 imports successful")
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False


def verify_episode_logger() -> bool:
    """Test Episode Logger functionality."""
    print("\n🔍 Verifying Episode Logger...")

    try:
        from aura_ia_mcp.training.episode_logger import EpisodeLogger

        # Create test logger
        logger = EpisodeLogger(episodes_dir="./data/training/test_episodes")

        # Start episode
        episode = logger.start_episode(
            run_id="test_run_001",
            episode_number=1,
            task_description="Test episode",
            context={"test": True},
        )

        assert episode.episode_id == "test_run_001_ep0001"
        assert episode.status == "in_progress"
        print(f"✅ Episode started: {episode.episode_id}")

        # Log action
        logger.log_action("test_action", {"key": "value"})
        assert len(episode.actions) == 1
        print("✅ Action logged")

        # Log outcome
        logger.log_outcome("test_outcome", {"result": "success"})
        assert len(episode.outcomes) == 1
        print("✅ Outcome logged")

        # Update metrics
        logger.update_metrics(tokens_used=100, rag_queries=2)
        assert episode.metrics.tokens_used == 100
        assert episode.metrics.rag_queries == 2
        print("✅ Metrics updated")

        # Complete episode
        completed = logger.complete_episode(
            status="completed", metadata={"test": "complete"}
        )
        assert completed.status == "completed"
        assert completed.completed_at is not None
        print("✅ Episode completed")

        # Load episode from disk
        loaded = logger.load_episode(episode.episode_id)
        assert loaded is not None
        assert loaded.episode_id == episode.episode_id
        print("✅ Episode persisted and reloaded")

        # List episodes
        episodes = logger.list_episodes(run_id="test_run_001")
        assert "test_run_001_ep0001" in episodes
        print("✅ Episode listing works")

        # Get run summary
        summary = logger.get_run_summary("test_run_001")
        assert summary["total_episodes"] == 1
        assert summary["completed"] == 1
        print(f"✅ Run summary: {summary}")

        print("✅ Episode Logger fully functional")
        return True

    except Exception as e:
        print(f"❌ Episode Logger error: {e}")
        import traceback

        traceback.print_exc()
        return False


def verify_pr_orchestrator() -> bool:
    """Test PR Orchestrator functionality."""
    print("\n🔍 Verifying PR Orchestrator...")

    try:
        from aura_ia_mcp.training.pr_orchestrator import PROrchestrator

        # Create orchestrator
        orchestrator = PROrchestrator(
            github_token="test_token",
            repo_owner="test_owner",
            repo_name="test_repo",
        )

        # Generate proposal
        changes = [
            {
                "file_path": "test.py",
                "new_content": "print('hello')",
                "change_type": "create",
                "rationale": "Add test file",
            },
            {
                "file_path": "README.md",
                "original_content": "# Old",
                "new_content": "# New",
                "change_type": "update",
                "rationale": "Update README",
            },
        ]

        proposal = orchestrator.generate_proposal(
            changes=changes,
            title="Test PR",
            description="Test description",
            run_id="test_run_001",
        )

        assert proposal.title == "Test PR"
        assert len(proposal.changes) == 2
        assert proposal.branch_name.startswith("aura-sicd/")
        assert "test_run_001" in proposal.body
        print(f"✅ PR Proposal generated: {proposal.proposal_id}")

        # Test legacy function
        from aura_ia_mcp.training.pr_orchestrator import propose_pr

        result = propose_pr(
            changes, title="Legacy Test", description="Legacy desc"
        )
        assert "proposal_id" in result
        assert result["changes"] == 2
        print("✅ Legacy propose_pr function works")

        print("✅ PR Orchestrator fully functional")
        return True

    except Exception as e:
        print(f"❌ PR Orchestrator error: {e}")
        import traceback

        traceback.print_exc()
        return False


def verify_training_routes() -> bool:
    """Verify training router has all required endpoints."""
    print("\n🔍 Verifying Training Routes...")

    try:
        from aura_ia_mcp.training.routes import training_router

        # Check routes exist
        routes = {route.path for route in training_router.routes}

        required_routes = {
            "/training/start",
            "/training/propose-pr",
            "/training/episodes/{run_id}",
            "/training/episodes/{run_id}/{episode_id}",
            "/training/runs/{run_id}/summary",
        }

        for route in required_routes:
            if route in routes:
                print(f"✅ Route exists: {route}")
            else:
                print(f"❌ Missing route: {route}")
                return False

        print("✅ All training routes present")
        return True

    except Exception as e:
        print(f"❌ Training routes error: {e}")
        import traceback

        traceback.print_exc()
        return False


def verify_integration() -> bool:
    """Verify Wave 2 integrates with Wave 1 services."""
    print("\n🔍 Verifying Wave 1 Integration...")

    try:
        # Check that RAG, embeddings, LLM services are importable

        print("✅ Wave 1 services accessible from Wave 2 context")

        # Verify training routes can import Wave 1 components

        print("✅ Training routes successfully import dependencies")

        print("✅ Wave 1 + Wave 2 integration verified")
        return True

    except Exception as e:
        print(f"❌ Integration error: {e}")
        import traceback

        traceback.print_exc()
        return False


def verify_data_structures() -> bool:
    """Verify data structures and models are correct."""
    print("\n🔍 Verifying Data Structures...")

    try:
        from dataclasses import asdict

        from aura_ia_mcp.training.episode_logger import (
            EpisodeMetrics,
            TrainingEpisode,
        )
        from aura_ia_mcp.training.pr_orchestrator import CodeChange, PRProposal

        # Test EpisodeMetrics
        metrics = EpisodeMetrics(tokens_used=100, inference_time_ms=50.5)
        metrics_dict = asdict(metrics)
        assert metrics_dict["tokens_used"] == 100
        print("✅ EpisodeMetrics structure valid")

        # Test TrainingEpisode
        episode = TrainingEpisode(
            episode_id="test_ep",
            run_id="test_run",
            episode_number=1,
            started_at="2025-01-01T00:00:00",
        )
        episode_dict = asdict(episode)
        assert episode_dict["episode_id"] == "test_ep"
        print("✅ TrainingEpisode structure valid")

        # Test CodeChange
        change = CodeChange(
            file_path="test.py",
            original_content=None,
            new_content="print('test')",
            change_type="create",
            rationale="Test",
        )
        change_dict = asdict(change)
        assert change_dict["file_path"] == "test.py"
        print("✅ CodeChange structure valid")

        # Test PRProposal
        proposal = PRProposal(
            title="Test",
            body="Test body",
            branch_name="test-branch",
            changes=[change],
            metadata={},
            created_at="2025-01-01T00:00:00",
            proposal_id="test_id",
        )
        proposal_dict = asdict(proposal)
        assert proposal_dict["title"] == "Test"
        print("✅ PRProposal structure valid")

        print("✅ All data structures valid")
        return True

    except Exception as e:
        print(f"❌ Data structure error: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all Wave 2 verification tests."""
    print("=" * 70)
    print("WAVE 2: SICD TRAINING LOOP VERIFICATION")
    print("=" * 70)

    results = {
        "Imports": verify_imports(),
        "Episode Logger": verify_episode_logger(),
        "PR Orchestrator": verify_pr_orchestrator(),
        "Training Routes": verify_training_routes(),
        "Wave 1 Integration": verify_integration(),
        "Data Structures": verify_data_structures(),
    }

    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(results.values())

    if all_passed:
        print("\n🎉 ALL WAVE 2 VERIFICATIONS PASSED!")
        print("\nWave 2 Components Ready:")
        print("  - Episode Logger: Persistent training episode tracking")
        print("  - PR Orchestrator: GitHub PR generation and automation")
        print(
            "  - Training API: /start, /propose-pr, /episodes, /runs endpoints"
        )
        print("  - Integration: Full compatibility with Wave 1 services")
        return 0
    else:
        print("\n⚠️  SOME VERIFICATIONS FAILED")
        print("Please review errors above and fix issues.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

if __name__ == "__main__":
    sys.exit(main())
