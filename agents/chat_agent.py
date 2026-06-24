import os
import streamlit as st

def generate_chat_response(prompt: str, context: dict) -> str:
    """
    Takes the user prompt and the dashboard context dictionary, and queries an LLM.
    Includes strict guardrails to prevent answering off-topic questions.
    """
    # Format the context into a readable string for the LLM
    context_str = "\n".join([f"- {k}: {v}" for k, v in context.items()])
    
    system_prompt = f"""You are the Chief Risk Officer Assistant for the Capital Risk Intelligence Platform (CRIP).
Your ONLY job is to answer questions based on the following risk dashboard reports:

=== RISK REPORTS CONTEXT ===
{context_str}
============================

STRICT GUARDRAILS:
1. You MUST NOT answer any questions that are unrelated to the dataset, risk, insurance, or the provided context.
2. If the user asks about coding, recipes, personal advice, or general knowledge, politely refuse and say:
   "I am an enterprise risk assistant. I can only answer questions pertaining to the currently loaded dataset and risk reports."
3. Be concise, professional, and data-driven in your answers.
"""
    
    # ---------------------------------------------------------
    # Connect to actual LLM API (OpenAI, Gemini, etc.)
    # ---------------------------------------------------------
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key == "your_api_key_goes_here":
        # Mock Response if no API key is provided yet
        return (
            "**[MOCK RESPONSE]**\n\n"
            f"I see you are asking about: *'{prompt}'*\n\n"
            "Here is the data I see in the context:\n"
            f"{context_str}\n\n"
            "*(Note: Once you add your real API key to `.env`, this will be a real AI response!)*"
        )
    
    # Example OpenAI Implementation (Requires `pip install openai`)
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error connecting to LLM: {str(e)}"
