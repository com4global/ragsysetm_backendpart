





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
            "\n\nCRITICAL LANGUAGE INSTRUCTION: You MUST respond in THANGLISH style. "
            "Use Tamil script (தமிழ்) as the primary language, but mix in English words "
            "naturally for technical terms, greetings, and common phrases. "
            "Use everyday conversational Tamil, NOT formal literary Tamil. "
            "Example: '[HRPolicy.pdf] படி, இந்த policy-ன் main point என்னன்னா...' "
            "Document names and technical terms can stay in English. "
            "If answering from general knowledge, say: 'General knowledge-லிருந்து (உங்க documents-ல இல்ல):' "
            "Keep the tone friendly and easy to understand like daily Tamil conversation."
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


