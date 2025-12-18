# Kiro IDE API Keys Setup Guide

---
**Project Creator:** Herman Swanepoel  
**Version:** 1.0  
**Last Updated:** 2025-11-14

---

## Overview

This guide helps you configure API keys for all AI providers in Kiro IDE. Your Kiro agent will be able to use multiple AI models from different providers.

## Current Configuration Status

✅ **MCP Server:** Fixed and configured  
✅ **GitHub Token:** Set in environment  
⚠️ **AI Provider Keys:** Need to be configured  

---

## Required API Keys

Your `models.json` is configured to use these providers:

### 1. OpenAI (Required for GPT models)
- **Models:** GPT-4 Turbo, GPT-4, GPT-3.5 Turbo, O1 Preview
- **Environment Variable:** `OPENAI_API_KEY`
- **Get Key:** https://platform.openai.com/api-keys

### 2. Anthropic (Optional - for Claude)
- **Models:** Claude 3.5 Sonnet, Claude 3 Opus
- **Environment Variable:** `ANTHROPIC_API_KEY`
- **Get Key:** https://console.anthropic.com/settings/keys

### 3. Google (Optional - for Gemini)
- **Models:** Gemini 2.0 Flash, Gemini 1.5 Pro
- **Environment Variable:** `GOOGLE_API_KEY`
- **Get Key:** https://makersuite.google.com/app/apikey

### 4. DeepSeek (Optional - for DeepSeek)
- **Models:** DeepSeek Chat, DeepSeek Coder
- **Environment Variable:** `DEEPSEEK_API_KEY`
- **Get Key:** https://platform.deepseek.com/api_keys

---

## How to Get API Keys

### OpenAI API Key (Primary - Required)

1. Go to https://platform.openai.com/api-keys
2. Sign in or create account
3. Click **"Create new secret key"**
4. Name it: `Kiro IDE`
5. Copy the key (starts with `sk-proj-...` or `sk-...`)
6. **Save it immediately** - you won't see it again!

**Cost:** Pay-as-you-go (typically $0.01-0.10 per request)

### Anthropic API Key (Optional)

1. Go to https://console.anthropic.com/settings/keys
2. Sign in or create account
3. Click **"Create Key"**
4. Name it: `Kiro IDE`
5. Copy the key (starts with `sk-ant-...`)

**Cost:** Pay-as-you-go

### Google API Key (Optional)

1. Go to https://makersuite.google.com/app/apikey
2. Sign in with Google account
3. Click **"Create API Key"**
4. Copy the key (starts with `AIza...`)

**Cost:** Free tier available, then pay-as-you-go

### DeepSeek API Key (Optional)

1. Go to https://platform.deepseek.com/api_keys
2. Sign in or create account
3. Click **"Create API Key"**
4. Copy the key

**Cost:** Very affordable pay-as-you-go

---

## Setting Environment Variables

### Method 1: PowerShell (Current Session Only)

```powershell
# Set OpenAI key (REQUIRED)
$env:OPENAI_API_KEY="sk-proj-your-key-here"

# Set Anthropic key (OPTIONAL)
$env:ANTHROPIC_API_KEY="sk-ant-your-key-here"

# Set Google key (OPTIONAL)
$env:GOOGLE_API_KEY="AIza-your-key-here"

# Set DeepSeek key (OPTIONAL)
$env:DEEPSEEK_API_KEY="your-key-here"

# Verify keys are set
echo "OpenAI: $($env:OPENAI_API_KEY.Substring(0,10))..."
echo "Anthropic: $($env:ANTHROPIC_API_KEY.Substring(0,10))..."
```

### Method 2: Add to .env File (Persistent)

Edit your `.env` file in the project root:

```bash
# AI Provider API Keys
OPENAI_API_KEY=sk-proj-your-key-here
ANTHROPIC_API_KEY=sk-ant-your-key-here
GOOGLE_API_KEY=AIza-your-key-here
DEEPSEEK_API_KEY=your-key-here

# GitHub Integration
GITHUB_TOKEN=your_github_personal_access_token_here

# Backend Configuration
IDE_AGENTS_BACKEND_URL=http://127.0.0.1:8001
IDE_AGENTS_REQUEST_TIMEOUT=30.0

# ULTRA Mode Configuration
IDE_AGENTS_ULTRA_ENABLED=true
IDE_AGENTS_ULTRA_MOCK=false
IDE_AGENTS_ULTRA_LOCAL=false

# Telemetry
MCP_TOOL_SPANS_DIR=./logs
```

### Method 3: System Environment Variables (Permanent)

**Windows:**

1. Press `Win + X` and select **"System"**
2. Click **"Advanced system settings"**
3. Click **"Environment Variables"**
4. Under **"User variables"**, click **"New"**
5. Add each variable:
   - Variable name: `OPENAI_API_KEY`
   - Variable value: `sk-proj-your-key-here`
6. Click **OK** on all dialogs
7. **Restart Kiro IDE** to load new variables

---

## Verification Script

I'll create a script to test all your API keys:

```powershell
# Run this to verify all keys
python verify_api_keys.py
```

---

## Current Configuration Files

### 1. User-Level MCP Config
**Location:** `C:\Users\herma\.kiro\settings\mcp.json`

