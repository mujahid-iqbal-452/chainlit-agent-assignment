import os
from dotenv import load_dotenv
from agents import(Agent, Runner, AsyncOpenAI, OpenAIChatCompletionsModel,set_tracing_disabled , function_tool, set_default_openai_client)

load_dotenv()
set_tracing_disabled(disabled = True)

BASE_URL =  os.getenv("BASE_URL")
GEMINI_kEYGEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

ext_client: AsyncOpenAI = AsyncOpenAI(
    base_url = BASE_URL,
    api_key = GEMINI_kEYGEMINI_API_KEY,
    )

model: OpenAIChatCompletionsModel = OpenAIChatCompletionsModel (
    model="gemini-2.5-flash",
    openai_client = ext_client,
    )
agent: Agent=Agent (
    name="Assistent",
    instructions= "You are helper assistent",
    model= model,
    )

if __name__ == "__main__":
    prompt ="What is Capital of Pakistan"
    result = Runner.run_sync(agent,prompt)
    print(result.final_output)