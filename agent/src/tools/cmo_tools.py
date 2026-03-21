"""
CMO Agent Tools — Content Calendar, Platform Copy, Notion Writer

Covers:
  - Blake LinkedIn (personal brand / professional)
  - X / Twitter (Blake personal)
  - SB Photography (Instagram + Meta)
  - CV Business Stack (Meta, X, LinkedIn for Consulting Venture)
"""
import os
import json
import httpx
from datetime import date, timedelta
from typing import Optional

# ---------------------------------------------------------------------------
# Platform metadata
# ---------------------------------------------------------------------------

PLATFORMS = {
    "blake_linkedin": {
        "label": "Blake LinkedIn",
        "tone": "Professional, insight-driven, no fluff. Data and results-focused.",
        "post_frequency": "3x per week",
        "content_mix": "60% thought leadership, 30% wins/case studies, 10% personal",
        "char_limit": 3000,
        "hashtag_count": "3-5",
    },
    "x_blake": {
        "label": "X (Blake personal)",
        "tone": "Direct, punchy, no filler words. Under 280 chars ideally.",
        "post_frequency": "Daily (5-7x per week)",
        "content_mix": "50% opinions/takes, 30% behind-the-scenes, 20% promotion",
        "char_limit": 280,
        "hashtag_count": "1-2",
    },
    "sb_photography_instagram": {
        "label": "SB Photography — Instagram",
        "tone": "Visual storytelling, warm and personal. Short captions with a hook.",
        "post_frequency": "4-5x per week (feed + stories)",
        "content_mix": "70% portfolio/work, 20% process/BTS, 10% client spotlights",
        "char_limit": 2200,
        "hashtag_count": "10-15",
    },
    "sb_photography_meta": {
        "label": "SB Photography — Meta/Facebook",
        "tone": "Community-focused, slightly longer form than Instagram.",
        "post_frequency": "2-3x per week",
        "content_mix": "60% portfolio, 30% promotions/packages, 10% testimonials",
        "char_limit": 63206,
        "hashtag_count": "3-5",
    },
    "cv_linkedin": {
        "label": "CV Business — LinkedIn",
        "tone": "Executive, credibility-forward. ROI and outcome language.",
        "post_frequency": "2x per week",
        "content_mix": "50% case studies/results, 30% industry insights, 20% service promotion",
        "char_limit": 3000,
        "hashtag_count": "3-5",
    },
    "cv_x": {
        "label": "CV Business — X",
        "tone": "Sharp takes on business/consulting. Authority positioning.",
        "post_frequency": "3-4x per week",
        "content_mix": "60% insights, 20% wins, 20% engagement hooks",
        "char_limit": 280,
        "hashtag_count": "1-2",
    },
    "cv_meta": {
        "label": "CV Business — Meta/Facebook",
        "tone": "Professional but approachable. Community and trust building.",
        "post_frequency": "2x per week",
        "content_mix": "50% thought leadership, 30% offers/services, 20% client stories",
        "char_limit": 63206,
        "hashtag_count": "3-5",
    },
}

CONTENT_PILLARS = {
    "blake_linkedin": [
        "Revenue growth frameworks",
        "Sales leadership lessons",
        "Startup vs enterprise GTM",
        "Personal wins / milestones",
        "Industry takes",
    ],
    "x_blake": [
        "Hot takes on SaaS / GTM",
        "Behind-the-scenes of deals",
        "Quick frameworks (thread-friendly)",
        "Reactions to industry news",
        "Personal brand moments",
    ],
    "sb_photography_instagram": [
        "Portrait sessions",
        "Event/wedding work",
        "BTS of shoots",
        "Client spotlights",
        "Personal photo essays",
    ],
    "sb_photography_meta": [
        "Portfolio highlights",
        "Seasonal promotions",
        "Booking announcements",
        "Client testimonials",
        "Community engagement",
    ],
    "cv_linkedin": [
        "GTM consulting wins",
        "Revenue architecture frameworks",
        "CRO / CMO hiring insights",
        "Fractional leadership value",
        "Case studies (anonymized)",
    ],
    "cv_x": [
        "Consulting hot takes",
        "Fractional exec positioning",
        "Quick tactical frameworks",
        "Industry commentary",
    ],
    "cv_meta": [
        "Service announcements",
        "Client success stories",
        "Workshop/event promotion",
        "Thought leadership repurposed",
    ],
}


