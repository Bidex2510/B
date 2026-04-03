# TikTok AI Video Automation

Automatically generate and post AI-powered videos to TikTok daily.

## How It Works

1. **Script Generation** - GPT-4o writes a viral TikTok script with scene breakdowns
2. **Image Generation** - DALL-E 3 creates vertical (9:16) images for each scene
3. **Voiceover** - OpenAI TTS or ElevenLabs generates narration audio
4. **Video Composition** - MoviePy assembles images, text overlays, and audio into a video
5. **Auto Upload** - TikTok Content Posting API publishes the video

## Supported Niches

- `motivational` - Success, discipline, mindset
- `facts` - Science, history, nature
- `tech` - AI, programming, gadgets
- `finance` - Investing, saving, passive income
- `scary` - Urban legends, mysteries, paranormal

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Get API Keys

- **OpenAI**: Get a key at https://platform.openai.com/api-keys
- **TikTok**: Create an app at https://developers.tiktok.com/ with "Content Posting API" scope

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 4. Authenticate TikTok

```bash
python scripts/setup_tiktok_auth.py
```

This opens a browser for TikTok OAuth. The access token is printed to your console.

## Usage

### Generate + Upload One Video

```bash
python main.py --mode once --niche motivational
```

### Test Without Uploading

```bash
python main.py --mode test --niche facts
```

### Run Daily Scheduler

```bash
python main.py --mode schedule
```

This runs continuously, posting a new video at the time set in `.env` (default: 10:00 UTC).

### Run via GitHub Actions (Recommended)

The included GitHub Actions workflow runs daily at your configured time. Set your API keys as repository secrets:

- `OPENAI_API_KEY`
- `TIKTOK_CLIENT_KEY`
- `TIKTOK_CLIENT_SECRET`
- `TIKTOK_ACCESS_TOKEN`

## Project Structure

```
├── main.py                  # Entry point
├── config/
│   └── settings.py          # Configuration
├── src/
│   ├── script_generator.py  # GPT-4o script generation
│   ├── image_generator.py   # DALL-E 3 image generation
│   ├── voiceover.py         # TTS voiceover (OpenAI / ElevenLabs)
│   ├── video_composer.py    # MoviePy video assembly
│   ├── tiktok_uploader.py   # TikTok API upload
│   └── pipeline.py          # Full pipeline orchestration
├── scripts/
│   └── setup_tiktok_auth.py # TikTok OAuth helper
└── .github/
    └── workflows/
        └── daily_video.yml  # GitHub Actions daily cron
```