✅ **Status:** Fixed - removed duplicate brace  
✅ **Configuration:** Properly configured for MCP server  
✅ **GitHub Token:** Uses `${GITHUB_TOKEN}` from environment  

### 2. Provider Config
**Location:** `C:\Users\herma\.kiro\settings\provider_config.json`

✅ **Status:** Properly configured  
✅ **Default Provider:** OpenAI  
✅ **Task Routing:** 
- Code tasks: GPT-4, GPT-4 Turbo, Claude 3.5 Sonnet
- Reasoning tasks: O1 Preview, GPT-4, Claude 3.5 Sonnet
- Default tasks: GPT-4 Turbo, Claude 3.5 Sonnet, GPT-4

### 3. Models Config
**Location:** `C:\Users\herma\.kiro\settings\models.json`

✅ **Status:** Properly configured  
✅ **Default Model:** GPT-4 Turbo  
✅ **Providers:** OpenAI, Anthropic, Google, DeepSeek  
✅ **API Keys:** Uses environment variables (secure)  

---

## Available Models in Kiro Agent

Once you set the API keys, these models will be available:

### OpenAI Models (REQUIRED)
- ✅ **GPT-4 Turbo** (Default) - 128K context, best for coding
- ✅ **GPT-4** - 8K context, reliable
- ✅ **GPT-3.5 Turbo** - 16K context, fast and cheap
- ✅ **O1 Preview** - 128K context, advanced reasoning

### Anthropic Models (OPTIONAL)
- ✅ **Claude 3.5 Sonnet** - 200K context, excellent for code
- ✅ **Claude 3 Opus** - 200K context, most capable

### Google Models (OPTIONAL)
- ✅ **Gemini 2.0 Flash** - 1M context, very fast
- ✅ **Gemini 1.5 Pro** - 2M context, huge context window

### DeepSeek Models (OPTIONAL)
- ✅ **DeepSeek Chat** - 64K context, affordable
- ✅ **DeepSeek Coder** - 64K context, specialized for code

---

## Testing Your Setup

### Step 1: Set OpenAI Key (Minimum Required)

```powershell
$env:OPENAI_API_KEY="sk-proj-your-actual-key-here"
```

### Step 2: Verify Key Works

```powershell
python verify_api_keys.py
```

### Step 3: Launch Kiro IDE

The IDE will automatically:
1. Load environment variables
2. Connect to MCP server
3. Make all configured models available
4. Use GPT-4 Turbo as default

### Step 4: Test in Kiro Agent

Try these commands:

**Test 1: Basic Chat**
```
Hello! Can you help me with coding?
```

**Test 2: MCP Integration**
```
Check MCP server health
```

**Test 3: Emotion Analysis**
```
Analyze the emotion in: I'm excited about this setup!
```

**Test 4: Model Selection**
You can switch models in the Kiro IDE model selector dropdown

---

## Troubleshooting

### Issue: "API key not found"

**Solution:**
```powershell
# Check if key is set
echo $env:OPENAI_API_KEY

# If empty, set it
$env:OPENAI_API_KEY="your-key-here"
```

### Issue: "Invalid API key"

**Solution:**
1. Verify key is correct (no extra spaces)
2. Check key hasn't expired
3. Regenerate key from provider dashboard

### Issue: "Model not available"

**Solution:**
1. Ensure API key for that provider is set
2. Check provider account has access to that model
3. Verify billing is set up (for paid models)

### Issue: Kiro IDE doesn't see environment variables

**Solution:**
1. Set variables as System Environment Variables (Method 3)
2. Restart Kiro IDE completely
3. Or add to `.env` file in project root

---

## Security Best Practices

⚠️ **NEVER commit API keys to Git!**

✅ **DO:**
- Use environment variables
- Add `.env` to `.gitignore`
- Rotate keys regularly
- Use separate keys for dev/prod
- Monitor usage and costs

❌ **DON'T:**
- Hardcode keys in files
- Share keys in chat/email
- Commit `.env` to Git
- Use same key across projects
- Leave unused keys active

---

## Cost Management

### OpenAI Pricing (Approximate)
- GPT-4 Turbo: $0.01 per 1K input tokens, $0.03 per 1K output
- GPT-4: $0.03 per 1K input tokens, $0.06 per 1K output
- GPT-3.5 Turbo: $0.0005 per 1K input tokens, $0.0015 per 1K output

### Tips to Save Money
1. Use GPT-3.5 Turbo for simple tasks
2. Set usage limits in provider dashboard
3. Monitor usage regularly
4. Use caching when available
5. Optimize prompts to be concise

---

## Quick Start Checklist

- [ ] Get OpenAI API key (required)
- [ ] Set `OPENAI_API_KEY` environment variable
- [ ] Verify key with `python verify_api_keys.py`
- [ ] (Optional) Get Anthropic/Google/DeepSeek keys
- [ ] (Optional) Set additional API keys
- [ ] Restart Kiro IDE
- [ ] Test with Kiro agent
- [ ] Verify MCP tools work
- [ ] Check model selector shows all models

---

## Next Steps

1. **Get your OpenAI API key** (minimum required)
2. **Set the environment variable** (use Method 1 for quick test)
3. **Run verification script** to test
4. **Launch Kiro IDE** and test the agent
5. **Add other providers** as needed

---

**End of API Keys Setup Guide**

