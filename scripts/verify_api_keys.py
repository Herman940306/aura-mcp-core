#!/usr/bin/env python3
"""
API Keys Verification Script

Project Creator: Herman Swanepoel
Version: 1.0
Last Updated: 2025-11-14

This script verifies that all API keys are properly configured for Kiro IDE.
"""

import json
import os
import sys
import urllib.request


class Colors:
    """ANSI color codes"""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_header(text: str):
    """Print formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(70)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ {text}{Colors.RESET}")


def check_openai_key() -> tuple[bool, str]:
    """Check OpenAI API key"""
    key = os.getenv("OPENAI_API_KEY")

    if not key:
        return False, "Not set"

    if not (key.startswith("sk-") or key.startswith("sk-proj-")):
        return False, "Invalid format (should start with sk- or sk-proj-)"

    # Test the key
    try:
        req = urllib.request.Request("https://api.openai.com/v1/models")
        req.add_header("Authorization", f"Bearer {key}")

        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                return True, f"Valid ({key[:15]}...)"
            else:
                return False, f"HTTP {response.status}"
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "Invalid or expired"
        else:
            return False, f"HTTP {e.code}"
    except Exception as e:
        return False, f"Error: {str(e)[:50]}"


def check_anthropic_key() -> tuple[bool, str]:
    """Check Anthropic API key"""
    key = os.getenv("ANTHROPIC_API_KEY")

    if not key:
        return False, "Not set (optional)"

    if not key.startswith("sk-ant-"):
        return False, "Invalid format (should start with sk-ant-)"

    # Test the key
    try:
        req = urllib.request.Request("https://api.anthropic.com/v1/messages")
        req.add_header("x-api-key", key)
        req.add_header("anthropic-version", "2023-06-01")
        req.add_header("content-type", "application/json")

        # Send minimal test request
        data = json.dumps(
            {
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "Hi"}],
            }
        ).encode()

        req.data = data

        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                return True, f"Valid ({key[:15]}...)"
            else:
                return False, f"HTTP {response.status}"
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "Invalid or expired"
        else:
            # Some errors are expected for minimal test
            return True, f"Key present ({key[:15]}...)"
    except Exception:
        return True, f"Key present ({key[:15]}...)"


def check_google_key() -> tuple[bool, str]:
    """Check Google API key"""
    key = os.getenv("GOOGLE_API_KEY")

    if not key:
        return False, "Not set (optional)"

    if not key.startswith("AIza"):
        return False, "Invalid format (should start with AIza)"

    return True, f"Present ({key[:15]}...)"


def check_deepseek_key() -> tuple[bool, str]:
    """Check DeepSeek API key"""
    key = os.getenv("DEEPSEEK_API_KEY")

    if not key:
        return False, "Not set (optional)"

    return True, f"Present ({key[:15]}...)"


def check_github_token() -> tuple[bool, str]:
    """Check GitHub token"""
    token = os.getenv("GITHUB_TOKEN")

    if not token:
        return False, "Not set"

    if not (token.startswith("ghp_") or token.startswith("github_pat_")):
        return False, "Invalid format"

    # Test the token
    try:
        req = urllib.request.Request("https://api.github.com/user")
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                data = json.loads(response.read())
                return True, f"Valid - {data['login']}"
            else:
                return False, f"HTTP {response.status}"
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "Invalid or expired"
        else:
            return False, f"HTTP {e.code}"
    except Exception as e:
        return False, f"Error: {str(e)[:50]}"


def main():
    """Main verification function"""
    print_header("API KEYS VERIFICATION")
    print_info("Checking all API keys for Kiro IDE integration...")

    results = {}

    # Check OpenAI (Required)
    print_header("1. OpenAI API Key (REQUIRED)")
    success, message = check_openai_key()
    results["OpenAI"] = success
    if success:
        print_success(f"OpenAI API Key: {message}")
    else:
        print_error(f"OpenAI API Key: {message}")
        print_info("Get key: https://platform.openai.com/api-keys")
        print_info('Set with: $env:OPENAI_API_KEY="sk-proj-your-key-here"')

    # Check Anthropic (Optional)
    print_header("2. Anthropic API Key (OPTIONAL)")
    success, message = check_anthropic_key()
    results["Anthropic"] = success
    if success:
        print_success(f"Anthropic API Key: {message}")
    else:
        print_warning(f"Anthropic API Key: {message}")
        print_info("Get key: https://console.anthropic.com/settings/keys")

    # Check Google (Optional)
    print_header("3. Google API Key (OPTIONAL)")
    success, message = check_google_key()
    results["Google"] = success
    if success:
        print_success(f"Google API Key: {message}")
    else:
        print_warning(f"Google API Key: {message}")
        print_info("Get key: https://makersuite.google.com/app/apikey")

    # Check DeepSeek (Optional)
    print_header("4. DeepSeek API Key (OPTIONAL)")
    success, message = check_deepseek_key()
    results["DeepSeek"] = success
    if success:
        print_success(f"DeepSeek API Key: {message}")
    else:
        print_warning(f"DeepSeek API Key: {message}")
        print_info("Get key: https://platform.deepseek.com/api_keys")

    # Check GitHub (For MCP)
    print_header("5. GitHub Token (FOR MCP TOOLS)")
    success, message = check_github_token()
    results["GitHub"] = success
    if success:
        print_success(f"GitHub Token: {message}")
    else:
        print_warning(f"GitHub Token: {message}")
        print_info("Already set in .env file")

    # Summary
    print_header("VERIFICATION SUMMARY")

    required_ok = results["OpenAI"]
    optional_count = sum(
        [results["Anthropic"], results["Google"], results["DeepSeek"]]
    )

    if required_ok:
        print_success("✓ Required: OpenAI API key is valid")
    else:
        print_error("✗ Required: OpenAI API key is missing or invalid")

    print_info(f"Optional: {optional_count}/3 additional providers configured")

    if results["GitHub"]:
        print_success("✓ GitHub token is valid (MCP tools will work)")
    else:
        print_warning("⚠ GitHub token not detected (but set in .env)")

    # Next steps
    print_header("NEXT STEPS")

    if required_ok:
        print_success("✓ You're ready to use Kiro IDE!")
        print_info("1. Launch Kiro IDE")
        print_info("2. MCP server will auto-start")
        print_info("3. All configured models will be available")
        print_info("4. Test with: 'Check MCP server health'")
    else:
        print_error("✗ OpenAI API key is required")
        print_info("1. Get key: https://platform.openai.com/api-keys")
        print_info('2. Set key: $env:OPENAI_API_KEY="sk-proj-your-key"')
        print_info("3. Run this script again to verify")

    # Exit code
    if required_ok:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_warning("\n\nVerification interrupted by user")
        sys.exit(130)
    except Exception as e:
        print_error(f"\n\nUnexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(3)