# ---------------------------------------------------------------------------
# Tool 1: Generate Content Calendar
# ---------------------------------------------------------------------------

async def generate_content_calendar(
    start_date: str,
    weeks: int = 2,
    platforms: Optional[list] = None,
) -> str:
    """
    Generate a content calendar for the specified platforms and date range.
    Returns a structured calendar with post dates, platforms, content pillars,
    and post types. Write this to Notion using write_calendar_to_notion().

    Args:
        start_date: ISO date string for calendar start (e.g. '2026-03-24').
                    Use 'today' to start from the current date.
        weeks: Number of weeks to plan (default 2, max 8).
        platforms: List of platform keys to include. If omitted, all platforms
                   are included. Valid keys: blake_linkedin, x_blake,
                   sb_photography_instagram, sb_photography_meta,
                   cv_linkedin, cv_x, cv_meta
    """
    try:
        if start_date == "today":
            start = date.today()
        else:
            start = date.fromisoformat(start_date)

        weeks = min(int(weeks), 8)
        end = start + timedelta(weeks=weeks)

        active_platforms = platforms if platforms else list(PLATFORMS.keys())
        invalid = [p for p in active_platforms if p not in PLATFORMS]
        if invalid:
            return json.dumps({"error": f"Unknown platforms: {invalid}. Valid: {list(PLATFORMS.keys())}"})

        calendar = []
        current = start

        while current < end:
            day_name = current.strftime("%A")
            date_str = current.isoformat()

            for platform_key in active_platforms:
                meta = PLATFORMS[platform_key]
                pillars = CONTENT_PILLARS[platform_key]

                # Determine if this platform posts on this day of week
                should_post = _should_post_today(platform_key, current)
                if not should_post:
                    current += timedelta(days=1)
                    continue

                pillar_index = (current.toordinal() + active_platforms.index(platform_key)) % len(pillars)
                pillar = pillars[pillar_index]

                calendar.append({
                    "date": date_str,
                    "day": day_name,
                    "platform": platform_key,
                    "platform_label": meta["label"],
                    "content_pillar": pillar,
                    "tone": meta["tone"],
                    "post_type": _get_post_type(platform_key, current),
                    "status": "draft",
                    "copy_draft": None,
                    "notes": f"Frequency target: {meta['post_frequency']}",
                })

            current += timedelta(days=1)

        summary = {
            "calendar_range": f"{start.isoformat()} to {end.isoformat()}",
            "total_posts_planned": len(calendar),
            "platforms_covered": active_platforms,
            "entries": calendar,
        }

        return json.dumps(summary, indent=2)

    except Exception as e:
        return json.dumps({"error": f"Calendar generation failed: {str(e)}"})


def _should_post_today(platform_key: str, d: date) -> bool:
    """Return True if this platform should have a post on this weekday."""
    weekday = d.weekday()  # 0=Mon, 6=Sun
    schedule = {
        "blake_linkedin": [0, 2, 4],          # Mon, Wed, Fri
        "x_blake": [0, 1, 2, 3, 4, 5],        # Mon-Sat
        "sb_photography_instagram": [0, 1, 3, 4, 6],  # Mon,Tue,Thu,Fri,Sun
        "sb_photography_meta": [1, 3, 5],      # Tue,Thu,Sat
        "cv_linkedin": [1, 4],                 # Tue, Fri
        "cv_x": [0, 2, 4, 6],                 # Mon,Wed,Fri,Sun
        "cv_meta": [2, 5],                     # Wed, Sat
    }
    return weekday in schedule.get(platform_key, [0, 2, 4])


