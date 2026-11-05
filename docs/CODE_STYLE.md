# Code style

## Code and comments

- Prefer clear names, short functions, early returns, and `const`. Extract for reuse or clearer responsibility.
- Keep Python typed and follow Ruff/MyPy; use functional React components and the existing import aliases.
- Add a brief one-line Python docstring or `/** ... */` intent comment to named functions, hooks, and components.
- Add one-line comments above non-obvious decisions; explain why. Link unusual external constraints.
- Add guards, retries, or state only for concrete failure risks. Avoid speculative abstractions and unnecessary memoization.
- Handle rejected promises. `void` does not catch a rejection; UI commands use the hook's error boundary.

## UI

- Use Tailwind for components; CSS for setup, five palette roles, native control defaults, and shared animation.
- Keep short classes inline. Split long lists into a few `cn` strings, grouped roughly as layout → surfaces/spacing → typography → interaction.
- `cn` uses `clsx` and `tailwind-merge`; Prettier sorts its strings. Use opacity variants rather than adding muted, border, or hover color tokens.
- Use shared `Typography`, `Button`, `Select`, `Icon`, and feedback components. Keep primitives independent of backend commands.
- Prefer direct, professional copy. Avoid slogans and decorative success indicators; keep the document and its actions prominent.
- Use floating toasts for action feedback; errors stay dismissible until resolved. Keep ongoing task progress in the workspace.
- Register only MDI icons in `Icon`, using source slugs and a typed name union. ESLint blocks direct MDI imports and inline interface SVGs elsewhere.
- Prefer native buttons, selects, labels, and headings. Give icon buttons accessible names; preserve keyboard focus, contrast, and reduced motion.
- Support English and Spanish from Spain. Translate UI copy in both locale files; code and comments stay English. UI language is independent of spoken language.

## Dependencies

- Frontend imports used at runtime belong in `dependencies`; build, lint, type and test tools belong in `devDependencies`.
- Python runtime packages go in `requirements.txt`; developer/packaging tools go in `requirements-dev.txt`, which includes runtime requirements.

## Contracts

- Keep transport DTOs as JSON-only `TypedDict` types in `backend/schemas/`.
- Preserve API names and DTO fields unless a contract change is intentional and both sides are updated.
- Never hand-edit `pywebview-api.d.ts`. Run `pnpm gen-api`, review the diff, and check it with `pnpm check-api`.
- Keep vendor types inside engine adapters. React reads backend state and owns only presentation state.
- ESLint checks promises, type-only imports, layer boundaries, and icon usage.
