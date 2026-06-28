#!/bin/bash
# weekly-ai-news の下書きを自動生成する launchd 用ラッパー。
# 毎週日曜 8:00 に launchd（com.aidotters.weekly-ai-news）から起動される。
# create-blog-post スキルを headless（claude -p）で走らせ、docs/drafts/ に
# 下書きを保存するところまでを自動化する。WordPress/X 投稿は行わない。
set -uo pipefail

# launchd は最小環境で動くため、claude / uv のパスを明示する。
export PATH="/Users/tak/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

PROJECT_DIR="/Users/tak/Projects/social-content-creator"
LOG_DIR="$PROJECT_DIR/outputs/logs"
DRAFTS_DIR="$PROJECT_DIR/docs/drafts"

mkdir -p "$LOG_DIR"
TS="$(date +%Y%m%d-%H%M%S)"
LOG_FILE="$LOG_DIR/weekly-ai-news-$TS.log"

cd "$PROJECT_DIR" || { echo "cd failed: $PROJECT_DIR"; exit 1; }

# 実行前の下書き数（後で増えたか検証する）
before="$(find "$DRAFTS_DIR" -name '*.md' 2>/dev/null | wc -l | tr -d ' ')"

PROMPT='/create-blog-post --type weekly-ai-news'
SYS='このセッションは非対話の自動実行です。weekly-ai-news の記事を生成し docs/drafts/ に下書き保存する（create-blog-post スキルのステップ1〜3）まで実行してください。ステップ4のWordPress投稿・X投稿・アイキャッチ画像生成は絶対に実行しないこと。ユーザーへの確認が必要な箇所は質問せず、最も標準的で妥当な判断を採用して最後まで完了させてください。'

{
  echo "=== weekly-ai-news auto run: $TS ==="
  claude -p "$PROMPT" \
    --append-system-prompt "$SYS" \
    --max-turns 200 \
    --output-format text \
    --allowedTools Bash WebSearch WebFetch Read Write Edit Glob Grep TodoWrite Skill
  rc=$?
  echo ""
  echo "=== claude exit code: $rc ==="
} >> "$LOG_FILE" 2>&1

# 下書きが実際に増えたか検証（headless は無言で失敗しうるため）
after="$(find "$DRAFTS_DIR" -name '*.md' 2>/dev/null | wc -l | tr -d ' ')"
if [ "$after" -gt "$before" ]; then
  echo "OK: 下書きが作成されました ($before -> $after)" >> "$LOG_FILE"
else
  echo "WARN: 下書きが増えていません ($before -> $after)。$LOG_FILE を確認してください。" >> "$LOG_FILE"
  osascript -e 'display notification "下書きが作成されませんでした。ログを確認してください。" with title "weekly-ai-news 自動生成"' 2>/dev/null || true
fi
