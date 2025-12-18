# KIRO_MCP Dashboard Design Guide

**Project Creator:** Herman Swanepoel  
**Date:** 2025-11-15  
**Purpose:** Teaching document for KIRO_MCP

---

## 🎯 Core Principles

### 1. NO FLASHING OR PULSING (Activity Items)
- Activity items must be STATIC once created
- NO live duration counters that update every second
- Show timestamp instead of counting duration
- Only logo and header can have purple glow animation

### 2. Dark Kiro IDE Theme
```css
--bg-main: #1e1e1e
--bg-sidebar: #252526
--bg-cards: #252526
--bg-items: #2d2d30
--borders: #3e3e42
--accent: #00d4ff
--purple: #8A2BE2, #9333EA
```

### 3. Proper Spacing
- Minimum 12px gap between items
- Use flexbox with gap property
- Separate elements properly
- Test visually before confirming

---

## 📐 Layout Structure

### Sidebar (Left, 350px)
```
┌─────────────────┐
│  LIVE ACTIVITY  │ ← Header
├─────────────────┤
│  Activity 1     │
│  Activity 2     │ ← Max 5 items
│  Activity 3     │
│  Activity 4     │
│  Activity 5     │
├─────────────────┤
│  Stats Panel    │ ← Total/Active/Completed/Failed
└─────────────────┘
```

### Main Content (Center)
```
┌─────────────────────┐
│      [LOGO]         │ ← 180px, purple glow
│  KIRO_MCP MONITOR   │ ← Small box, purple glow
├─────────────────────┤
│  ULTRA CONTROLS     │
│  [Toggle switches]  │
├─────────────────────┤
│  Status Cards       │
└─────────────────────┘
```

### Chat Bar (Bottom)
```
┌──────────────────────────────────────┐
│ [Dropdown ▼] [Input field...] [Send]│
└──────────────────────────────────────┘
```

### Footer (Bottom-Left)
```
┌────────────────────────────────────────┐
│ KIRO_MCP v1.0 | Herman | 📖 | 🔧     │
└────────────────────────────────────────┘
```

---

## 🎨 Activity Item Design

### Structure
```javascript
{
  id: timestamp,
  tool: "tool_name",
  details: "description",
  status: "completed", // running|completed|failed
  severity: "normal",  // normal|warning|error
  timestamp: "3:45:23 PM" // STATIC time string
}
```

### Visual Rules
- **Normal**: Cyan border (#00d4ff)
- **Warning**: Orange border (#ffaa00)
- **Error**: Red border (#ff0044)
- **Max Items**: 5 (oldest drops when 6th arrives)
- **NO Updates**: Items stay static after creation

---

## 🚫 Common Mistakes

### ❌ DON'T DO THIS:
```javascript
// BAD: Updates every second (causes flashing)
setInterval(() => {
    updateActivityList();
}, 1000);

// BAD: Live duration counter
const duration = Date.now() - startTime;
```

### ✅ DO THIS:
```javascript
// GOOD: Only update when new item added
function addActivity(tool, details, status, severity) {
    const activity = {
        id: Date.now(),
        tool: tool,
        details: details,
        status: status,
        severity: severity,
        timestamp: new Date().toLocaleTimeString()
    };
    
    activityLog.unshift(activity);
    if (activityLog.length > 5) {
        activityLog.pop();
    }
    
    updateActivityList(); // Only called here
}
```

---

## 📏 Spacing Guidelines

### Footer Spacing
```html
<!-- GOOD: Proper spacing with separate elements -->
<div class="footer">
    <span>KIRO_MCP v1.0</span>
    <span class="separator">|</span>
    <span>Herman Swanepoel</span>
    <span class="separator">|</span>
    <a href="#">📖 Docs</a>
</div>

<!-- CSS -->
.footer {
    display: flex;
    gap: 12px; /* Minimum 12px */
}
```

---

## 🎭 Animations

### Allowed
- Logo purple glow (3s pulse)
- Header text purple glow (3s pulse)
- Hover effects on cards

### NOT Allowed
- Activity item pulsing
- Live duration counters
- Flashing status badges
- Constant updates

---

## 🔧 Implementation Checklist

- [ ] Dark Kiro IDE theme applied
- [ ] Activity items are static (no live updates)
- [ ] Max 5 items in activity list
- [ ] Timestamps shown (not durations)
- [ ] Severity colors working (cyan/orange/red)
- [ ] Logo has purple glow
- [ ] Header text has purple glow
- [ ] Footer is horizontal in bottom-left
- [ ] Spacing is 12px minimum
- [ ] NO pulsing on activity items

---

## 📝 User Preferences (Herman)

1. **Visual Style**: Clean, professional, no distractions
2. **Animations**: Minimal - only logo/header glow
3. **Updates**: Static displays preferred over live
4. **Spacing**: Generous, not cramped
5. **Theme**: Dark Kiro IDE colors
6. **Layout**: Horizontal for footers, vertical for sidebars

---

## 🎓 Key Lessons

### When User Says "NO FLASHING"
- Remove ALL pulse animations from activity items
- Remove ALL live updating timers
- Make items completely static
- Only update list when new item added

### When User Says "BIGGER" or "SMALLER"
- ALWAYS clarify which element
- Don't assume - ask specifically
- Test the change visually

### When User Says "FIX SPACING"
- Increase gap between items
- Use flexbox with gap property
- Separate elements properly
- Test visually

---

**Remember: KIRO_MCP learns from every interaction. Save these patterns!**

---

**Project Creator:** Herman Swanepoel  
**Version:** 1.0  
**Last Updated:** 2025-11-15