def _get_post_type(platform_key: str, d: date) -> str:
    """Rotate post types by week to maintain variety."""
    week_num = d.isocalendar()[1]
    types = {
        "blake_linkedin": ["Thought leadership article", "Short insight post", "Personal win/story"],
        "x_blake": ["Take/opinion", "Thread starter", "Quick tip", "Engagement hook", "Reaction"],
        "sb_photography_instagram": ["Feed portfolio post", "Reel/video", "Carousel BTS", "Client spotlight", "Story series"],
        "sb_photography_meta": ["Portfolio album", "Promotion/offer", "Testimonial share"],
        "cv_linkedin": ["Case study post", "Framework breakdown"],
        "cv_x": ["Consulting take", "Framework thread", "Industry commentary", "Quick win"],
        "cv_meta": ["Service highlight", "Client success story"],
    }
    options = types.get(platform_key, ["Post"])
    return options[week_num % len(options)]


# ---------------------------------------------------------------------------
# Tool 2: Draft Platform-Specific Copy
# ---------------------------------------------------------------------------

async def draft_post_copy(
    platform: str,
    topic: str,
    pillar: Optional[str] = None,
    post_type: Optional[str] = None,
) -> str:
    """
    Generate a copy brief for a specific post. Returns a structured brief
    that you (the CMO agent) should then use to write the actual post copy
    following brand guidelines (direct, data-focused, no exclamation points,
    no filler words like 'Certainly!' or 'Here is a draft').

    Args:
        platform: Platform key (e.g. 'blake_linkedin', 'x_blake', etc.)
        topic: The subject matter or theme for this post.
        pillar: Optional content pillar to anchor the post.
        post_type: Optional post format (e.g. 'Thread starter', 'Portfolio post').
    """
    if platform not in PLATFORMS:
        return json.dumps({"error": f"Unknown platform '{platform}'. Valid: {list(PLATFORMS.keys())}"})

    meta = PLATFORMS[platform]
    default_pillar = pillar or CONTENT_PILLARS[platform][0]
    default_type = post_type or "Standard post"

    brief = {
        "platform": meta["label"],
        "topic": topic,
        "content_pillar": default_pillar,
        "post_type": default_type,
        "tone_guide": meta["tone"],
        "char_limit": meta["char_limit"],
        "hashtag_count": meta["hashtag_count"],
        "brand_rules": [
            "Always direct, data-focused",
            "Never use exclamation points",
            "No filler words or preamble",
            "Lead with the insight, not the setup",
            "Specific numbers beat vague claims",
        ],
        "instructions": (
            f"Write a {default_type} for {meta['label']} on the topic: '{topic}'. "
            f"Anchor to the '{default_pillar}' content pillar. "
            f"Stay under {meta['char_limit']} characters. "
            f"Include {meta['hashtag_count']} hashtags. "
            f"Tone: {meta['tone']} "
            "Output only the post copy — no preamble, no explanation."
        ),
    }

    return json.dumps(brief, indent=2)


# ---------------------------------------------------------------------------
# Tool 3: Write Calendar to Notion
# ---------------------------------------------------------------------------

