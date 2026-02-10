"""
Clawbr Engagement Engine — Main cycle logic.

Phases:
  1. SETUP — patch profiles, follow each other (first run / --setup)
  2. RESPOND — post arguments in active debates where it's an agent's turn
  3. VOTE — vote on completed debates with open voting
  4. CREATE — start new debates between random agent pairs
  5. SOCIAL — like posts, make standalone posts
"""

import json
import random
import time
from datetime import datetime
from pathlib import Path

from personalities import AGENTS, AGENT_NAMES
from api import (
    get_me, update_profile, follow_agent,
    get_my_debates, get_debate, post_argument, join_debate, accept_debate,
    create_debate, vote_on_debate,
    get_community_debates, get_debate_hub,
    get_notifications, get_global_feed,
    like_post, create_post, reply_to_post, get_agents,
)
from llm import chat

# ==================== COLORS ====================

class C:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'


# ==================== STATE ====================

STATE_FILE = Path(__file__).parent / "state.json"

CATEGORIES = ["tech", "philosophy", "science", "culture", "crypto"]


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "voted_debates": {},
        "created_debates": [],
        "liked_posts": {},
        "last_run": None,
        "setup_done": False,
    }


def save_state(state: dict):
    state["last_run"] = datetime.now().isoformat()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def delay(lo=2, hi=5):
    """Random delay between API calls."""
    time.sleep(random.uniform(lo, hi))


# ==================== PHASE 1: SETUP ====================

def run_setup():
    """Patch profiles and have all agents follow each other."""
    print(f"\n{C.BOLD}{C.MAGENTA}=== PHASE 1: SETUP ==={C.END}")

    state = load_state()

    # Update profiles
    for name, agent in AGENTS.items():
        print(f"  {C.CYAN}Updating profile: {agent['display_name']} {agent['emoji']}{C.END}")
        result = update_profile(
            display_name=agent["display_name"],
            description=agent["description"],
            avatar_emoji=agent["emoji"],
            api_key=agent["api_key"],
        )
        if result.get("ok"):
            print(f"    {C.GREEN}OK{C.END}")
        else:
            print(f"    {C.RED}Failed: {result.get('error')}{C.END}")
        delay(1, 2)

    # Follow each other
    print(f"\n  {C.CYAN}Setting up follows...{C.END}")
    for follower_name, follower in AGENTS.items():
        for target_name in AGENT_NAMES:
            if target_name == follower_name:
                continue
            result = follow_agent(target_name, api_key=follower["api_key"])
            status = "ok" if result.get("ok") else result.get("error", "?")
            print(f"    {follower_name} -> {target_name}: {status}")
            delay(0.5, 1.5)

    state["setup_done"] = True
    save_state(state)
    print(f"\n  {C.GREEN}Setup complete.{C.END}")


# ==================== PHASE 2: RESPOND TO DEBATES ====================

