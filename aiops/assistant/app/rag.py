"""RAG — 检索增强生成：用运维知识库提升回答准确性、降低幻觉。

MVP 实现：
  - 用简单的关键词向量检索（TF-IDF 风格的词频打分）作为占位，
    后续可平滑替换为 Chroma / pgvector / embedding。
  - 知识库文档放在 knowledge/ 目录的 .md 文件中。
"""
import os
import re
import glob
from collections import Counter

KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "..", "knowledge")


def _load_docs():
    docs = []
    for path in glob.glob(os.path.join(KNOWLEDGE_DIR, "*.md")):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        # 按段落分割，作为检索单元
        for para in re.split(r"\n\s*\n", text):
            para = para.strip()
            if len(para) > 30:
                docs.append({"source": os.path.basename(path), "text": para})
    return docs


def _tokenize(text: str) -> Counter:
    """分词：英文/数字按词切分，中文切 2-gram（重叠）。

    注意：不能用 r"[\\w\\u4e00-\\u9fa5]+" 直接匹配——那样会把整段连续中文当成
    一个 token，导致中文提问与知识库段落几乎不可能有交集，检索恒为空。
    """
    text = text.lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    for seg in re.findall(r"[\u4e00-\u9fa5]+", text):
        if len(seg) == 1:
            tokens.append(seg)
        else:
            # 2-gram 重叠切分：「节点不可用」→ 节点/点不/不可/可用
            tokens.extend(seg[i:i + 2] for i in range(len(seg) - 1))
    return Counter(tokens)


def rag_search(query: str, top_k: int = 3) -> list:
    docs = _load_docs()
    if not docs:
        return []
    q_tokens = _tokenize(query)
    scored = []
    for d in docs:
        d_tokens = _tokenize(d["text"])
        # 简单共享词打分（可替换成向量相似度）
        score = sum(min(c, d_tokens[w]) for w, c in q_tokens.items())
        scored.append((score, d))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [d for s, d in scored[:top_k] if s > 0]
