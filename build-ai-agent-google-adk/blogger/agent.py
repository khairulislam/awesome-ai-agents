import os

from dotenv import load_dotenv
from google.adk import Agent, Context, Event, Workflow
from google.adk.models.lite_llm import LiteLlm
from google.adk.workflow import DEFAULT_ROUTE, RetryConfig
from pydantic import BaseModel, Field, ValidationError

# ── env/config ───────────────────────────────────────────────────────────────
load_dotenv()

# OpenRouter via LiteLLM: a `provider/model` id (e.g. `deepseek/deepseek-v4-flash`)
# is routed through OpenRouter using OPENROUTER_API_KEY from .env. Names without a
# slash (e.g. `gemini-flash-latest`) are passed to ADK as native Gemini models.
_name = os.getenv("MODEL", "gemini-flash-latest").strip("\"'")
if "/" in _name:
   # Reasoning models can spend most of their time "thinking" (minutes for a blog post);
   # set REASONING_EFFORT=low|medium|high in .env if you want it back.
   MODEL = LiteLlm(
       model=_name if _name.startswith("openrouter/") else f"openrouter/{_name}",
       reasoning_effort=os.getenv("REASONING_EFFORT", "none"),
   )
else:
   MODEL = _name

MAX_ATTEMPTS = 3
# Malformed JSON (doesn't fit the schema at all) is retried by ADK itself.
RETRY = RetryConfig(max_attempts=MAX_ATTEMPTS, initial_delay=0, exceptions=[ValidationError])


# ── Schemas ──────────────────────────────────────────────────────────────────
class Section(BaseModel):
   heading: str
   bullets: list[str] = Field(min_length=2, max_length=3)


class Outline(BaseModel):
   title: str
   intro: str
   sections: list[Section]
   conclusion: str


class BlogPost(BaseModel):
   markdown: str  # the full article, starting with the H1 title
   alternate_titles: list[str]
   tweet_hooks: list[str]


# ── Agents ───────────────────────────────────────────────────────────────────
blog_planner = Agent(
   name="BlogPlanner",
   model=MODEL,
   description="Creates a practical, skimmable outline.",
   instruction="""
You are a technical content strategist. Plan a blog post on the given topic:
a title, a short intro, 4-6 sections with 2-3 bullets each, and a conclusion.
If you are given problems with a previous outline, fix them.
""",
   output_schema=Outline,
   retry_config=RETRY,
)

blog_writer = Agent(
   name="BlogWriter",
   model=MODEL,
   description="Writes a technical blog post from an outline.",
   instruction="""
Write a complete Markdown article that follows the outline you are given.

- Audience: software engineers; skip basics and focus on practical insight.
- Explain both the 'how' and 'why'.
- Include concise code snippets when helpful.
- Use an H1 title, an H2 per outline section, and end with a conclusion.
- Give exactly 3 alternate titles and 2 tweet-length hooks (under 250 characters each)
  only in their own fields. Never put them, or sections for them, inside the markdown.
If you are given problems with a previous draft, fix them.
""",
   output_schema=BlogPost,
   retry_config=RETRY,
)


# ── Review nodes: check the output, loop back with feedback, or move on ──────
def _retry_prompt(request: str, problems: list[str], previous: str) -> str:
   fixes = "\n".join(f"- {p}" for p in problems)
   return f"{request}\n\nProblems with the previous attempt:\n{fixes}\n\nPrevious attempt:\n{previous}"


def remember_topic(node_input: str):
   return Event(output=node_input, state={"brief": node_input})


def review_outline(ctx: Context, node_input: Outline):
   problems = []
   if not 4 <= len(node_input.sections) <= 6:
       problems.append(f"has {len(node_input.sections)} sections; needs 4-6")

   attempts = ctx.state.get("outline_attempts", 0) + 1
   outline = node_input.model_dump_json()
   if problems and attempts < MAX_ATTEMPTS:
       return Event(route="retry", output=_retry_prompt(ctx.state["brief"], problems, outline), state={"outline_attempts": attempts})
   return Event(output=f"Outline:\n{outline}", state={"outline": outline})


def review_post(ctx: Context, node_input: BlogPost):
   md = node_input.markdown
   problems = []
   if not md.lstrip().startswith("# "):
       problems.append("must start with an H1 title")
   if md.count("\n## ") < 4:
       problems.append("needs at least 4 H2 sections")
   if "conclusion" not in md.lower():
       problems.append("needs a conclusion")
   if len(md.split()) < 400:
       problems.append("is too short (under 400 words)")
   if len(node_input.alternate_titles) != 3:
       problems.append("needs exactly 3 alternate titles")
   if len(node_input.tweet_hooks) != 2:
       problems.append("needs exactly 2 tweet hooks")
   if any(len(h) > 250 for h in node_input.tweet_hooks):
       problems.append("tweet hooks must be under 250 characters")
   if "\n## alternate titles" in md.lower() or "\n## tweet hooks" in md.lower():
       problems.append("markdown must not contain alternate titles or tweet hooks; keep them in their own fields")

   attempts = ctx.state.get("post_attempts", 0) + 1
   if problems and attempts < MAX_ATTEMPTS:
       request = f"Outline:\n{ctx.state['outline']}"
       return Event(route="retry", output=_retry_prompt(request, problems, md), state={"post_attempts": attempts})
   return Event(output=node_input)


def format_post(node_input: BlogPost):
   titles = "\n".join(f"- {t}" for t in node_input.alternate_titles)
   hooks = "\n".join(f"- {h}" for h in node_input.tweet_hooks)
   return f"{node_input.markdown}\n\n---\n**Alternate titles**\n{titles}\n\n**Hooks**\n{hooks}"


# ── Graph: plan ⇄ review → write ⇄ review → format ───────────────────────────
root_agent = Workflow(
   name="root_agent",
   edges=[
       ("START", remember_topic, blog_planner, review_outline),
       (review_outline, {"retry": blog_planner, DEFAULT_ROUTE: blog_writer}),
       (blog_writer, review_post),
       (review_post, {"retry": blog_writer, DEFAULT_ROUTE: format_post}),
   ],
)
