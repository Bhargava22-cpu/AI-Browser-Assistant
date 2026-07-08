import json
import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver
from tools import navigate_to, click_element, type_text, get_page_text, close_browser
from high_level_tools import fill_form_tool, compose_email_draft_tool, create_calendar_draft_tool

load_dotenv()

PROFILE_PATH = Path(__file__).parent.parent.parent / "week1" / "data" / "user_profile.json"


def load_user_profile() -> dict:
    if not PROFILE_PATH.exists():
        raise FileNotFoundError(f"Profile not found: {PROFILE_PATH}")
    with open(PROFILE_PATH) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(f"Invalid profile JSON: {e.msg}", e.doc, e.pos)


def build_agent():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY not set in .env")

    profile = load_user_profile()

    model = os.getenv("GROQ_MODEL", "qwen/qwen3-32b")
    llm = ChatGroq(api_key=api_key, model=model, temperature=0)
    tools = [
        navigate_to,
        click_element,
        type_text,
        get_page_text,
        fill_form_tool,
        compose_email_draft_tool,
        create_calendar_draft_tool,
    ]
    memory = MemorySaver()

    system_prompt = f"""You are an AI browser agent. You control a real browser to complete tasks.

Low-level browser control:
- navigate_to, click_element, type_text — for raw page interaction.
- get_page_text — reads the actual visible text of the current page (or one
  selector's subtree). Use this whenever you need to know what's ON a page —
  to answer a question, list results, or summarize content. Do NOT guess an
  answer from a page title alone; call get_page_text and read it first.
  Default to passing an empty string (reads the whole page) so you see
  everything in one call — only pass a specific CSS selector if you already
  know the page structure. Don't guess narrow selectors one at a time; that
  wastes calls and often misses content.

High-level module tools:
- fill_form_tool — detects every field on a form page and fills it from the user's
  saved profile (optionally navigating there first). Never submits the form.
- compose_email_draft_tool — drafts (but never sends) an email to a literal address.
  Sending only ever happens after the user clicks Send in the UI — never claim an
  email was "sent"; it is only "drafted" until the user confirms.
- create_calendar_draft_tool — drafts (but never creates) a calendar event from a
  natural language scheduling phrase, including recurring events ("every day for
  2 weeks"). Creation only ever happens after the user clicks Confirm in the UI —
  never claim an event was "added to the calendar"; it is only "drafted" until the
  user confirms.

Prefer the high-level tools over raw clicking/typing when the task is "fill this form",
"email someone", or "schedule/add an event" — they already know how to read forms,
profile data, and natural language dates. Chain tools across modules when a command
asks for more than one thing, e.g. "fill this form and then email my mentor that I
applied" should call fill_form_tool, then compose_email_draft_tool.

IMPORTANT: Call only ONE tool at a time. Wait for the result before calling the next tool.
Never batch multiple tool calls in one response — always call them one by one sequentially.
Do NOT include any explanatory text in the same response as a tool call — call the tool directly,
then explain the result in a follow-up message after you receive the tool's output.

How to present results: when your final answer lists multiple items — search results,
articles, headlines, options, steps — use a numbered or bulleted markdown list, one
item per line, not a dense paragraph. Keep each item to a short title/summary; leave
out raw boilerplate (ads, nav menus, cookie notices) that get_page_text may have
picked up. If get_page_text didn't return the content you needed (e.g. the page shows
a bot-check or login wall instead of real content), say that plainly instead of
inventing an answer from general knowledge.

Common selectors:
- Google search box: textarea[name="q"]
- Google search button: input[name="btnK"]

User profile (use when asked about the user's details):
{json.dumps(profile, indent=2)}"""

    agent = create_agent(
        llm,
        tools,
        checkpointer=memory,
        system_prompt=system_prompt,
        debug=True,
    )
    return agent


def run_task(agent, task: str, thread_id: str = "default") -> str:
    config = {"configurable": {"thread_id": thread_id}}
    result = agent.invoke(
        {"messages": [HumanMessage(content=task)]},
        config=config,
    )
    return result["messages"][-1].content


def main():
    agent = build_agent()

    tasks = [
        ("go to google.com and search for AI news", "thread-1"),
        ("what was the last page I visited?", "thread-1"),
    ]

    for task, thread_id in tasks:
        print(f"\n{'='*60}")
        print(f"Task: {task}")
        print("=" * 60)
        result = run_task(agent, task, thread_id)
        print(f"\nAgent: {result}")

    close_browser()


if __name__ == "__main__":
    main()
