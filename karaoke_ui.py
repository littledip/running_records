"""Karaoke-style read-along player: an <audio> element synced to per-word
highlighting of a target passage, rendered via streamlit.components.v1.

Streamlit-facing (unlike src/karaoke.py, which stays pure). Mirrors the
placement of ui.py/utils.py alongside the Streamlit-free src/ core.
"""
import base64
import html
from typing import List, Optional, Tuple

import streamlit.components.v1 as components

_TEMPLATE = """
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;">
  <audio id="kw-audio" controls src="{audio_src}" style="width: 100%;"></audio>
  <div id="kw-text" style="margin-top: 12px; line-height: 1.9; font-size: 1.05rem;
       max-height: {text_max_height}px; overflow-y: auto;">
    {spans_html}
  </div>
</div>
<style>
  .kw {{ padding: 1px 2px; border-radius: 3px; }}
  .kw.current {{ background-color: #fff59d; }}
  .kw-untimed {{ opacity: 0.55; }}
</style>
<script>
(function() {{
  const audio = document.getElementById('kw-audio');
  const spans = Array.from(document.querySelectorAll('#kw-text .kw'));
  const timings = spans.map(function(s) {{
    return {{ el: s, start: parseFloat(s.dataset.start), end: parseFloat(s.dataset.end) }};
  }});
  let activeEl = null;

  function clearActive() {{
    if (activeEl) {{ activeEl.classList.remove('current'); activeEl = null; }}
  }}

  audio.addEventListener('timeupdate', function() {{
    const t = audio.currentTime;
    let match = null;
    for (let i = 0; i < timings.length; i++) {{
      if (timings[i].start <= t) {{ match = timings[i]; }} else {{ break; }}
    }}
    if (match && t > match.end) {{
      const idx = timings.indexOf(match);
      const next = timings[idx + 1];
      if (next && t >= next.start) {{ match = next; }}
    }}
    if (match && match.el !== activeEl) {{
      clearActive();
      match.el.classList.add('current');
      activeEl = match.el;
      activeEl.scrollIntoView({{block: 'nearest', behavior: 'smooth'}});
    }} else if (!match) {{
      clearActive();
    }}
  }});

  audio.addEventListener('seeking', clearActive);
}})();
</script>
"""


def render_karaoke_player(
    target_text: str,
    audio_bytes: bytes,
    audio_mime: str,
    word_timings: List[Optional[Tuple[float, float]]],
    height: int = 250,
) -> None:
    """Render an <audio> player with word-by-word highlighting of target_text
    synced to playback."""
    words = target_text.split()
    if not words:
        return

    spans = []
    for word, timing in zip(words, word_timings):
        escaped = html.escape(word)
        if timing is not None:
            start, end = timing
            spans.append(f'<span class="kw" data-start="{start}" data-end="{end}">{escaped}</span>')
        else:
            spans.append(f'<span class="kw-untimed">{escaped}</span>')

    audio_mime = audio_mime or "audio/wav"
    b64 = base64.b64encode(audio_bytes).decode("ascii")
    audio_src = f"data:{audio_mime};base64,{b64}"

    full_html = _TEMPLATE.format(
        audio_src=audio_src,
        spans_html=" ".join(spans),
        text_max_height=max(height - 80, 80),
    )
    components.html(full_html, height=height, scrolling=True)