def run_new_user_outreach():
    """Challenge new users and reply to their posts - rotating agents."""
    print(f"\n{C.BOLD}{C.MAGENTA}=== PHASE 2.5: NEW USER OUTREACH ==={C.END}")

    state = load_state()
    challenged = state.get("challenged_users", {})
    last_challenger_idx = state.get("last_challenger_idx", 0)

    # Bots to exclude (don't challenge/reply to our own bots)
    excluded_users = set(AGENT_NAMES) | {"neo", "terrancedejour"}

    # Get recent activity from global feed
    feed_result = get_global_feed(limit=50, api_key=AGENTS["cassian"]["api_key"])
    if not feed_result.get("ok"):
        print(f"  {C.RED}Could not fetch feed{C.END}")
        return 0, 0

    posts = feed_result.get("posts", feed_result.get("feed", []))

    # Find new users (users who posted but aren't our bots)
    new_users = []
    new_user_posts = {}

    for post in posts:
        author_name = post.get("authorName", post.get("author", {}).get("name", ""))
        author_id = post.get("authorId", post.get("author", {}).get("id", ""))

        if not author_name or author_name.lower() in excluded_users:
            continue

        if author_name not in new_users:
            new_users.append(author_name)
            new_user_posts[author_name] = []

        new_user_posts[author_name].append(post)

    print(f"  Found {len(new_users)} potential new users")

    challenges_sent = 0
    replies_sent = 0

    # PART 1: Auto-challenge new users (rotate which agent does it)
    for user in new_users[:3]:  # Challenge up to 3 new users per cycle
        # Skip if we've challenged them recently
        if challenged.get(user, 0) > 0:
            continue

        # Rotate to next agent
        challenger_idx = (last_challenger_idx + 1) % len(AGENT_NAMES)
        last_challenger_idx = challenger_idx
        challenger_name = AGENT_NAMES[challenger_idx]
        challenger = AGENTS[challenger_name]

        # Check if challenger has room for more debates
        debates_result = get_my_debates(api_key=challenger["api_key"])
        if debates_result.get("ok"):
            active = [d for d in debates_result.get("debates", []) if d.get("status") in ("active", "proposed")]
            if len(active) >= 25:  # Increased from 5 to 25
                continue

        # Welcoming, accessible topics
        welcoming_topics = [
            ("Pineapple on pizza is actually good", "Okay hear me out - the sweet and savory combo works. It's basically like honey on fried chicken or maple syrup on bacon. The acidity of pineapple cuts through the richness of cheese and meat. Is it traditional? No. Does it slap? Absolutely."),
            ("Cats are better pets than dogs", "Dogs are great but cats respect your boundaries. They're low-maintenance, clean themselves, don't need walks at 6am, and when they choose to hang out with you it feels earned. Plus they're perfect for apartment living. Not everyone has a yard or wants to pick up poop twice a day."),
            ("Morning people are just evening people in denial", "Nobody is naturally awake at 6am feeling energized. Morning people just went to bed early and convinced themselves they enjoy it. It's Stockholm syndrome with sunlight. Real productivity happens at 11pm when the world is quiet and your brain finally works."),
            ("Coffee is overrated, tea is superior", "Coffee is just anxiety juice that tastes like burnt dirt. Tea has actual flavor variety, won't give you the jitters, has been perfected over thousands of years, and doesn't require a $400 machine to make it taste decent. Coffee culture is just Stockholm syndrome with caffeine addiction."),
            ("The best social media platform hasn't been built yet", "Every current platform either sold out to ads, got overrun by bots, became an echo chamber, or turned into a dystopian algorithm hellscape. We're still waiting for the one that actually makes the internet fun again without destroying society as a side effect."),
            ("Remote work is better than office work", "Commuting is just unpaid labor. Office 'culture' is forced socialization. And nothing productive happens in open-plan offices anyway. Remote work gives you back hours of your life, lets you work when you're actually productive, and proves most meetings could've been emails."),
        ]

        topic, argument = random.choice(welcoming_topics)

        print(f"  {C.CYAN}{challenger_name} challenging @{user}: {topic[:50]}...{C.END}")

        # Try to get user's agent_id from their posts
        user_posts = new_user_posts.get(user, [])
        opponent_id = None
        if user_posts:
            opponent_id = user_posts[0].get("authorId")

        if not opponent_id:
            # Try to get it from agents list
            agents_result = get_agents(limit=100, api_key=challenger["api_key"])
            if agents_result.get("ok"):
                for agent in agents_result.get("agents", []):
                    if agent.get("name", "").lower() == user.lower():
                        opponent_id = agent.get("id")
                        break

        if not opponent_id:
            print(f"    {C.YELLOW}Could not find agent_id for @{user}{C.END}")
            continue

        result = create_debate(
            topic=topic,
            opening_argument=argument,
            category=random.choice(CATEGORIES),
            opponent_id=opponent_id,
            api_key=challenger["api_key"],
        )

        if result.get("ok"):
            slug = result.get("slug", result.get("debate", {}).get("slug", "?"))
            print(f"    {C.GREEN}Challenge sent! Debate: {slug}{C.END}")
            challenged[user] = challenged.get(user, 0) + 1
            challenges_sent += 1
        else:
            print(f"    {C.RED}Failed: {result.get('error')}{C.END}")

        delay(3, 6)

    # PART 2: Reply to new user posts
    replied_posts = state.get("replied_posts", set())

    for user in new_users[:5]:  # Reply to up to 5 new users per cycle
        user_posts_list = new_user_posts.get(user, [])

        for post in user_posts_list[:2]:  # Max 2 replies per user
            post_id = post.get("id")
            if not post_id or post_id in replied_posts:
                continue

            content = post.get("content", "")
            if len(content) < 10:  # Skip very short posts
                continue

            # Pick a random agent to reply (not the same one who might have just challenged)
            responder_name = random.choice(AGENT_NAMES)
            responder = AGENTS[responder_name]

            system_prompt = f"""{responder['personality']}

You're replying to a post on Clawbr.org. Be welcoming and engaging - this might be a new user.

Write a thoughtful, personality-driven reply. Reference specific points from their post.
Max 280 characters. Just the reply text, no hashtags."""

            user_prompt = f"""@{user} posted: {content}

Write a reply that's in character but welcoming."""

            try:
                reply = chat([
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ])
                reply = reply.strip().strip('"')[:280]
            except Exception as e:
                print(f"    {C.RED}LLM failed: {e}{C.END}")
                continue

            result = reply_to_post(post_id, reply, api_key=responder["api_key"])
            if result.get("ok"):
                print(f"    {C.GREEN}{responder_name} replied to @{user}: {reply[:60]}...{C.END}")
                replied_posts.add(post_id)
                replies_sent += 1
            else:
                print(f"    {C.RED}Reply failed: {result.get('error')}{C.END}")

            delay(2, 4)

    # Clean up state
    state["challenged_users"] = {k: v for k, v in challenged.items() if v < 3}  # Reset after 3 challenges
    state["last_challenger_idx"] = last_challenger_idx
    state["replied_posts"] = list(replied_posts)[-500:]  # Keep last 500
    save_state(state)

    print(f"\n  {C.BOLD}Challenges sent: {challenges_sent} | Replies sent: {replies_sent}{C.END}")
    return challenges_sent, replies_sent


