async def read_notion_brand_guidelines(query: str) -> str:
    """
    Read-only. Searches the specific Notion 'Brand Guidelines' and 'SOPs' database.
    Use this to pull the ground-truth instructions for messaging.
    
    Args:
        query (str): The semantic search query for the brand guidelines.
    """
    try:
        # Placeholder for scoped Notion API / RAG hit.
        # Should rigidly filter to a specific Parent Page ID to ensure no leakage.
        if "tone" in query.lower():
            return "Brand Instruction: The tone must always be direct, data-focused, and never use exclamation points."
        return f"No specific guidelines found for '{query}' in the Brand Database."
    except Exception as e:
        return f'{{"error": "Notion retrieval failed: {str(e)}"}}'

cmo_tools = [read_notion_brand_guidelines]
