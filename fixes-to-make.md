# Fixes Yet To Make

This file documents all outstanding improvements, fixes, and enhancements for the AI-102 repo. It includes both incoming suggestions and action items discussed in this project.

---

## 🛠️ Governance & Documentation

- [ ] Add `CODE_OF_CONDUCT.md` at the repo root (README links expect it)
- [ ] Add `CONTRIBUTING.md` at the repo root (README links expect it)
- [ ] Ensure all referenced files in README.md exist and are up to date
- [ ] Fix broken or outdated documentation links (e.g., image paths in `model_README.md`)
- [ ] Ensure all README files end with a trailing newline and are cleanly formatted

## 🔑 Environment & Configuration

- [x] Add a global `.env.sample` at the repo root (done)
- [ ] Add `.env.sample` files to lesson folders that require them
- [ ] Ensure all setup instructions referencing `.env.sample` are accurate

## 🧩 Demo Apps & Lesson Coverage

- [ ] Create or port demo apps for lessons currently missing them:
  - [ ] Lesson 1: Plan Azure AI Solutions
  - [ ] Lesson 2: Design AI Architectures
  - [ ] Lesson 7: Create Custom Computer Vision Models
  - [ ] Lesson 10: Build Conversational AI with Bots
  - [ ] Lesson 13: Translate and Localize Content
  - [ ] Lesson 17: Optimize Generative AI Models
- [ ] Expand lesson subfolder READMEs with detailed instructions and sample code
- [ ] Map each imported resource/demo to its corresponding lesson in the scaffold

## 🔄 Code Quality & Security

- [x] Remove embedded `.git` directories from imported resources (done)
- [x] Add `.gitattributes` for cross-platform line ending consistency (done)
- [ ] Parameterize all hard-coded service endpoints (e.g., in `analyze_text.py`) to use environment variables
- [ ] Normalize line endings across the repo (optional, after .gitattributes)

## 🚦 CI/CD & Best Practices

- [ ] Add GitHub Actions workflows for:
  - [ ] Linting (e.g., ESLint, flake8)
  - [ ] Testing (unit/integration)
  - [ ] Security scanning (e.g., CodeQL, secret scanning)
- [ ] Document how to run and interpret CI results in the repo

## 🗂️ Resource Centralization & Hygiene

- [ ] Document how each imported resource/demo ties into the lessons
- [ ] Trim or archive unused files/scripts in `imported-resources/`
- [ ] Ensure all images and assets are referenced with correct paths

## 🧠 Learner Experience

- [ ] Ensure all lesson folders have clear, actionable instructions
- [ ] Add teaching notes, tips, and troubleshooting sections where helpful
- [ ] Maintain a neurodivergent-friendly, accessible, and delightful repo structure

---

> This checklist is a living document. Update as you go to keep the repo polished, professional, and learner-friendly!