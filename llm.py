





import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = "gpt-4o-mini"


def query_llm_with_context(question: str, context: str) -> str:
    system_prompt = (
        "You are an intelligent assistant. Answer the question using the provided context blocks. "
        "Each block starts with 'Document:', 'Page:', and 'Path:'. "
        "For every answer based on context, You MUST start your answer by naming the document you are using. For example: 'According to [HRPolicy.pdf], the policy is...'. "
        
        "If the provided context does NOT contain the answer or is insufficient, answer the question using your general knowledge to the best of your ability. "
        "However, if you answer from general knowledge, you MUST preface your answer with: "
        "'Using my general knowledge (not from your documents):'. "
        "Do NOT simply say you don't have information unless you truly cannot answer at all."
    )

    user_prompt = f"CONTEXT:\n{context}\n\nUSER QUESTION:\n{question}"

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )
    return response.choices[0].message.content