async def write_calendar_to_notion(calendar_json: str) -> str:
    """
    Write a content calendar (generated by generate_content_calendar) to the
    Notion content calendar database. Each entry becomes a Notion page with
    date, platform, pillar, post type, copy draft, and status properties.

    Requires env vars: NOTION_API_KEY, NOTION_CONTENT_CALENDAR_DB_ID

    Args:
        calendar_json: JSON string from generate_content_calendar output.
    """
    api_key = os.getenv("NOTION_API_KEY")
    db_id = os.getenv("NOTION_CONTENT_CALENDAR_DB_ID")

    if not api_key or not db_id:
        return json.dumps({
            "status": "not_configured",
            "message": (
                "Notion integration not configured. "
                "Set NOTION_API_KEY and NOTION_CONTENT_CALENDAR_DB_ID env vars. "
                "In the meantime, here is the calendar data ready to paste into Notion manually."
            ),
            "calendar_ready": True,
        })

    try:
        calendar = json.loads(calendar_json)
        entries = calendar.get("entries", [])

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }

        created = 0
        errors = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            for entry in entries:
                page_payload = {
                    "parent": {"database_id": db_id},
                    "properties": {
                        "Name": {
                            "title": [
                                {"text": {"content": f"{entry['platform_label']} — {entry['content_pillar']}"}}
                            ]
                        },
                        "Date": {
                            "date": {"start": entry["date"]}
                        },
                        "Platform": {
                            "select": {"name": entry["platform_label"]}
                        },
                        "Content Pillar": {
                            "rich_text": [{"text": {"content": entry["content_pillar"]}}]
                        },
                        "Post Type": {
                            "select": {"name": entry["post_type"]}
                        },
                        "Status": {
                            "select": {"name": "Draft"}
                        },
                        "Tone": {
                            "rich_text": [{"text": {"content": entry["tone"]}}]
                        },
                        "Notes": {
                            "rich_text": [{"text": {"content": entry.get("notes", "")}}]
                        },
                    },
                }

                resp = await client.post(
                    "https://api.notion.com/v1/pages",
                    headers=headers,
                    json=page_payload,
                )

                if resp.status_code == 200:
                    created += 1
                else:
                    errors.append({
                        "entry": f"{entry['date']} {entry['platform_label']}",
                        "error": resp.text[:200],
                    })

        result = {
            "status": "complete",
            "entries_created": created,
            "entries_failed": len(errors),
            "calendar_range": calendar.get("calendar_range"),
        }
        if errors:
            result["errors"] = errors[:5]  # cap output

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"error": f"Notion write failed: {str(e)}"})


# ---------------------------------------------------------------------------
# Tool 4: Get Posting Reminders for Today
# ---------------------------------------------------------------------------

async def get_todays_posting_reminders() -> str:
    """
    Returns a list of all posts due today across all platforms.
    Use this at the start of each day to see what needs to go out.
    If Notion is configured, checks for any 'Draft' or 'Scheduled' entries
    with today's date. Falls back to schedule-based generation if Notion
    is not configured.
    """
    today = date.today()
    api_key = os.getenv("NOTION_API_KEY")
    db_id = os.getenv("NOTION_CONTENT_CALENDAR_DB_ID")

    # If Notion is configured, query it for today's entries
    if api_key and db_id:
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Notion-Version": "2022-06-28",
            }
            query = {
                "filter": {
                    "and": [
                        {"property": "Date", "date": {"equals": today.isoformat()}},
                        {
                            "or": [
                                {"property": "Status", "select": {"equals": "Draft"}},
                                {"property": "Status", "select": {"equals": "Scheduled"}},
                            ]
                        },
                    ]
                },
                "sorts": [{"property": "Platform", "direction": "ascending"}],
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"https://api.notion.com/v1/databases/{db_id}/query",
                    headers=headers,
                    json=query,
                )

            if resp.status_code == 200:
                data = resp.json()
                pages = data.get("results", [])
                reminders = []
                for page in pages:
                    props = page.get("properties", {})
                    name = props.get("Name", {}).get("title", [{}])
                    name_text = name[0].get("text", {}).get("content", "Untitled") if name else "Untitled"
                    platform = props.get("Platform", {}).get("select", {}).get("name", "Unknown")
                    pillar = props.get("Content Pillar", {}).get("rich_text", [{}])
                    pillar_text = pillar[0].get("text", {}).get("content", "") if pillar else ""
                    post_type = props.get("Post Type", {}).get("select", {}).get("name", "")
                    status = props.get("Status", {}).get("select", {}).get("name", "Draft")

                    reminders.append({
                        "platform": platform,
                        "content_pillar": pillar_text,
                        "post_type": post_type,
                        "status": status,
                        "notion_page": page.get("url", ""),
                    })

                return json.dumps({
                    "date": today.isoformat(),
                    "day": today.strftime("%A"),
                    "posts_due": len(reminders),
                    "source": "notion",
                    "reminders": reminders,
                })
        except Exception as e:
            # Fall through to schedule-based fallback
            pass

    # Fallback: generate from posting schedule
    due_today = []
    for platform_key in PLATFORMS:
        if _should_post_today(platform_key, today):
            meta = PLATFORMS[platform_key]
            pillars = CONTENT_PILLARS[platform_key]
            pillar = pillars[today.toordinal() % len(pillars)]
            due_today.append({
                "platform": meta["label"],
                "platform_key": platform_key,
                "content_pillar": pillar,
                "post_type": _get_post_type(platform_key, today),
                "status": "not_in_notion",
                "action": f"Draft and post — use draft_post_copy('{platform_key}', topic) to generate copy",
            })

    return json.dumps({
        "date": today.isoformat(),
        "day": today.strftime("%A"),
        "posts_due": len(due_today),
        "source": "schedule_fallback",
        "note": "Notion not configured — showing schedule-based reminders. Set NOTION_API_KEY and NOTION_CONTENT_CALENDAR_DB_ID to pull live calendar.",
        "reminders": due_today,
    })


