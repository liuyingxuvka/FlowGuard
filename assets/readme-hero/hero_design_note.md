# README Hero Design Note

## Project summary

FlowGuard maintains a versioned, executable semantic model of what current
evidence supports inside a declared software boundary. It lets an AI agent
search the declared finite behavior space, navigate explicit
model-to-code/UI/test relationships, test candidate changes, and accept a new
Current only after the affected model, implementation, and evidence align
again.

## Target users

AI coding agents, engineers, and maintainers working on stateful behavior,
shared software structure, retries, side effects, UI/API paths, and changes
that need current evidence.

## Core problem

Code, specifications, commits, and historical test results do not automatically
form one current answer about a software system. Agents can repeatedly rebuild
that answer, miss undeclared behavior paths, or add a parallel structure instead
of reusing the current owner.

## Core workflow

Start from the accepted Current, create a separate Candidate, search the
declared finite paths and explicit affected relationships, align the change
with real code/UI/test observations, and accept a new Current only after the
declared gates hold.

## Hero tagline

Executable software DNA for finite-path search, affected-change navigation,
candidate simulation, and evidence-gated evolution.

## Visual concept

A wide, bright product-object sculpture. The left-hand teal core represents
the accepted Current. A blue Current route and an amber Candidate route pass
through connected model and evidence modules. Red fragments are stopped as
counterexamples or unresolved gaps. A green core on the right represents the
next accepted Current after alignment.

## Material language

Matte ceramic, brushed aluminum, enamel modules, soft translucent light paths,
and small crystalline counterexample fragments on a clean off-white studio
background.

## Generation method

Direct project-specific text-to-image generation followed by an image-to-image
composition refinement. The asset contains no text, logos, people, credentials,
user data, repository paths, or screenshots.

## File paths

- `assets/readme-hero/hero.jpg`
- `assets/readme-hero/hero_prompt.md`
- `assets/readme-hero/hero_design_note.md`

## README insertion position

Immediately below the title, language switch, and FlowGuard icon.
