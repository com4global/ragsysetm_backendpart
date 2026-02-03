





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
        "For every answer, You MUST start your answer by naming the document you are using. For example: 'According to [HRPolicy.pdf], the policy is... Document Name, Path and Page/Timestamp. "

        "If the answer is not in the context, say you don't have information on that."
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

# --- Keep your original function ---
# def ask_llm(transcript: str, question: str) -> str:
#     system_prompt = (
#         "You answer questions about a YouTube video transcript using ONLY the transcript. "
#         "Include timestamps if available."
#     )
#     user_prompt = f"TRANSCRIPT:\n{transcript}\n\nQUESTION:\n{question}\n\nFormat:\nAnswer:\nTimestamps:"
    
#     response = client.chat.completions.create(
#         model=MODEL,
#         messages=[
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": user_prompt},
#         ],
#         temperature=0.2,
#     )
#     return response.choices[0].message.content

# # --- NEW: Function for your HR RAG ---
# def query_llm_with_context(question: str, context: str) -> str:
#     system_prompt = (
#         "You are a professional HR Assistant. Answer the user's question using ONLY the provided context. "
#         "If the answer is not in the context, say you don't know based on company documents. "
#         "Be concise and helpful."
#     )

#     user_prompt = f"""
# CONTEXT FROM COMPANY DOCUMENTS:
# {context}

# USER QUESTION:
# {question}
# """

#     response = client.chat.completions.create(
#         model=MODEL,
#         messages=[
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": user_prompt},
#         ],
#         temperature=0, # Lower temperature is better for factual HR answers
#     )

#     return response.choices[0].message.content



# import os
# from dotenv import load_dotenv
# from openai import OpenAI

# load_dotenv()

# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# MODEL = "gpt-4o-mini"

# def ask_llm(transcript: str, question: str) -> str:
#     system_prompt = (
#         "You answer questions about a YouTube video transcript using ONLY the transcript. "
#         "Include timestamps if available."
#     )

#     user_prompt = f"""
# TRANSCRIPT:
# {transcript}

# QUESTION:
# {question}

# Format:
# Answer:
# Timestamps:
# """

#     response = client.chat.completions.create(
#         model=MODEL,
#         messages=[
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": user_prompt},
#         ],
#         temperature=0.2,
#     )

#     return response.choices[0].message.content



# from openai import OpenAI
# from dotenv import load_dotenv
# import os

# load_dotenv()

# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# def query_llm_with_context(query: str, context: str):
#     system_content = """You are a professional assistant. Answer based ONLY on the context.
#     For every fact you state, you MUST provide a citation in this format: [Document Name, Page X].
#     If the context is an Excel file, use [Document Name, Row X].
#     """
#     response = client.chat.completions.create(
#         model="gpt-3.5-turbo",
#         messages=[
#             {"role": "system", "content": system_content},
#             {"role": "user", "content": f"Query: {query}\n\nContext:\n{context}"}
#         ],
#         temperature=0.4
#     )
#     return response.choices[0].message.content
