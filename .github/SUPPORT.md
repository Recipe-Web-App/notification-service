# Support

Thank you for using the Notification Service! This document provides information on how to get help and support.

## Documentation

Start with our documentation:

- **[README](../README.md)** - Overview, installation, and basic usage
- **[Contributing Guide](CONTRIBUTING.md)** - How to contribute to the project
- **[Security Policy](SECURITY.md)** - Security reporting and best practices
- **[API Documentation](../docs/api.md)** - API endpoint documentation (if available)

## Getting Help

### Before Asking for Help

Please check if your question has already been answered:

1. Search [existing GitHub Discussions](https://github.com/Recipe-Web-App/notification-service/discussions)
2. Search [closed GitHub Issues](https://github.com/Recipe-Web-App/notification-service/issues?q=is%3Aissue+is%3Aclosed)
3. Review the [README](../README.md) and documentation
4. Check the [Django documentation](https://docs.djangoproject.com/)
5. Check the [Django REST Framework docs](https://www.django-rest-framework.org/)

### Where to Get Help

Choose the right channel for your question:

#### GitHub Discussions (Recommended for Questions)

Use [GitHub Discussions](https://github.com/Recipe-Web-App/notification-service/discussions) for:

- General questions about using the service
- Installation and setup help
- Configuration questions
- API usage questions
- Feature discussions
- Sharing your implementations

**Create a Discussion**: [Start a new discussion](https://github.com/Recipe-Web-App/notification-service/discussions/new)

#### GitHub Issues (For Bugs and Features)

Use [GitHub Issues](https://github.com/Recipe-Web-App/notification-service/issues) for:

- Bug reports
- Feature requests
- Performance issues
- Documentation errors

**Create an Issue**: Choose the appropriate template when creating an issue.

#### Security Vulnerabilities

**Never create public issues for security vulnerabilities.**

Report security issues via:
- [GitHub Security Advisories](https://github.com/Recipe-Web-App/notification-service/security/advisories/new)
- Email: jsamuelsen11@gmail.com

## Common Questions

### Installation and Setup

**Q: How do I install the notification service?**

A: See the [Installation section](../README.md#setup) in the README. You'll need Python 3.14+ and Poetry.

**Q: How do I run the service locally?**

A: After installation, run:
```bash
poetry run local
# or
poetry run python manage.py runserver
```

**Q: Can I use Docker?**

A: Yes! See the [Docker section](../README.md#docker) in the README or run:
```bash
docker-compose up
```

### Configuration

**Q: Where do I configure environment variables?**

A: Create a `.env` file in the project root based on `.env.example` (when available), or set environment variables directly.

**Q: How do I change the database?**

A: Update the `DATABASES` setting in `notification_service/settings.py`. For production, use PostgreSQL or MySQL instead of SQLite.

**Q: How do I enable debug mode?**

A: Set `DEBUG=True` in your environment or settings. **Never use DEBUG=True in production.**

### API Usage

**Q: How do I authenticate with the API?**

A: See the API documentation for authentication methods. Typically, you'll use token-based authentication with Django REST Framework.

**Q: What's the base URL for API endpoints?**

A: By default, API endpoints are available at `http://localhost:8000/api/v1/`

**Q: How do I handle rate limiting?**

A: The API implements rate limiting to prevent abuse. Respect the rate limits and implement exponential backoff in your client.

### Development

**Q: How do I contribute?**

A: See the [Contributing Guide](CONTRIBUTING.md) for detailed instructions on setting up your development environment and submitting pull requests.

**Q: How do I run tests?**

A:
```bash
poetry run python manage.py test
```

**Q: How do I check code style?**

A:
```bash
poetry run black .
poetry run flake8 notification_service/ core/
poetry run mypy notification_service/ core/
```

### Troubleshooting

**Q: I'm getting "Module not found" errors**

A: Make sure you've installed all dependencies:
```bash
poetry install
```

**Q: Migrations aren't working**

A: Try:
```bash
poetry run python manage.py makemigrations
poetry run python manage.py migrate
```

**Q: I'm getting CORS errors**

A: Configure CORS settings in `notification_service/settings.py`. For development, you may need to add your frontend URL to `CORS_ALLOWED_ORIGINS`.

**Q: The service won't start**

A: Check:
- All dependencies are installed
- Database is accessible
- No other service is using port 8000
- Environment variables are set correctly

## Response Times

We're a small team, so please be patient:

- **GitHub Discussions**: Usually within 1-3 days
- **Bug Reports**: Acknowledged within 1 week
- **Feature Requests**: Reviewed within 2 weeks
- **Security Reports**: Acknowledged within 48 hours
- **Pull Requests**: Reviewed within 1-2 weeks

## Community Guidelines

When asking for help:

1. **Be respectful** and follow our [Code of Conduct](CODE_OF_CONDUCT.md)
2. **Provide context** - version, environment, what you've tried
3. **Be specific** - include error messages, logs, steps to reproduce
4. **Be patient** - maintainers are volunteers
5. **Give back** - help others when you can

## How to Ask Good Questions

Help us help you by providing:

1. **What you're trying to do**
2. **What you expected to happen**
3. **What actually happened**
4. **Steps to reproduce**
5. **Your environment**:
   - Python version
   - Django version
   - Operating system
   - Deployment method (local, Docker, cloud)
6. **Error messages** (complete stack traces)
7. **What you've tried** (so we don't suggest things you've already attempted)

### Example Good Question

> **Title**: "API returns 500 error when creating notification with email type"
>
> **Description**:
> I'm trying to create a notification via the API but getting a 500 error.
>
> **Environment**:
> - Python 3.14
> - Django 5.2.7
> - Ubuntu 22.04
> - Running locally with `poetry run local`
>
> **Steps to reproduce**:
> ```bash
> curl -X POST http://localhost:8000/api/v1/notifications/ \
>   -H "Content-Type: application/json" \
>   -d '{"type": "email", "recipient": "test@example.com"}'
> ```
>
> **Expected**: 201 Created with notification object
>
> **Actual**: 500 Internal Server Error
>
> **Error log**:
> ```
> [error log here]
> ```
>
> **What I've tried**:
> - Checked database connection
> - Verified migrations are up to date
> - Tested with different payload

## Bug Report Best Practices

When reporting bugs:

1. **Use the bug report template**
2. **One bug per issue** - don't combine multiple bugs
3. **Search first** - check if it's already reported
4. **Provide minimal reproduction** - simplest case that shows the bug
5. **Include logs** - but redact sensitive information
6. **Test on latest version** - make sure it's not already fixed

## Feature Request Best Practices

When requesting features:

1. **Use the feature request template**
2. **Explain the problem** - not just the solution
3. **Describe use cases** - help us understand the need
4. **Consider alternatives** - show you've thought about it
5. **Be open to discussion** - we may suggest different approaches

## Additional Resources

### Django Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [Django Tutorial](https://docs.djangoproject.com/en/stable/intro/tutorial01/)
- [Django Best Practices](https://django-best-practices.readthedocs.io/)

### Django REST Framework Resources

- [DRF Documentation](https://www.django-rest-framework.org/)
- [DRF Tutorial](https://www.django-rest-framework.org/tutorial/quickstart/)

### Poetry Resources

- [Poetry Documentation](https://python-poetry.org/docs/)
- [Poetry Commands](https://python-poetry.org/docs/cli/)

### Python Resources

- [Python Documentation](https://docs.python.org/3/)
- [PEP 8 Style Guide](https://pep8.org/)

## Commercial Support

Commercial support is not currently available for this project.

## Sponsorship

If you'd like to support the development of this project, please reach out to the maintainers.

---

Thank you for being part of the Notification Service community! 🙏
