# Project Context: AI-Powered Restaurant Recommendation System

This document captures the full context from the project problem statement. Use it as persistent reference when designing, implementing, or extending the application.

## Overview

Build an **AI-powered restaurant recommendation service** inspired by Zomato. The system suggests restaurants based on user preferences by combining **structured restaurant data** with a **Large Language Model (LLM)** to produce personalized, human-like recommendations.

## Objective

Design and implement an application that:

1. Accepts user preferences (location, budget, cuisine, ratings, and more)
2. Uses a real-world restaurant dataset
3. Leverages an LLM to generate personalized, natural-language recommendations
4. Displays clear, useful results to the user

## Data Source

| Item | Detail |
|------|--------|
| Dataset | Zomato restaurant data on Hugging Face |
| URL | https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation |
| Relevant fields | Restaurant name, location, cuisine, cost, rating, and related attributes |

## System Workflow

### 1. Data Ingestion

- Load and preprocess the Zomato dataset from Hugging Face
- Extract fields needed for filtering and display: name, location, cuisine, cost, rating, etc.

### 2. User Input

Collect preferences from the user:

| Preference | Examples / notes |
|------------|------------------|
| Location | e.g. Delhi, Bangalore |
| Budget | low, medium, high |
| Cuisine | e.g. Italian, Chinese |
| Minimum rating | numeric threshold |
| Additional | e.g. family-friendly, quick service |

### 3. Integration Layer

- Filter and prepare restaurant records that match user input
- Pass structured, filtered results into an LLM prompt
- Design prompts so the LLM can **reason** and **rank** options effectively

### 4. Recommendation Engine (LLM)

The LLM should:

- **Rank** restaurants against user preferences
- **Explain** why each recommendation fits
- **Optionally** summarize the overall set of choices

### 5. Output Display

Present top recommendations in a user-friendly format. Each result should include:

- Restaurant name
- Cuisine
- Rating
- Estimated cost
- AI-generated explanation (why it was recommended)

## Architectural Implications

| Layer | Responsibility |
|-------|----------------|
| Data pipeline | Hugging Face load, clean, normalize fields |
| Preference capture | UI or CLI for location, budget, cuisine, rating, extras |
| Filtering | Rule-based or query-based subset before LLM |
| LLM service | Prompt construction, ranking, explanations, optional summary |
| Presentation | Formatted list of top picks with structured + narrative fields |

## Success Criteria (Implicit)

- Recommendations reflect stated preferences (location, budget, cuisine, rating)
- Explanations are readable and tied to user input
- Output is structured enough to compare options (name, cuisine, rating, cost) plus narrative rationale
- End-to-end flow: ingest data → collect preferences → filter → LLM rank/explain → display

## Out of Scope (Not Specified in Problem Statement)

The problem statement does not mandate: specific tech stack, deployment target, authentication, caching, or evaluation metrics. Those choices are left to implementation unless added later.

## Reference

- Original problem statement: `docs/ProblemStatement`
