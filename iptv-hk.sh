#!/bin/bash
# 从远程 m3u 提取港澳台直播源
# 用法: ./iptv-hk.sh [输出目录]

SOURCE_URL="https://raw.githubusercontent.com/Jsnzkpg/Jsnzkpg/Jsnzkpg/Jsnzkpg1.m3u"
OUTPUT_DIR="${1:-/mnt/Configs/IPTV/output/lighttps/root}"
OUTPUT="$OUTPUT_DIR/got.m3u"

# 确保输出目录存在
mkdir -p "$OUTPUT_DIR"

# 下载源文件
tmpfile=$(mktemp)
curl -sL "$SOURCE_URL" -o "$tmpfile"

if [ ! -s "$tmpfile" ]; then
  echo "❌ 下载失败"
  rm -f "$tmpfile"
  exit 1
fi

# 提取 #EXTM3U 头 + 港澳台直播 + [备用]港澳台直播分组
{
  head -1 "$tmpfile"
  awk '/🔮港澳台直播|\[备用\]港澳台直播/{found=1; print; next} /^#EXTINF/{found=0} found' "$tmpfile" | sed 's/央视综合/RTHK33/g'
} > "$OUTPUT"

rm -f "$tmpfile"

count=$(grep -c '#EXTINF' "$OUTPUT")
echo "✅ 已提取 $count 个港澳台频道 → $OUTPUT"
