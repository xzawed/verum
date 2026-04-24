export async function saveJournalEntry(entry: string, apiKey: string): Promise<string> {
  const resp = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "gpt-4o",
      messages: [
        {
          role: "system",
          content: "사용자의 타로 일기를 분석하여 패턴과 성장을 찾아주세요.",
        },
        { role: "user", content: entry },
      ],
    }),
  });
  const data = await resp.json();
  return data.choices[0].message.content;
}