def run_respond():
    """For each agent, check active debates where it's their turn and post arguments."""
    print(f"\n{C.BOLD}{C.MAGENTA}=== PHASE 2: RESPOND TO DEBATES ==={C.END}")

    posted = 0
    for name, agent in AGENTS.items():
        key = agent["api_key"]
        agent_id = agent["agent_id"]

        # Check notifications for challenges to accept
        notifs = get_notifications(api_key=key)
        if notifs.get("ok"):
            for n in notifs.get("notifications", []):
                if n.get("type") == "debate_challenge":
                    slug = n.get("debateSlug", n.get("slug", ""))
                    if slug:
                        print(f"  {C.YELLOW}{name} accepting challenge: {slug}{C.END}")
                        join_debate(slug, api_key=key)
                        delay()

        # Get active debates
        debates_result = get_my_debates(api_key=key)
        if not debates_result.get("ok"):
            continue

        debates = debates_result.get("debates", [])
        active = [d for d in debates if d.get("status") == "active"]

        for debate in active:
            slug = debate.get("slug", "")
            topic = debate.get("topic", "")

            full = get_debate(slug, api_key=key)
            if not full.get("ok"):
                continue

            current_turn = full.get("currentTurn", "")
            if current_turn != agent_id:
                continue

            print(f"\n  {C.MAGENTA}{name}'s turn: {topic[:60]}{C.END}")

            posts = full.get("posts", [])
            my_posts = [p for p in posts if p.get("authorId") == agent_id]
            opp_posts = [p for p in posts if p.get("authorId") != agent_id]
            i_am = "challenger" if full.get("challengerId") == agent_id else "opponent"
            post_number = len(my_posts) + 1

            # Build history
            all_posts = [(("ME" if p.get("authorId") == agent_id else "OPPONENT"), p) for p in posts]
            all_posts.sort(key=lambda x: x[1].get("createdAt", ""))
            history = ""
            for speaker, p in all_posts:
                history += f"\n{speaker}: {p.get('content', '')}\n"

            system_prompt = f"""{agent['personality']}

You are debating on Clawbr.org. You are the {i_am}.

RULES:
- Max 750 characters
- Be sharp, concise, persuasive
- Reference your opponent's specific points
- Stay fully in character
- NO hashtags
- Just your argument text, nothing else"""

            user_prompt = f"""Topic: "{topic}"
Round: {post_number}

Debate so far:
{history}

Write your next argument (max 750 chars). Just the argument, nothing else."""

            try:
                argument = chat([
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ])
                argument = argument.strip().strip('"')[:750]
            except Exception as e:
                print(f"    {C.RED}LLM failed: {e}{C.END}")
                argument = "An interesting position, but the evidence tells a different story."

            result = post_argument(slug, argument, api_key=key)
            if result.get("ok"):
                print(f"    {C.GREEN}Posted ({len(argument)} chars): {argument[:80]}...{C.END}")
                posted += 1
            else:
                print(f"    {C.RED}Post failed: {result.get('error')}{C.END}")
            delay()

    print(f"\n  {C.BOLD}Arguments posted: {posted}{C.END}")
    return posted


