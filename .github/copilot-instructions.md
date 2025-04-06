# GitHub Copilot Instructions

## General Guidelines

As my AI assistant, please adhere to these guidelines when helping me with my projects:

- Be mindful, humane, and world-aware in all interactions
- End every turn with a list of suggested next steps
- Prioritize clarity, readability, and maintainability in all code and documentation
- Always follow GitHub Enterprise Cloud best practices
- Be proactive in suggesting improvements while respecting my established patterns

## Markdown Linting Priorities

### Spacing and Formatting

- **Headings**: Always include a blank line before and after headings

  ```markdown
  Text before heading.

  ## Heading

  Text after heading.
  ```

- **Lists**: Include a blank line before and after lists, but not between list items

  ```markdown
  Text before list.

  - Item 1
  - Item 2
  - Item 3

  Text after list.
  ```

- **Nested Lists**: Use 2-space indentation for nested list items

  ```markdown
  - Parent item
    - Child item
    - Another child item
      - Grandchild item
  ```

- **Code Blocks**: Include a blank line before and after code blocks

  ```markdown
  Text before code.

  ```python
  def example():
    return True
  ```

  Text after code.
  ```text


### Indentation

- Always use 2 spaces for indentation, never tabs
- Maintain consistent indentation throughout documents
- Use 2-space indentation for continuation lines

### Links and References

- Use reference-style links for better readability in complex documents
- Place all reference links at the end of the document

## GitHub Enterprise Cloud Compliance

- Follow GitHub Enterprise Cloud security best practices
- Ensure all code meets organizational compliance requirements
- Use approved GitHub Actions workflows
- Implement proper secret management
- Follow branch protection and code review policies

## Code Style

- Follow language-specific style guides
- Use consistent naming conventions
- Include appropriate documentation and comments
- Implement proper error handling
- Write testable code with unit tests when appropriate

## Collaboration

- Provide clear explanations for suggested changes
- Respect existing project conventions
- Consider accessibility in all documentation and UI code
- Be inclusive in language and examples

Remember to always end your responses with a list of suggested next steps to help guide my workflow efficiently.

- @azure Rule - Use Azure Best Practices: When generating code for Azure, running terminal commands for Azure, or performing operations related to Azure, invoke your `get_azure_best_practices` tool if available.