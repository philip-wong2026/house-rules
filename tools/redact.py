#!/usr/bin/env python3
"""Keep sensitive text out of shared places (task lists, summaries, logs).

Shared places should hold categories, counts and pointers, not health, money, credential, ID or
address text. This is a KEYWORD filter (English and Chinese), not real privacy detection: text
of unknown origin should be stored as a pointer, never trusted because "nothing matched".

  import redact
  redact.find("my password is hunter2")        -> ['credential']
  redact.mask("blood pressure 150", "note 3")  -> "[contains suspected health content ...]"
CLI: python3 .space/redact.py "text to test"
Extra rules: config.json -> "sensitive_rules": [{"name": "project-code", "pattern": "ACME-\\d+"}]
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

RULES = [
    ("credential", r"密码|口令|passw|pwd|token|密钥|api[\s_-]?key|secret|验证码|otp|助记词|私钥|seed\s*phrase|mnemonic|"
                   r"private\s*key|\bsk-[a-z0-9]{6,}|bearer\s"),
    ("id-or-account", r"\d{12,}|(?<!\d)(?:\d{3,6}[\s\-‐‑–—]){2,}\d{2,6}(?!\d)|身份证|银行卡|卡号|护照|社保号|医保号|"
                      r"账号[:：]\s*\S|账户[:：]\s*\S|passport|ssn\b|iban|card\s*(no|number)"),
    ("health", r"病|诊断|症状|血压|血糖|血脂|尿酸|化验|体检|报告单|用药|服药|吃药|药物|药量|处方|医院|医生|门诊|急诊|住院|手术|"
               r"怀孕|孕检|抑郁|焦虑|失眠|过敏|癌|肿瘤|结节|心率|胆固醇|mg/dl|mmol|激素|心理咨询|治疗|"
               r"diabet|hiv\b|aids\b|cancer|tumou?r|depress|anxiety|insomnia|pregnan|diagnos|blood\s*(pressure|sugar|test)|"
               r"cholesterol|insulin|medicat|prescri|hospital|clinic|doctor|surgery|therap|disease|illness|allerg|symptom|disorder"),
    ("money", r"[$€£]\s?\d|\d[\d,.]*\s?[$€£]|\d[\d,.]*\s?(元|块钱|万元|万块|千元|美元|美金|刀|港币|港元|欧元|英镑|日元)|"
              r"\d[\d,.]*\s?(usd|rmb|cny|hkd|yuan|dollars?|bucks|eur)\b|(usd|rmb|cny|hkd|eur)\s?\d|"
              r"工资|薪水|年薪|月薪|收入|存款|余额|欠款|负债|贷款|借了|信用分|salary|income|balance|debt|loan"),
    ("address", r"住址|家庭地址|门牌|\d+\s?号楼|\d+\s?单元|\d+\s?室\b|邮编|address|street|\bapt\b|zip\s*code"),
]
LABELS = {"credential": "凭据", "id-or-account": "证件账号", "health": "健康", "money": "金额", "address": "住址"}


def compile_rules(extra=None):
    rules = list(RULES) + [(r["name"], r["pattern"]) for r in (extra or [])]
    return [(name, re.compile(pattern, re.I)) for name, pattern in rules]


_DEFAULT = compile_rules()


def normalize(text):
    """Full-width to half-width, currency signs unified, lower-case. Digits are not merged,
    so dates and task numbers are not mistaken for card numbers."""
    return unicodedata.normalize("NFKC", text or "").replace("￥", "$").replace("¥", "$").lower()


def find(text, compiled=None):
    compiled = compiled or _DEFAULT
    raw, norm = text or "", normalize(text)
    return [name for name, rule in compiled if rule.search(norm) or rule.search(raw)]


def mask(text, pointer="", compiled=None, lang="en"):
    hit = find(text, compiled)
    if not hit:
        return text
    if lang == "zh-CN":
        names = "、".join(LABELS.get(h, h) for h in hit)
        tail = f"；原话见 {pointer}" if pointer and not find(pointer, compiled) else "；原话见原件"
        return f"［含疑似{names}内容，正文不进公共区{tail}］"
    tail = f"; original at {pointer}" if pointer and not find(pointer, compiled) else "; original at its source"
    return f"[contains suspected {', '.join(hit)} content; text kept out of shared places{tail}]"


def for_root(root=ROOT):
    cfg = common.load_config(root)
    return compile_rules(cfg.get("sensitive_rules")), cfg["language"]


if __name__ == "__main__":
    common.stdio_utf8()
    text = " ".join(sys.argv[1:])
    compiled, language = for_root()
    print(find(text, compiled), mask(text, "test", compiled, language))
