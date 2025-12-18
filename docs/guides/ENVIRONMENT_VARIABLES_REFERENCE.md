# Environment Variables Reference for Kiro IDE

---
**Project Creator:** Herman Swanepoel  
**Quick Reference for System Environment Variables**

---

## Correct Variable Names

You need to set these **exact** variable names in Windows Environment Variables:

### Required Variables

| Variable Name | Your Key Name | Value Format |
|---------------|---------------|--------------|
| `OPENAI_API_KEY` | openAI key | `sk-proj-...` or `sk-...` |
| `GITHUB_TOKEN` | GitHub Kiro MCP token | `github_pat_...` or `ghp_...` |

### Optional Variables

| Variable Name | Your Key Name | Value Format |
|---------------|---------------|--------------|
| `ANTHROPIC_API_KEY` | Anthropic key | `sk-ant-...` |
| `DEEPSEEK_API_KEY` | DeepSeek Key | (varies) |
| `GOOGLE_API_KEY` | Google Gemini Key | `AIza...` |
| `GROQ_API_KEY` | Groq key | (varies) |

---

## Step-by-Step Setup

### 1. Open Environment Variables
- Press `Win + R`
- Type `sysdm.cpl`
- Press Enter
- Go to "Advanced" tab
- Click "Environment Variables"

### 2. Add Each Variable

Click "New" under "User variables" and add:

#### Variable 1: OpenAI (REQUIRED)
- **Variable name:** `OPENAI_API_KEY`
- **Variable value:** [Paste your openAI key here]

#### Variable 2: GitHub (REQUIRED for MCP)
- **Variable name:** `GITHUB_TOKEN`
- **Variable value:** `your_github_personal_access_token_here`

#### Variable 3: Anthropic (OPTIONAL)
- **Variable name:** `ANTHROPIC_API_KEY`
- **Variable value:** [Paste your Anthropic key here]

#### Variable 4: DeepSeek (OPTIONAL)
- **Variable name:** `DEEPSEEK_API_KEY`
- **Variable value:** [Paste your DeepSeek Key here]

#### Variable 5: Google (OPTIONAL)
- **Variable name:** `GOOGLE_API_KEY`
- **Variable value:** [Paste your Google Gemini Key here]

#### Variable 6: Groq (OPTIONAL - if you want to add it)
- **Variable name:** `GROQ_API_KEY`
- **Variable value:** [Paste your Groq key here]

### 3. Click OK on All Dialogs

### 4. Restart PowerShell/Terminal
Close all PowerShell windows and open a new one.

### 5. Verify Variables Are Set

```powershell
# Check each variable
echo $env:OPENAI_API_KEY
echo $env:GITHUB_TOKEN
echo $env:ANTHROPIC_API_KEY
echo $env:DEEPSEEK_API_KEY
echo $env:GOOGLE_API_KEY
echo $env:GROQ_API_KEY
```

---

## Important Notes

⚠️ **Variable names are CASE-SENSITIVE in some contexts**
- Use UPPERCASE for all variable names
- Use underscores `_` not spaces or dashes

⚠️ **After setting system variables:**
- Close ALL PowerShell/Terminal windows
- Restart Kiro IDE completely
- Variables will be available to all applications

✅ **Your keys are already in .env file:**
The GitHub token is already in your `.env` file, but setting it as a system variable ensures it works everywhere.

---

## Verification

After setting all variables and restarting, run:

```powershell
python verify_api_keys.py
```

Expected output:
```
✓ OpenAI API Key: Valid
✓ Anthropic API Key: Valid
✓ Google API Key: Present
✓ DeepSeek API Key: Present
✓ GitHub Token: Valid
```

---

## Quick Copy-Paste Format

For easy reference, here's the format to copy:

```
Variable Name: OPENAI_API_KEY
Variable Value: [your sk-proj-... key]

Variable Name: GITHUB_TOKEN
Variable Value: your_github_personal_access_token_here

Variable Name: ANTHROPIC_API_KEY
Variable Value: [your sk-ant-... key]

Variable Name: DEEPSEEK_API_KEY
Variable Value: [your deepseek key]

Variable Name: GOOGLE_API_KEY
Variable Value: [your AIza... key]

Variable Name: GROQ_API_KEY
Variable Value: [your groq key]
```

---

**End of Reference**

