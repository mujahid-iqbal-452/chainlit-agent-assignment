from config import Config
import chainlit as cl
import os, json, asyncio,aiohttp
from datetime import datetime
from typing import Dict, List, Optional
from agents import (Agent, Runner, AsyncOpenAI, OpenAIChatCompletionsModel,
                    function_tool, set_default_openai_client, ItemHelpers,set_tracing_disabled)


set_tracing_disabled(disabled=True)

# ----------  Config values  ----------
BASE_URL   = Config.BASE_URL
GEMINI_API_KEY = Config.GEMINI_API_KEY
WEATHER_API_KEY = Config.WEATHER_API_KEY 
WEATHER_URL     = Config.WEATHER_URL


# ----------  general current-tab memory  ----------
USER_FACTS: Dict[str, str] = {}

def extract_facts(text: str) -> None:
    t = text.lower()
    for a,b in (("my name is ", "name"), ("i am ", "name")):
        if t.startswith(a):
            USER_FACTS[b] = text[len(a):].strip().title()
# ----------------------------------------------------

# Rebuild agent instructions including current known facts
def rebuild_instructions() -> str:
    base = (
        "You are a helpful assistant. "
        "Answer in as much detail as requested; do not refuse purely because the answer is long. "
        "Use the weather tool for weather questions and the calculator for arithmetic. "
        "Answer every other question normally."
    )

    if USER_FACTS:
        base += f"\nUser facts you already know: {'; '.join(f'{key}: {val}' for key, val in USER_FACTS.items())}"
        # print(base)    
    return base
# ----------------------------------------------------

# ----  "did I ask/mention about X?"  ----  
def was_topic_asked(history: List[Dict], keyword: str) -> Optional[str]:
    print(  f"Searching for previous mentions of '{keyword}' in history..."  )  
    kw = keyword.strip().lower()
    for entry in history:
        if kw in entry["user_message"].strip().lower():
            return entry["user_message"]
    return None
# ----------------------------------------------------

# ----------  Define Tools  ----------
@function_tool
async def get_weather(city: str) -> str:
    """
    Return current weather for <city>.
    city: e.g. "Lahore" or "Karachi" etc.
    """
    print("Tool called: get_weather")
    params = {"q": city, "appid": WEATHER_API_KEY, "units": "metric"}  # Celsius
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(WEATHER_URL, params=params) as resp:
                if resp.status != 200:
                    return f"Error {resp.status}: Unable to fetch weather. Check city name."
                data = await resp.json()
                temp = data["main"]["temp"]
                desc = data["weather"][0]["description"]
                return f"{city}: {temp}°C, {desc}."
    except Exception as e:
        return f"⚠️ Weather fetch failed: {str(e)}"


        
@function_tool
def calculator(operation: str, a: float, b: float) -> str:
    print("Tool called: calculator")
    match operation.lower():
        case "add":      return str(a + b)
        case "subtract": return str(a - b)
        case "multiply": return str(a * b)
        case "divide":   return str(a / b) if b != 0 else "Error: division by zero"
        case _:          return "Error: unsupported operation"
# ----------------------------------------------------

# ----------  Agent setup  ----------
ext_client = AsyncOpenAI(
    base_url=BASE_URL,
    api_key=GEMINI_API_KEY,
    )
set_default_openai_client(ext_client)
model = OpenAIChatCompletionsModel(model="gemini-2.5-flash", openai_client=ext_client)

# ----------  Define the Agent  ----------
agent = Agent(
    name="Assistent",
    instructions=rebuild_instructions(),
    model=model,
    tools=[calculator,get_weather],
)

# ----------  Chainlit event handlers  ----------
# Define some message templates for starter buttons
TEMPLATES = {
    "Greeting": "Hello! Introduce yourself politely and ask how you can help today.",
    "Math demo": "Explain step-by-step how to add the fractions 3/4 + 5/6.",
    "Creative story": "Write a 500-word fantasy story that includes a dragon and a calculator.",
}

# ====== NEW: Starter Buttons ======
@cl.set_starters
async def set_starters():
    """Define quick-start buttons shown when chat starts."""
    starters = [
        cl.Starter(
            label="👋 Greeting",
            message=TEMPLATES["Greeting"],
            icon="💬"
        ),
        cl.Starter(
            label="🧮 Math Demo",
            message=TEMPLATES["Math demo"],
            icon="🧠"
        ),
        cl.Starter(
            label="🐉 Creative Story",
            message=TEMPLATES["Creative story"],
            icon="✨"
        ),
    ]
    return starters
# ---------------------------------------------

# Active on user message received from chainlit frontend
@cl.on_message
async def main(message: cl.Message):
    history: List[Dict] = cl.user_session.get("history", [])

    # ----  "did I ask/mention about X?"  ----
    print(f"User message: '{message.content}'")
    if message.content.lower().startswith("did i ask"):
        topic = message.content[10:].strip().lstrip("about").strip().rstrip("?")
        print(f"Extracted topic: '{topic}'")
        prev = was_topic_asked(history, topic)
        ans = f'Yes, you said: "{prev}"' if prev else f"No, you haven't mentioned {topic}."
        
        await cl.Message(content=ans, author="Assistant").send()
        return

    # ----  Update known facts and instructions  ----
    extract_facts(message.content)
    agent.instructions = rebuild_instructions()

    # ----  normal agent flow  ----
    msg = cl.Message(content="", author="Assistant")
    # await msg.send()
    thinking_step = cl.Step(type="tool", name="Thinking…")
    await thinking_step.send()
    
#   ---  Run the agent and stream response  ----
    full = ""
    result = Runner.run_streamed(starting_agent=agent, input=message.content)
    async for event in result.stream_events():
        if hasattr(event, "item") and event.item.type == "message_output_item":
            full += ItemHelpers.text_message_output(event.item)
            # await msg.stream_token(full)
            # await asyncio.sleep(0.25)  # simulate streaming delay using sleep
            await thinking_step.remove()

    for line in full.splitlines(keepends=True):
        await msg.stream_token(line)
        await asyncio.sleep(0.25)  # simulate streaming delay using sleep
    await msg.update()

    # "Appending current session to history..."    
    history.append({
        "timestamp": datetime.now().isoformat() + "Z",
        "user_message": message.content,
        "assistant_response": msg.content,
        "agent_name": agent.name,
    })
    cl.user_session.set("history", history)

# -----  On chat end: save history to file  ----------
@cl.on_chat_end
async def on_end():
    print("Chat ended, saving history..."    )
    hist = cl.user_session.get("history", [])

    if not hist:
        return
    # os.makedirs("runs", exist_ok=True)
    timestamp = datetime.now().strftime("%d%m%Y_%H%M%S")
    filename = f"runs/chat_{timestamp}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(hist, f, indent=2)
    print(f"Current chat saved to {filename}")