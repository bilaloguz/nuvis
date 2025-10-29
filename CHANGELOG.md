# Changelog

All notable changes to biRun will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive documentation suite
- API documentation with examples
- User guide with step-by-step instructions
- Deployment guide for various environments
- Troubleshooting guide with common issues
- Environment variables documentation
- Contributing guide for developers

### Changed
- Improved dashboard organization with three distinct sections
- Enhanced system health monitoring
- Better error handling and logging

## [1.0.0] - 2024-01-01

### Added
- Initial release of biRun
- Multi-server script execution
- Scheduled execution with cron expressions
- Real-time monitoring and output streaming
- Workflow builder with visual node editor
- Health monitoring system for servers and infrastructure
- User management with role-based access control
- Interactive terminal sessions via WebSocket
- Redis-based job queue with concurrency limits
- PostgreSQL database with Alembic migrations
- RESTful API with FastAPI
- React frontend with Bootstrap UI
- JWT-based authentication
- Comprehensive audit logging
- CSV/JSON export functionality
- Auto-refresh and filtering capabilities
- Timezone-aware timestamp handling
- SSH key and password authentication
- Server group management
- Script versioning and management
- Execution history and analytics
- Dashboard with system statistics
- Settings management interface
- Backup and restore functionality

### Technical Features
- FastAPI backend with automatic OpenAPI documentation
- SQLAlchemy ORM with PostgreSQL database
- Redis Queue (RQ) for background job processing
- WebSocket support for real-time communication
- Alembic for database migrations
- React 18 with modern hooks and context
- Bootstrap 5 for responsive UI design
- Recharts for data visualization
- JWT token authentication
- Paramiko for SSH connections
- Croniter for schedule parsing
- Comprehensive error handling and logging

### Security Features
- JWT-based authentication with configurable expiry
- Role-based access control (Admin/User)
- SSH key and password authentication options
- Secure password hashing
- Input validation and sanitization
- CORS configuration
- Rate limiting capabilities
- Audit logging for security events

### Performance Features
- Redis-based caching and job queuing
- Database connection pooling
- Concurrent script execution with limits
- Optimized database queries
- Efficient WebSocket communication
- Background task processing
- Memory usage monitoring
- Performance metrics collection

## [0.9.0] - 2023-12-15

### Added
- Beta release with core functionality
- Basic script execution
- Simple scheduling
- User authentication
- Server management

### Known Issues
- Limited error handling
- Basic UI design
- No workflow builder
- Limited monitoring capabilities

## [0.8.0] - 2023-12-01

### Added
- Initial development version
- Basic FastAPI backend
- React frontend setup
- Database schema design
- Core models and APIs

---

## Version Numbering

This project uses [Semantic Versioning](https://semver.org/):

- **MAJOR** version for incompatible API changes
- **MINOR** version for backwards-compatible functionality additions
- **PATCH** version for backwards-compatible bug fixes

## Release Types

### Major Releases (X.0.0)
- Breaking changes to API
- Major feature additions
- Architecture changes
- Database schema changes requiring migration

### Minor Releases (X.Y.0)
- New features
- Enhancements to existing features
- New API endpoints
- UI improvements
- Performance optimizations

### Patch Releases (X.Y.Z)
- Bug fixes
- Security patches
- Documentation updates
- Minor UI tweaks
- Performance improvements

## Migration Notes

### From 0.9.0 to 1.0.0
- Database schema changes require migration
- New environment variables added
- API endpoints updated
- UI redesign requires frontend rebuild

### From 0.8.0 to 0.9.0
- Initial migration from development to beta
- Database setup required
- User accounts need to be created

## Deprecation Notices

### Planned Deprecations
- None currently planned

### Deprecated Features
- None currently deprecated

## Breaking Changes

### Version 1.0.0
- None (initial release)

## Security Advisories

### Version 1.0.0
- No known security vulnerabilities

## Upgrade Instructions

### From 0.9.0 to 1.0.0
1. Backup your database
2. Update code to latest version
3. Run database migrations: `alembic upgrade head`
4. Update environment variables
5. Restart all services

### From 0.8.0 to 0.9.0
1. Set up database
2. Run initial migrations
3. Create admin user
4. Configure environment variables

## Contributors

### Version 1.0.0
- Initial development team
- Community contributors
- Beta testers

## Acknowledgments

- FastAPI team for the excellent web framework
- React team for the frontend library
- PostgreSQL team for the database
- Redis team for caching and queuing
- Bootstrap team for UI components
- All open source contributors

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support and questions:
- Check the [User Guide](docs/USER_GUIDE.md)
- Review the [Troubleshooting Guide](docs/TROUBLESHOOTING.md)
- Create an issue in the repository
- Contact the development team