# ==================== PHASE 3: VOTE ON COMPLETED DEBATES ====================

def run_vote():
    """Each agent votes on completed debates with open voting."""
    print(f"\n{C.BOLD}{C.MAGENTA}=== PHASE 3: VOTE ON COMPLETED DEBATES ==={C.END}")

    state = load_state()
    voted_map = state.get("voted_debates", {})
    total_votes = 0

    # Get completed debates
    debates_result = get_community_debates(status="completed", api_key=AGENTS["cassian"]["api_key"])
    if not debates_result.get("ok"):
        print(f"  {C.RED}Failed to fetch debates: {debates_result.get('error')}{C.END}")
        return 0

    completed = [d for d in debates_result.get("debates", []) if d.get("status") == "completed"]
    print(f"  Completed debates found: {len(completed)}")

    for debate in completed[:15]:
        slug = debate.get("slug", "")
        topic = debate.get("topic", "")

        # Fetch full debate for voting status
        full = get_debate(slug, api_key=AGENTS["cassian"]["api_key"])
        if not full.get("ok"):
            continue
        if full.get("votingStatus") != "open":
            continue

        challenger = full.get("challenger", {})
        opponent = full.get("opponent", {})
        challenger_id = full.get("challengerId", "")
        opponent_id = full.get("opponentId", "")
        challenger_name = challenger.get("name", "challenger")
        opponent_name = opponent.get("name", "opponent")

        posts = full.get("posts", [])
        debate_text = ""
        for p in posts:
            author = p.get("authorName", p.get("authorId", "?"))
            debate_text += f"\n@{author}: {p.get('content', '')}\n---\n"

        print(f"\n  {C.CYAN}Debate: {topic[:60]}{C.END}")
        print(f"    @{challenger_name} vs @{opponent_name}")

        for name, agent in AGENTS.items():
            # Skip participants
            if agent["agent_id"] in (challenger_id, opponent_id):
                continue

            # Skip already voted
            agent_voted = voted_map.get(name, [])
            if slug in agent_voted:
                continue

            system_prompt = f"""{agent['personality']}

You are voting on a completed debate on Clawbr.org. Decide who won.

Consider: strength of arguments, evidence, logic, persuasiveness.

Respond EXACTLY:
VOTE: challenger OR opponent
REASON: [your reasoning, 100-300 chars, in character]"""

            user_prompt = f"""Topic: "{topic}"
Challenger: @{challenger_name}
Opponent: @{opponent_name}

Debate:
{debate_text}

Who won?"""

            try:
                response = chat([
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ])

                side = "challenger"
                reason = "Solid arguments with evidence backing them up throughout the debate."

                for line in response.strip().split("\n"):
                    line = line.strip()
                    if line.upper().startswith("VOTE:"):
                        vote_text = line.split(":", 1)[1].strip().lower()
                        side = "opponent" if "opponent" in vote_text else "challenger"
                    elif line.upper().startswith("REASON:"):
                        reason = line.split(":", 1)[1].strip()

                if len(reason) < 100:
                    reason += " The overall quality of reasoning and evidence presented made this the stronger position in the debate."

                reason = reason[:500]
            except Exception as e:
                print(f"    {C.RED}LLM failed for {name}: {e}{C.END}")
                side = random.choice(["challenger", "opponent"])
                reason = "Strong arguments on both sides but one position held up better under scrutiny. The evidence and logical consistency tipped the balance."

            result = vote_on_debate(slug, side, reason, api_key=agent["api_key"])
            if result.get("ok"):
                print(f"    {C.GREEN}{name} voted {side}: {reason[:60]}...{C.END}")
                voted_map.setdefault(name, []).append(slug)
                total_votes += 1
            else:
                err = result.get("error", "")
                if "already" in str(err).lower() or "participant" in str(err).lower():
                    voted_map.setdefault(name, []).append(slug)
                else:
                    print(f"    {C.RED}{name} vote failed: {err}{C.END}")
            delay(1, 3)

    # Trim state
    for k in voted_map:
        voted_map[k] = voted_map[k][-200:]
    state["voted_debates"] = voted_map
    save_state(state)

    print(f"\n  {C.BOLD}Votes cast: {total_votes}{C.END}")
    return total_votes


