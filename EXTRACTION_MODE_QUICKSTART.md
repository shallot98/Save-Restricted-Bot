# Extraction Mode - Quick Start Guide

## What is Extraction Mode?

Extraction Mode makes the bot forward **only the matched text snippets** instead of the entire message. Perfect for filtering long messages and getting straight to the important parts.

## Quick Setup (5 steps)

### 1. Add Some Filters

Add keywords or patterns you want to match:

```
/addre /bitcoin|crypto/i
```

or use global keywords in `filter_config.json`:
```json
{
  "keywords": ["urgent", "important"],
  "patterns": []
}
```

### 2. Test Your Setup

Before enabling, test what you'll get:

```
/preview This is an urgent announcement about Bitcoin reaching $50000!
```

You'll see a preview of the extracted snippets.

### 3. Enable Extraction Mode

```
/mode extract on
```

### 4. Set Up Watch

```
/watch add @source_channel me
```

### 5. Done!

Now when messages match your filters, you'll only receive the matched snippets with source information.

## Example Output

**Original Message:**
```
Good morning everyone! The weather is nice today. 
This is an important announcement about the meeting.
Tomorrow will be sunny. Have a great day!
```

**With Extraction Mode ON:**
```
👤 作者: John Doe
💬 频道: @announcements
🔗 链接: https://t.me/announcements/123

──────────────────────────────

📌 匹配 #1:
This is an important announcement about the meeting.
```

## Common Commands

| Command | Description |
|---------|-------------|
| `/mode show` | Check if extraction mode is on/off |
| `/mode extract on` | Turn extraction mode ON |
| `/mode extract off` | Turn extraction mode OFF |
| `/preview <text>` | Test extraction on sample text |
| `/addre <pattern>` | Add a regex filter |
| `/listre` | Show all regex filters |

## Tips

✅ **Do's:**
- Use `/preview` to test before enabling
- Start with one watch to verify output
- Use specific keywords for better results
- Combine with whitelist/blacklist for fine control

❌ **Don'ts:**
- Don't enable without setting up filters first
- Don't use too broad keywords (you'll get everything)
- Don't worry if a message is skipped (no match = no forward)

## Turning It Off

If you want full messages again:

```
/mode extract off
```

The bot will return to normal forwarding immediately.

## Need Help?

- Read full docs: `EXTRACTION_MODE.md`
- Run demo: `python3 demo_extraction.py`
- Check examples in help: `/help`

## FAQ

**Q: Will this affect all my watches?**  
A: Yes, extraction mode is global. All watches with matching filters will forward snippets.

**Q: What if there are no matches?**  
A: The message is silently skipped (not forwarded).

**Q: Can I test without enabling?**  
A: Yes! Use `/preview <text>` to test anytime.

**Q: How many snippets per message?**  
A: Maximum 10 snippets. If more, you'll see a warning.

**Q: Does it work with media?**  
A: Yes, but only captions are extracted (not media itself).

**Q: How do I see what I'm filtering for?**  
A: Use `/listre` to see all regex patterns. Keywords are in `filter_config.json`.

**Q: Can I use this with whitelist/blacklist?**  
A: Yes! They work together. Whitelist/blacklist filter first, then extraction happens.

## Examples by Use Case

### Monitor Crypto News
```
/addre /bitcoin|ethereum|BTC|ETH/i
/addre /\$\d+(?:,\d{3})*/
/mode extract on
/watch add @cryptonews me
```

### Track Urgent Messages
```
Edit filter_config.json:
{
  "keywords": ["urgent", "important", "critical"],
  "patterns": [],
  "extract_mode": true
}

/watch add @company_channel me
```

### Extract Prices/Numbers
```
/addre /\$\d+/
/addre /€\d+/
/addre /price.*\d+/i
/mode extract on
```

### Monitor Specific Topics
```
/addre /meeting|conference|event/i
/addre /deadline.*\d+/i
/watch add @work_channel me whitelist:project
/mode extract on
```

---

**That's it!** You're now extracting only what matters. 🎯
