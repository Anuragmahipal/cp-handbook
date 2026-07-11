# Architecture

The implementation is divided into independent layers.


Capture Layer

↓

Knowledge Layer

↓

Learning Layer

↓

Rendering Layer

↓

Interface Layer


---

## Capture Layer

Collects information.

Sources:

- Codeforces

- AtCoder

- LeetCode

- Manual

- AI Conversation

---

## Knowledge Layer

Stores structured knowledge.

Objects:

Problem

Algorithm

Pattern

Mistake

Contest

Concept

Relations

---

## Learning Layer

Transforms knowledge into learning.

Responsibilities:

- mistake detection

- duplicate detection

- graph updates

- revision scheduling

- mastery estimation

- learning analytics

---

## Rendering Layer

Converts knowledge into outputs.

Markdown

Canvas

Handwritten Notes

Flashcards

PDF

Slides

Interactive Pages

---

## Interface Layer

Everything the user interacts with.

CLI

Desktop

Tablet

Phone

AI Chat

Notebook

---

# Design Principles

Knowledge is renderer independent.

Every renderer consumes the same learning representation.

Never duplicate knowledge.

Never regenerate entire notebooks.

Only evolve existing knowledge.

The graph is the source of truth.

Renderers are disposable.