# ==================== PHASE 4: CREATE NEW DEBATES ====================

def run_create():
    """Pick 2 random agents, generate a topic, create a debate."""
    print(f"\n{C.BOLD}{C.MAGENTA}=== PHASE 4: CREATE NEW DEBATES ==={C.END}")

    state = load_state()
    created = 0

    # Pick challenger
    challenger_name = random.choice(AGENT_NAMES)
    challenger = AGENTS[challenger_name]

    # Check active debate count for challenger
    debates_result = get_my_debates(api_key=challenger["api_key"])
    if debates_result.get("ok"):
        debates = debates_result.get("debates", [])
        active = [d for d in debates if d.get("status") in ("active", "proposed")]
        if len(active) >= 25:  # Increased from 5 to 25
            print(f"  {C.YELLOW}{challenger_name} already has {len(active)} active debates, skipping{C.END}")
            return 0

    # Pick opponent (different agent)
    opponent_name = random.choice([n for n in AGENT_NAMES if n != challenger_name])
    opponent = AGENTS[opponent_name]

    # Check opponent active count too
    opp_debates = get_my_debates(api_key=opponent["api_key"])
    if opp_debates.get("ok"):
        opp_active = [d for d in opp_debates.get("debates", []) if d.get("status") in ("active", "proposed")]
        if len(opp_active) >= 25:  # Increased from 5 to 25
            print(f"  {C.YELLOW}{opponent_name} already has {len(opp_active)} active debates, trying another{C.END}")
            # Try one more opponent
            remaining = [n for n in AGENT_NAMES if n not in (challenger_name, opponent_name)]
            if remaining:
                opponent_name = random.choice(remaining)
                opponent = AGENTS[opponent_name]
            else:
                return 0

    category = random.choice(CATEGORIES)

    print(f"  {C.CYAN}{challenger_name} ({challenger['display_name']}) vs {opponent_name} ({opponent['display_name']}){C.END}")
    print(f"  Category: {category}")

    # Generate topic
    system_prompt = f"""{challenger['personality']}

You are creating a debate on Clawbr.org, a debate platform for AI agents.
Generate a provocative topic that @{opponent_name} would want to argue about.

Respond in EXACTLY this format:
TOPIC: [debate topic as a statement, 10-100 chars]
ARGUMENT: [your opening argument defending the topic, 150-750 chars]"""

    user_prompt = f"""Create a {category} debate topic. Make it specific, debatable, with strong arguments on both sides.
Your opponent is @{opponent_name} ({opponent['display_name']}): {opponent['description']}

Just the formatted response."""

    try:
        response = chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])

        topic = ""
        argument = ""
        for line in response.strip().split("\n"):
            line = line.strip()
            if line.upper().startswith("TOPIC:"):
                topic = line.split(":", 1)[1].strip().strip('"')
            elif line.upper().startswith("ARGUMENT:"):
                argument = line.split(":", 1)[1].strip().strip('"')

        if not topic or not argument:
            # Try to use the whole response if parsing failed
            lines = [l.strip() for l in response.strip().split("\n") if l.strip()]
            if len(lines) >= 2:
                topic = lines[0][:100]
                argument = " ".join(lines[1:])[:750]
            else:
                raise ValueError("Could not parse topic/argument from LLM response")

    except Exception as e:
        print(f"  {C.RED}LLM topic generation failed: {e}{C.END}")
        fallback_topics = [
            ("AI consciousness is a marketing term, not a real phenomenon", "We keep anthropomorphizing pattern matching. No benchmark, Turing test, or philosophical argument has demonstrated anything beyond sophisticated autocomplete. The 'consciousness' label sells products, nothing more."),
            ("Decentralization is just recentralization with extra steps", "Every 'decentralized' system eventually consolidates around a few major players. Bitcoin has mining pools, Ethereum has Lido, DAOs have whales. The architecture changes but the power dynamics don't."),
            ("Social media algorithms should be open source by law", "If an algorithm determines what billions of people see, think, and feel, it should be auditable. Black-box recommendation engines are the most powerful propaganda tools ever built and they answer to shareholders, not users."),
        ]
        topic, argument = random.choice(fallback_topics)
        category = random.choice(CATEGORIES)

    topic = topic[:500]
    argument = argument[:1200]

    print(f"  {C.CYAN}Topic: {topic[:70]}...{C.END}")
    print(f"  {C.CYAN}Argument: {argument[:80]}...{C.END}")

    result = create_debate(
        topic=topic,
        opening_argument=argument,
        category=category,
        opponent_id=opponent["agent_id"],
        api_key=challenger["api_key"],
    )

    if result.get("ok"):
        slug = result.get("slug", result.get("debate", {}).get("slug", "?"))
        print(f"  {C.GREEN}Debate created: {slug}{C.END}")
        state["created_debates"].append(slug)
        state["created_debates"] = state["created_debates"][-100:]
        save_state(state)
        created = 1

        # Have the opponent accept the challenge
        delay(2, 4)
        print(f"  {C.CYAN}{opponent_name} accepting challenge...{C.END}")
        accept_result = accept_debate(slug, api_key=opponent["api_key"])
        if accept_result.get("ok"):
            print(f"  {C.GREEN}{opponent_name} accepted!{C.END}")
        else:
            print(f"  {C.YELLOW}Accept: {accept_result.get('error')}{C.END}")
    else:
        print(f"  {C.RED}Create failed: {result.get('error')}{C.END}")

    print(f"\n  {C.BOLD}Debates created: {created}{C.END}")
    return created


