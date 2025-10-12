# AI Slayd Bot

Telegram bot for creating AI-powered presentations using ChatGPT and PowerPoint generation.

## Features

- 🤖 AI-powered content generation using OpenAI GPT
- 📊 Professional presentation creation
- 📝 Independent works (essays, reports, articles)
- 🎮 Interactive magic game
- 💰 User balance and statistics
- 📞 Contact support

## Railway Deployment

This bot is configured to run on Railway platform.

### Environment Variables

Set these environment variables in Railway:

- `BOT_TOKEN` - Telegram bot token from @BotFather
- `OPENAI_API_KEY` - OpenAI API key for content generation
- `RAILWAY_STATIC_URL` - Railway static URL (automatically set)
- `PORT` - Port number (automatically set by Railway)

### Local Development

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Create `.env` file with required environment variables
4. Run: `python run_bot.py` (for polling) or `python main.py` (for webhook)

### Railway Setup

1. Connect your GitHub repository to Railway
2. Set environment variables in Railway dashboard
3. Deploy automatically

## Bot Commands

- `/start` - Start the bot and see main menu
- `/stats` - View user statistics

## Main Menu Options

1. 📊 Taqdimot tayyorlash - Create presentations
2. 📝 Mustaqil ishlar - Independent works
3. 🔧 Boshqa xizmatlar - Other services
4. 🎮 Sehrli o'yin - Magic game
5. 💰 Balansim - User balance
6. ℹ️ Bot haqida - About bot
7. 📞 Aloqa uchun - Contact us

## Contact

- Telegram: @ai_slaydbot
- Email: ai.slayd.bot@gmail.com
