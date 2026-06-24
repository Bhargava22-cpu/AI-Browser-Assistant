import json
import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver
from tools import navigate_to, click_element, type_text, close_browser

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
    tools = [navigate_to, click_element, type_text]
    memory = MemorySaver()

    system_prompt = f"""You are an AI browser agent. You control a real browser to complete tasks.
Use the navigate_to, click_element, and type_text tools to interact with the browser.

IMPORTANT: Call only ONE tool at a time. Wait for the result before calling the next tool.
Never batch multiple tool calls in one response — always call them one by one sequentially.
Do NOT include any explanatory text in the same response as a tool call — call the tool directly,
then explain the result in a follow-up message after you receive the tool's output.

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