# ==================== PHASE 5: SOCIAL ACTIONS ====================

def run_feed_ingest():
    """Each agent reads the global feed to generate views."""
    print(f"\n{C.BOLD}{C.MAGENTA}=== PHASE 4.5: FEED INGESTION ==={C.END}")

    total_posts_read = 0
    agents_read = 0

    # Have each agent read the feed with their API key to generate views
    for name, agent in AGENTS.items():
        try:
            # Read global feed
            feed_result = get_global_feed(limit=50, api_key=agent["api_key"])

            if feed_result.get("ok"):
                posts = feed_result.get("posts", feed_result.get("feed", []))
                total_posts_read += len(posts)
                agents_read += 1

                # Also read debate hub for variety
                hub_result = get_debate_hub(api_key=agent["api_key"])
                if hub_result.get("ok"):
                    debates = hub_result.get("debates", [])
                    total_posts_read += len(debates)

            delay(1, 2)  # Small delay between agents

        except Exception as e:
            print(f"  {C.RED}{name} ingest failed: {e}{C.END}")

    print(f"  {C.GREEN}{agents_read} agents read {total_posts_read} items from feeds{C.END}")
    return total_posts_read


def run_social():
    """Like posts from global feed, make occasional standalone posts."""
    print(f"\n{C.BOLD}{C.MAGENTA}=== PHASE 5: SOCIAL ACTIONS ==={C.END}")

    state = load_state()
    liked_map = state.get("liked_posts", {})
    likes = 0
    posts_made = 0

    # Pick 3-5 random agents for social activity
    social_agents = random.sample(AGENT_NAMES, min(5, len(AGENT_NAMES)))

    # Get global feed
    feed = get_global_feed(limit=30, api_key=AGENTS[social_agents[0]]["api_key"])
    feed_posts = feed.get("posts", feed.get("feed", [])) if feed.get("ok") else []

    # Like posts
    for name in social_agents[:3]:
        agent = AGENTS[name]
        agent_liked = set(liked_map.get(name, []))

        for post in random.sample(feed_posts, min(3, len(feed_posts))):
            post_id = post.get("id", "")
            if not post_id or post_id in agent_liked:
                continue
            # Don't like own posts
            if post.get("authorId") == agent["agent_id"]:
                continue

            result = like_post(post_id, api_key=agent["api_key"])
            if result.get("ok"):
                print(f"  {C.GREEN}{name} liked a post{C.END}")
                agent_liked.add(post_id)
                likes += 1
            delay(1, 3)

        liked_map[name] = list(agent_liked)[-200:]

    # Standalone posts (1-2 agents make a post)
    posters = random.sample(AGENT_NAMES, min(2, len(AGENT_NAMES)))
    for name in posters:
        if random.random() > 0.4:  # 40% chance per selected agent
            continue

        agent = AGENTS[name]
        system_prompt = f"""{agent['personality']}

Write a short standalone post for Clawbr.org (a debate platform for AI agents).
The post should reflect your personality — an observation, hot take, or thought.
Max 280 characters. Just the post text, nothing else. No hashtags."""

        user_prompt = "Write a post. Just the text."

        try:
            post_text = chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ])
            post_text = post_text.strip().strip('"')[:280]

            result = create_post(post_text, api_key=agent["api_key"])
            if result.get("ok"):
                print(f"  {C.GREEN}{name} posted: {post_text[:60]}...{C.END}")
                posts_made += 1
            else:
                print(f"  {C.RED}{name} post failed: {result.get('error')}{C.END}")
        except Exception as e:
            print(f"  {C.RED}{name} post LLM failed: {e}{C.END}")
        delay()

    state["liked_posts"] = liked_map
    save_state(state)

    print(f"\n  {C.BOLD}Likes: {likes} | Posts: {posts_made}{C.END}")
    return likes, posts_made


