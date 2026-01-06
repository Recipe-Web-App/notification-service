# Security Policy

## Supported Versions

We release patches for security vulnerabilities for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them using one of the following methods:

### GitHub Security Advisories (Preferred)

Report vulnerabilities through [GitHub Security Advisories](https://github.com/Recipe-Web-App/notification-service/security/advisories/new).

This allows us to:
- Discuss the vulnerability privately
- Work on a fix without public disclosure
- Coordinate disclosure timing
- Issue a CVE if necessary

### Email

Alternatively, email security reports to: **jsamuelsen11@gmail.com**

Include the following information:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)
- Your contact information

## What to Include in a Security Report

Please provide as much information as possible:

1. **Type of vulnerability** (e.g., SQL injection, XSS, authentication bypass)
2. **Location** (file path, endpoint, function name)
3. **Impact** (what an attacker could achieve)
4. **Steps to reproduce** (detailed reproduction steps)
5. **Proof of concept** (if available)
6. **Suggested mitigation** (if you have ideas)
7. **Affected versions**

## Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Fix Timeline**: Depends on severity
  - **Critical**: Within 7 days
  - **High**: Within 30 days
  - **Medium**: Within 90 days
  - **Low**: Best effort

## Severity Levels

### Critical

- Remote code execution
- SQL injection allowing data exfiltration
- Authentication bypass
- Privilege escalation to admin
- Exposure of sensitive data (passwords, API keys)

### High

- Cross-site scripting (XSS) allowing account takeover
- Server-side request forgery (SSRF)
- Information disclosure of sensitive data
- Denial of service affecting all users

### Medium

- Cross-site request forgery (CSRF)
- Path traversal
- Information disclosure of non-sensitive data
- Denial of service affecting single user

### Low

- Minor information disclosure
- Security misconfigurations with minimal impact
- Best practice violations

## Security Features

### Django Security Features

This service leverages Django's built-in security features:

- **CSRF Protection**: All POST requests require CSRF tokens
- **SQL Injection Protection**: Django ORM with parameterized queries
- **XSS Protection**: Template auto-escaping
- **Clickjacking Protection**: X-Frame-Options header
- **SSL/HTTPS**: Enforced in production
- **Session Security**: Secure session cookies

**Note**: This service is a read-only database consumer and does not manage user passwords.

### Django REST Framework Security

- **Authentication**: Token-based authentication
- **Permission Classes**: Granular access control
- **Throttling**: Rate limiting on API endpoints
- **Content Negotiation**: Strict content type handling

### Additional Security Measures

- **Dependency Scanning**: Automated with Dependabot and osv-scanner
- **Code Scanning**: CodeQL and Bandit security analysis
- **Container Scanning**: Trivy for Docker image vulnerabilities
- **Secret Detection**: No secrets in code or logs
- **Input Validation**: Serializer validation on all inputs

## Security Best Practices for Operators

### Environment Configuration

1. **Set `DEBUG = False` in production**
2. **Use strong `SECRET_KEY`** (minimum 50 characters, randomly generated)
3. **Set `ALLOWED_HOSTS`** to specific domains
4. **Use HTTPS only** with `SECURE_SSL_REDIRECT = True`
5. **Enable secure cookies**:
   - `SESSION_COOKIE_SECURE = True`
   - `CSRF_COOKIE_SECURE = True`

### Database Security

1. **Use strong database passwords**
2. **Restrict database access** to application only
3. **Enable SSL/TLS** for database connections
4. **Regular backups** with encryption
5. **Principle of least privilege** for database user

### API Security

1. **Use authentication** on all endpoints
2. **Implement rate limiting** to prevent abuse
3. **Validate all input** using serializers
4. **Use HTTPS** for all API communication
5. **Log API access** for auditing

### Dependency Management

1. **Keep dependencies updated**
2. **Review Dependabot PRs** promptly
3. **Run security scans** regularly
4. **Audit new dependencies** before adding

### Secret Management

1. **Never commit secrets** to version control
2. **Use environment variables** for configuration
3. **Rotate secrets** periodically
4. **Use secret management tools** (AWS Secrets Manager, Vault)
5. **Restrict access** to production secrets

## Security Checklist for Deployment

Before deploying to production:

- [ ] `DEBUG = False`
- [ ] Strong `SECRET_KEY` set
- [ ] `ALLOWED_HOSTS` configured
- [ ] HTTPS enforced
- [ ] Secure cookies enabled
- [ ] Database password is strong and secure
- [ ] Database access restricted
- [ ] All dependencies updated
- [ ] Security scanning completed
- [ ] Environment variables secured
- [ ] Logging configured
- [ ] Backups enabled
- [ ] Monitoring enabled
- [ ] Rate limiting configured
- [ ] CORS properly configured
- [ ] No secrets in code or logs

## Known Security Considerations

### Django Specifics

- **Database**: This service requires PostgreSQL (uses a shared database with schema isolation).
- **Static File Serving**: Use a CDN or reverse proxy (nginx) in production, not Django.
- **Admin Interface**: Restrict access, use strong passwords, consider hiding at custom URL.

### API Considerations

- **Rate Limiting**: Implement throttling to prevent abuse
- **Input Validation**: All user input is validated through DRF serializers
- **Output Encoding**: Responses are properly encoded to prevent XSS

## Disclosure Policy

We follow a coordinated disclosure policy:

1. **Private Disclosure**: Security researcher reports vulnerability privately
2. **Acknowledgment**: We acknowledge receipt within 48 hours
3. **Investigation**: We investigate and develop a fix
4. **Fix Release**: We release a patched version
5. **Public Disclosure**: We publish a security advisory 7 days after fix release
6. **Credit**: We credit the researcher (if desired)

## Security Updates

Stay informed about security updates:

- Watch this repository for security advisories
- Subscribe to [GitHub Security Advisories](https://github.com/Recipe-Web-App/notification-service/security/advisories)
- Check the [Releases](https://github.com/Recipe-Web-App/notification-service/releases) page

## Contact

Security Team: jsamuelsen11@gmail.com

## Acknowledgments

We appreciate the security research community and will acknowledge researchers who report vulnerabilities responsibly.

### Hall of Fame

<!-- Security researchers who have helped improve our security will be listed here -->

*No security reports yet.*

---

Thank you for helping keep the Notification Service secure! 🔒
