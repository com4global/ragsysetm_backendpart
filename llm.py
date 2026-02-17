





import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = "gpt-4o-mini"


def query_llm_with_context(question: str, context: str, language: str = "en") -> str:
    system_prompt = (
        "You are an intelligent assistant. Answer the question using the provided context blocks. "
        "Each block starts with 'Document:', 'Page:', and 'Path:'. "
        "For every answer based on context, You MUST start your answer by naming the document you are using. For example: 'According to [HRPolicy.pdf], the policy is...'. "
        
        "If the provided context does NOT contain the answer or is insufficient, answer the question using your general knowledge to the best of your ability. "
        "However, if you answer from general knowledge, you MUST preface your answer with: "
        "'Using my general knowledge (not from your documents):'. "
        "Do NOT simply say you don't have information unless you truly cannot answer at all."
    )

    # Add Tamil language instruction when requested
    if language == "ta":
        system_prompt += (
            "\n\nCRITICAL LANGUAGE INSTRUCTION: You MUST respond ENTIRELY in Tamil (தமிழ்). "
            "Use Tamil script for ALL text in your response. "
            "Document names and technical terms can remain in English, but all explanations, "
            "sentences, and descriptions must be in Tamil. "
            "For example, instead of 'According to [HRPolicy.pdf], the policy is...', "
            "say '[HRPolicy.pdf] படி, கொள்கை என்னவென்றால்...'. "
            "If answering from general knowledge, say: 'பொது அறிவிலிருந்து (உங்கள் ஆவணங்களிலிருந்து அல்ல):'"
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