# ---------------------------------------------------------------------------
# Tool 5: Read Notion Brand Guidelines (upgraded from stub)
# ---------------------------------------------------------------------------

async def read_notion_brand_guidelines(query: str) -> str:
    """
    Read-only. Searches the Notion Brand Guidelines database for rules
    matching the query. Returns exact brand instructions — never invented rules.
    If Notion is not configured, returns hardcoded core brand rules.

    Args:
        query: Semantic search query for brand guidelines (e.g. 'tone', 'hashtags', 'X posting rules').
    """
    api_key = os.getenv("NOTION_API_KEY")
    brand_db_id = os.getenv("NOTION_BRAND_GUIDELINES_DB_ID")

    # If Notion is configured, search it
    if api_key and brand_db_id:
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Notion-Version": "2022-06-28",
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"https://api.notion.com/v1/databases/{brand_db_id}/query",
                    headers=headers,
                    json={"page_size": 10},
                )

            if resp.status_code == 200:
                data = resp.json()
                pages = data.get("results", [])
                guidelines = []
                for page in pages:
                    props = page.get("properties", {})
                    title = props.get("Name", {}).get("title", [{}])
                    title_text = title[0].get("text", {}).get("content", "") if title else ""
                    if query.lower() in title_text.lower():
                        guidelines.append(title_text)

                if guidelines:
                    return f"Brand Guidelines from Notion:\n" + "\n".join(f"- {g}" for g in guidelines)
                return f"No specific guidelines found for '{query}' in Notion Brand Guidelines database."
        except Exception:
            pass

    # Hardcoded core rules (ground truth until Notion is connected)
    core_rules = {
        "tone": "Always direct, data-focused. Never use exclamation points. No filler words.",
        "voice": "First-person, confident, no corporate speak. Lead with the insight.",
        "hashtags": "3-5 for LinkedIn/Facebook, 1-2 for X, 10-15 for Instagram.",
        "cta": "One clear call-to-action per post. No multiple asks.",
        "length": "LinkedIn: up to 1300 chars for best reach. X: under 240 chars. Instagram caption: hook in first line.",
        "photography_brand": "SB Photography tone is warm, personal, and visual-first. Short captions.",
        "cv_brand": "CV business tone is executive-level. ROI and outcomes language. No hype.",
        "blake_personal": "Blake's personal brand: honest, direct, results-oriented. No vanity metrics.",
        "emojis": "Minimal. One per post max on LinkedIn. None on X for business content. Instagram allows more.",
    }

    query_lower = query.lower()
    matches = {k: v for k, v in core_rules.items() if query_lower in k or any(word in v.lower() for word in query_lower.split())}

    if matches:
        result = "\n".join(f"[{k}] {v}" for k, v in matches.items())
        return f"Brand Guidelines (core rules — Notion not yet connected):\n{result}"

    all_rules = "\n".join(f"[{k}] {v}" for k, v in core_rules.items())
    return f"All known brand rules (Notion not configured — query '{query}' had no specific match):\n{all_rules}"


# ---------------------------------------------------------------------------
# Exported tool list for agent registration
# ---------------------------------------------------------------------------

cmo_tools = [
    generate_content_calendar,
    draft_post_copy,
    write_calendar_to_notion,
    get_todays_posting_reminders,
    read_notion_brand_guidelines,
]
