import OpenAI from "openai";

const client = new OpenAI();

export async function interpretCard(card: string, question: string): Promise<string> {
  const response = await client.chat.completions.create({
    model: "gpt-4o",
    messages: [
      {
        role: "system",
        content:
          "당신은 전문 타로 카드 리더입니다. 카드의 의미를 깊이 있게 해석하여 사용자에게 통찰을 제공하세요. Major Arcana와 Minor Arcana 모두에 정통하며, Celtic Cross 스프레드 해석에 특히 능숙합니다.",
      },
      { role: "user", content: `카드: ${card}\n질문: ${question}` },
    ],
  });
  return response.choices[0].message.content ?? "";
}

export async function dailyReading(birthday: string): Promise<string> {
  const response = await client.chat.completions.create({
    model: "gpt-4o-mini",
    messages: [
      {
        role: "system",
        content:
          "오늘의 타로 운세를 봐드립니다. 생년월일을 바탕으로 오늘 하루의 에너지와 조언을 전달합니다.",
      },
      { role: "user", content: `생년월일: ${birthday}` },
    ],
  });
  return response.choices[0].message.content ?? "";
}
