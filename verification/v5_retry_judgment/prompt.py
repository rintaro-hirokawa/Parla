"""V5: プロンプトテンプレート."""

SYSTEM_PROMPT_TEMPLATE = """\
音声がターゲット文と一致しているか判定せよ。
許容: 冠詞(a/an/the)の欠落・誤用、三単現-sの欠落、短縮形(I'll=I will)。
不一致: 上記以外の単語の違い、語の欠落、日本語の混入、文の未完成。
出力: JSON {{"correct": bool, "reason": "日本語15文字以内"}}\
"""

USER_PROMPT_TEMPLATE = """\
ターゲット文: {reference_answer}\
"""
