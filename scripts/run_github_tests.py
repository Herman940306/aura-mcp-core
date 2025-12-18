"""Simple runner for GitHub integration tests with timeout.

Project Creator: Herman Swanepoel
"""

import asyncio
import os
import sys

# Add tests and src to path
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../tests"))
)
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))
)


async def run_with_timeout():
    """Run tests with a timeout."""
    try:
        # Import and run the test
        from test_github_integration_tools import main as test_main

        # Run with 60 second timeout
        exit_code = await asyncio.wait_for(test_main(), timeout=60.0)
        return exit_code
    except TimeoutError:
        print("\n⚠ Tests timed out after 60 seconds")
        print("This may indicate GitHub API rate limiting or network issues")
        return 1
    except Exception as e:
        print(f"\n✗ Test execution failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_with_timeout())
    sys.exit(exit_code)