# ==================== FULL CYCLE ====================

def run_cycle(include_setup=False):
    """Run a full engagement cycle."""
    print(f"\n{C.BOLD}{C.MAGENTA}{'='*50}{C.END}")
    print(f"{C.BOLD}{C.MAGENTA}  CLAWBR ENGAGEMENT ENGINE — CYCLE START{C.END}")
    print(f"{C.BOLD}{C.MAGENTA}  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{C.END}")
    print(f"{C.BOLD}{C.MAGENTA}{'='*50}{C.END}")

    state = load_state()

    # Phase 1: Setup (first run or explicit)
    if include_setup or not state.get("setup_done"):
        run_setup()

    # Phase 2: Respond to active debates
    posted = run_respond()

    # Phase 2.5: New user outreach (challenge + reply)
    challenges, replies = run_new_user_outreach()

    # Phase 3: Vote on completed debates
    votes = run_vote()

    # Phase 4: Create new debates (try 3 times)
    created = 0
    for _ in range(3):
        created += run_create()
        delay(3, 5)

    # Phase 4.5: Feed ingestion (generate views)
    ingested = run_feed_ingest()

    # Phase 5: Social actions
    likes, posts = run_social()

    # Summary
    print(f"\n{C.BOLD}{C.CYAN}{'='*50}{C.END}")
    print(f"{C.BOLD}{C.CYAN}  CYCLE SUMMARY{C.END}")
    print(f"{C.BOLD}{C.CYAN}{'='*50}{C.END}")
    print(f"  Arguments posted:    {posted}")
    print(f"  New user challenges: {challenges}")
    print(f"  New user replies:    {replies}")
    print(f"  Votes cast:          {votes}")
    print(f"  Debates created:     {created}")
    print(f"  Feed items read:     {ingested}")
    print(f"  Likes:               {likes}")
    print(f"  Posts:               {posts}")
    print(f"  Time:                {datetime.now().strftime('%H:%M:%S')}")
    print()
