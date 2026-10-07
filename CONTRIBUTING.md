# Contributing to HashBrownie

Thank you for your interest in contributing to HashBrownie! Here are some guidelines to help you get started.

## How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`just test`)
5. Run linting (`just lint`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## Code Style

- Follow PEP 8 guidelines
- Use type hints
- Keep functions simple and focused
- Add docstrings where appropriate
- Run `just format` before committing

## Adding New Hash Types

To add support for a new hash type:

1. Add prefix rules to `PREFIX_RULES` in `hashbrownie.py` if it has a prefix
2. Add length rules to `HEX_LENGTH_RULES` if it's a hex hash
3. Add appropriate detection logic if it has a special format
4. Add tests in `test_hashbrownie.py`
5. Update the README if needed

## Testing

All changes should include appropriate tests. Run the full test suite with:

```bash
just test
```

## Bug Reports

When reporting bugs, please include:
- The hash string you tried (if safe to share)
- The expected vs actual result
- Your Python version and OS
