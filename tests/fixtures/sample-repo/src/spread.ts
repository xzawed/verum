import Anthropic from "@anthropic-ai/sdk";

const anthropic = new Anthropic();

export async function analyzeCelticCross(cards: string[]): Promise<string> {
  const message = await anthropic.messages.create({
    model: "claude-opus-4-5",
    max_tokens: 1024,
    messages: [
      {
        role: "user",
        content: `Celtic Cross 스프레드 해석을 부탁드립니다. 카드: ${cards.join(", ")}`,
      },
    ],
    system:
      "당신은 타로 전문가입니다. Celtic Cross 10장 배열을 깊이 있게 해석합니다.",
  });
  return message.content[0].type === "text" ? message.content[0].text : "";
}
