# ArcanaInsight Mini — 타로 리딩 AI 서비스

> An AI-powered tarot reading service that interprets cards for your questions.

## 소개 (Introduction)

ArcanaInsight Mini는 사용자의 질문을 받아 타로 카드를 뽑고 AI가 해석해주는 서비스입니다. 수천 년의 역사를 가진 타로의 지혜와 최신 대형 언어 모델을 결합하여 개인 맞춤형 운세와 통찰을 제공합니다.

This service accepts user questions, draws tarot cards, and provides AI-generated interpretations. It combines the ancient wisdom of tarot divination with modern LLM technology to deliver personalized readings.

## 주요 기능 (Features)

### 🃏 카드 해석 (Card Interpretation)

Major Arcana 22장과 Minor Arcana 56장, 총 78장의 타로 카드 전체를 지원합니다. The Fool부터 The World까지 Major Arcana의 아르카나 상징 체계와 Wands, Cups, Swords, Pentacles 네 수트로 구성된 Minor Arcana를 모두 해석합니다.

The system supports all 78 tarot cards — 22 Major Arcana and 56 Minor Arcana — providing nuanced interpretations for each card in context.

### 🔮 Celtic Cross 스프레드 (Celtic Cross Spread)

가장 전통적이고 심층적인 타로 스프레드인 Celtic Cross를 지원합니다. 10장의 카드로 현재 상황, 장애물, 과거, 미래, 의식/무의식, 외부 영향, 희망과 두려움, 최종 결과까지 종합적으로 분석합니다.

The Celtic Cross is the most widely recognized tarot spread, offering a comprehensive 10-card layout that reveals the full picture of a situation — past influences, present circumstances, hidden factors, and likely outcomes.

### 📅 오늘의 운세 (Daily Reading)

생년월일 기반 개인 맞춤형 일일 타로 운세를 제공합니다. 매일 새로운 카드 에너지와 함께 하루를 시작하세요.

Get a personalized daily tarot reading based on your birth date. Each day brings new energies and guidance through the cards.

### 📓 타로 일기 (Tarot Journal)

나만의 타로 리딩 기록을 남기고 AI가 시간이 지남에 따라 패턴을 분석합니다. 반복되는 카드, 성장하는 에너지, 지속되는 테마를 발견해보세요.

Record your tarot readings over time and let the AI analyze patterns in your journey. Discover recurring cards, evolving energies, and persistent themes.

## 기술 스택 (Tech Stack)

- **Runtime**: Node.js + Python
- **LLM**: OpenAI GPT-4o (primary), Anthropic Claude (guidance)
- **Language**: TypeScript + Python
- **Domain**: divination, tarot reading, spiritual guidance

## 사용 방법 (Usage)

```bash
npm install
# Set OPENAI_API_KEY and ANTHROPIC_API_KEY in .env
npm run dev
```

```python
# Python backend
pip install anthropic
python -m app.daily
```

## 도메인 정보 (Domain)

이 서비스는 타로 점술(tarot divination)과 운세(fortune telling) 도메인에 속합니다. 신비주의적 전통과 현대 AI 기술을 결합하여 사용자에게 의미 있는 자기 성찰의 기회를 제공합니다.

This service operates in the tarot reading and divination domain, blending mystical tradition with AI to support meaningful self-reflection and guidance.

## 라이선스 (License)

MIT — see [LICENSE](LICENSE)
