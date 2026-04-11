---
id: V13
title: Phase A 画面デザイン再現
priority: P3
category: UI
related_llm_calls: []
related_requirements: ["09-ux-screens.md", "02-learning-cycle.md"]
status: not_started
result: null
---

# V13: Phase A 画面デザイン再現

## 問い

デザイナーが作成した Phase A 発話画面の HTML モックアップ (`docs/design/phase_a_mockup.html`) を、PySide6 + QSS でどこまで忠実に再現できるか?

## 背景

現在の PySide6 実装はデザイン面で課題がある。デザイナーに HTML 形式でモックアップを作成してもらったため、PySide6 での再現可能性を検証する。

## 検証内容

- HTML の全 UI 要素（TopBar, TimeBar, ドット進捗, 文カルーセル, ヒント, 波形, 録音ボタン）を PySide6 で再現
- QSS によるスタイリングの限界（box-shadow, transitions, scale 等）を把握
- QPainter によるカスタム描画（波形バー、録音ボタン）の実現性確認
- インタラクション（録音トグル、タイマー、ヒント表示、自動文切替）の動作確認

## 方針

- `src/` からは一切 import しない（完全スタンドアロン）
- `verification/v13_phase_a_ui_design/` に `main.py` 単一ファイルで実装
- 表示内容は HTML モックアップに準拠
