import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = "gpt-4o-mini"

def analyze_legal_document(text_content: str) -> dict:
    """
    Analyze a legal document using LLM
    
    Args:
        text_content: The text content of the document
        
    Returns:
        JSON dictionary with analysis
    """
    system_prompt = (
        "You are an expert Legal AI Assistant. Your task is to analyze the provided legal document "
        "and return a structured analysis in JSON format.\n"
        "The analysis MUST include:\n"
        "1. 'summary': A brief summary of the document (max 3 sentences).\n"
        "2. 'key_clauses': A list of key clauses or terms found.\n"
        "3. 'risks': A list of potential risks or liabilities.\n"
        "4. 'entities': A list of involved parties/entities.\n"
        "5. 'audit_score': A score from 0-100 indicating document completeness/safety (100 = safe).\n"
        "\n"
        "Return ONLY valid JSON. Do not include markdown formatting like ```json."
    )

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze this legal document:\n\n{text_content[:15000]}"} # Limit context if needed
            ],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        print(f"Legal analysis error: {e}")
        return {
            "error": "Failed to analyze document",
            "details": str(e)
        }
