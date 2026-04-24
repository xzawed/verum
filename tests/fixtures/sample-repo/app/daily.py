import anthropic

client = anthropic.Anthropic()


async def get_tarot_guidance(question: str, cards: list[str]) -> str:
    """Get tarot card guidance for a user question."""
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system="당신은 수십 년의 경험을 가진 타로 마스터입니다. Celtic Cross 스프레드와 Major Arcana, Minor Arcana의 상징적 의미를 깊이 이해하고 있습니다. 사용자의 질문에 타로 카드의 에너지를 담아 진심 어린 통찰을 제공하세요.",
        messages=[
            {"role": "user", "content": f"질문: {question}\n뽑은 카드: {', '.join(cards)}"}
        ],
    )
    return response.content[0].text
