# Contributing Guide

## Welcome!

Thank you for your interest in contributing to biRun! This guide will help you get started with contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Contributing Process](#contributing-process)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)
- [Issue Reporting](#issue-reporting)
- [Pull Request Process](#pull-request-process)

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for all contributors. By participating in this project, you agree to:

- Be respectful and inclusive
- Welcome newcomers and help them learn
- Focus on what's best for the community
- Show empathy towards other community members
- Accept constructive criticism gracefully
- Respect different viewpoints and experiences

### Unacceptable Behavior

The following behaviors are considered unacceptable:

- Harassment, discrimination, or offensive comments
- Personal attacks or trolling
- Public or private harassment
- Publishing others' private information without permission
- Other unprofessional conduct

## Getting Started

### Prerequisites

Before contributing, ensure you have:

- Python 3.8+ installed
- Node.js 16+ installed
- Git installed
- PostgreSQL 12+ installed
- Redis 6+ installed
- A GitHub account

### Fork and Clone

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/your-username/script-manager.git
   cd script-manager
   ```
3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/original-owner/script-manager.git
   ```

## Development Setup

### Backend Setup

1. **Navigate to backend directory**:
   ```bash
   cd backend
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # Development dependencies
   ```

4. **Set up environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your local configuration
   ```

5. **Set up database**:
   ```bash
   # Start PostgreSQL and Redis
   sudo systemctl start postgresql redis
   
   # Create database
   createdb script_manager
   
   # Run migrations
   alembic upgrade head
   ```

6. **Create admin user**:
   ```bash
   python create_admin.py
   ```

7. **Start backend**:
   ```bash
   python main.py
   ```

### Frontend Setup

1. **Navigate to frontend directory**:
   ```bash
   cd frontend
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Start development server**:
   ```bash
   npm start
   ```

### Development Tools

#### Pre-commit Hooks

Install pre-commit hooks for code quality:

```bash
pip install pre-commit
pre-commit install
```

#### Code Formatting

The project uses Black for Python formatting and Prettier for JavaScript:

```bash
# Format Python code
black backend/

# Format JavaScript code
cd frontend
npm run format
```

#### Linting

```bash
# Lint Python code
flake8 backend/
pylint backend/

# Lint JavaScript code
cd frontend
npm run lint
```

## Contributing Process

### 1. Choose an Issue

- Look for issues labeled `good first issue` or `help wanted`
- Comment on the issue to indicate you're working on it
- Ask questions if anything is unclear

### 2. Create a Branch

```bash
# Update your fork
git fetch upstream
git checkout main
git merge upstream/main

# Create feature branch
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-number-description
```

### 3. Make Changes

- Write clean, readable code
- Follow the coding standards
- Add tests for new functionality
- Update documentation as needed

### 4. Test Your Changes

```bash
# Backend tests
cd backend
python -m pytest tests/ -v

# Frontend tests
cd frontend
npm test

# Integration tests
python -m pytest tests/integration/ -v
```

### 5. Commit Changes

```bash
# Stage changes
git add .

# Commit with descriptive message
git commit -m "Add feature: brief description

- Detailed description of changes
- Reference issue number if applicable
- Breaking changes if any"
```

### 6. Push and Create Pull Request

```bash
# Push to your fork
git push origin feature/your-feature-name

# Create pull request on GitHub
```

## Coding Standards

### Python (Backend)

#### Style Guide
- Follow PEP 8
- Use Black for formatting
- Maximum line length: 88 characters
- Use type hints where appropriate

#### Code Structure
```python
# Imports (standard library, third-party, local)
import os
from typing import List, Optional

import fastapi
from sqlalchemy import Column, Integer, String

from .models import User
from .schemas import UserCreate

# Constants
MAX_RETRIES = 3

# Classes and functions
class UserService:
    def __init__(self, db_session):
        self.db = db_session
    
    def create_user(self, user_data: UserCreate) -> User:
        """Create a new user.
        
        Args:
            user_data: User creation data
            
        Returns:
            Created user object
            
        Raises:
            ValueError: If user already exists
        """
        # Implementation
        pass
```

#### Naming Conventions
- **Variables and functions**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private methods**: `_leading_underscore`

#### Documentation
- Use docstrings for all public functions and classes
- Follow Google docstring format
- Include type hints
- Document complex logic

### JavaScript/React (Frontend)

#### Style Guide
- Follow Airbnb JavaScript Style Guide
- Use Prettier for formatting
- Use ESLint for linting

#### Component Structure
```javascript
import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';

const MyComponent = ({ title, onAction }) => {
  const [state, setState] = useState(null);

  useEffect(() => {
    // Effect logic
  }, []);

  const handleClick = () => {
    onAction(state);
  };

  return (
    <div className="my-component">
      <h2>{title}</h2>
      <button onClick={handleClick}>Action</button>
    </div>
  );
};

MyComponent.propTypes = {
  title: PropTypes.string.isRequired,
  onAction: PropTypes.func.isRequired,
};

export default MyComponent;
```

#### Naming Conventions
- **Variables and functions**: `camelCase`
- **Components**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Files**: `kebab-case` for components, `camelCase` for utilities

### Database

#### Migration Guidelines
- Always create migrations for schema changes
- Use descriptive migration names
- Test migrations on sample data
- Include rollback instructions

```python
# Example migration
"""Add user preferences table

Revision ID: 001_add_user_preferences
Revises: 000_initial_schema
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'user_preferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('theme', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'])
    )

def downgrade():
    op.drop_table('user_preferences')
```

## Testing

### Backend Testing

#### Unit Tests
```python
# tests/unit/test_user_service.py
import pytest
from unittest.mock import Mock

from app.services.user_service import UserService
from app.schemas import UserCreate

class TestUserService:
    def test_create_user_success(self):
        # Arrange
        mock_db = Mock()
        service = UserService(mock_db)
        user_data = UserCreate(username="test", email="test@example.com")
        
        # Act
        result = service.create_user(user_data)
        
        # Assert
        assert result.username == "test"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
```

#### Integration Tests
```python
# tests/integration/test_user_api.py
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_create_user():
    response = client.post(
        "/api/users/",
        json={"username": "test", "email": "test@example.com"}
    )
    assert response.status_code == 201
    assert response.json()["username"] == "test"
```

#### Running Tests
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_user_service.py

# Run with coverage
pytest --cov=app tests/

# Run with verbose output
pytest -v
```

### Frontend Testing

#### Component Tests
```javascript
// tests/components/MyComponent.test.js
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import MyComponent from '../MyComponent';

describe('MyComponent', () => {
  it('renders title correctly', () => {
    render(<MyComponent title="Test Title" onAction={jest.fn()} />);
    expect(screen.getByText('Test Title')).toBeInTheDocument();
  });

  it('calls onAction when button is clicked', () => {
    const mockAction = jest.fn();
    render(<MyComponent title="Test" onAction={mockAction} />);
    
    fireEvent.click(screen.getByText('Action'));
    expect(mockAction).toHaveBeenCalled();
  });
});
```

#### API Tests
```javascript
// tests/api/userApi.test.js
import { userApi } from '../userApi';

describe('userApi', () => {
  it('fetches users successfully', async () => {
    const mockResponse = { users: [{ id: 1, username: 'test' }] };
    global.fetch = jest.fn().mockResolvedValue({
      json: () => Promise.resolve(mockResponse)
    });

    const result = await userApi.getUsers();
    expect(result).toEqual(mockResponse);
  });
});
```

#### Running Tests
```bash
# Run all tests
npm test

# Run tests in watch mode
npm test -- --watch

# Run tests with coverage
npm test -- --coverage
```

## Documentation

### Code Documentation

#### Python Docstrings
```python
def create_user(user_data: UserCreate, db: Session) -> User:
    """Create a new user in the database.
    
    Args:
        user_data: User creation data from request
        db: Database session
        
    Returns:
        Created user object with generated ID
        
    Raises:
        ValueError: If username already exists
        IntegrityError: If database constraint is violated
        
    Example:
        >>> user_data = UserCreate(username="john", email="john@example.com")
        >>> user = create_user(user_data, db)
        >>> print(user.username)
        john
    """
    pass
```

#### JavaScript JSDoc
```javascript
/**
 * Creates a new user via API
 * @param {Object} userData - User creation data
 * @param {string} userData.username - Username
 * @param {string} userData.email - Email address
 * @returns {Promise<Object>} Created user object
 * @throws {Error} If API request fails
 * 
 * @example
 * const user = await createUser({ username: 'john', email: 'john@example.com' });
 * console.log(user.id);
 */
async function createUser(userData) {
  // Implementation
}
```

### README Updates

When adding new features:
1. Update the main README.md
2. Add feature description to the features list
3. Update installation instructions if needed
4. Add new environment variables to documentation

### API Documentation

Update API documentation when:
1. Adding new endpoints
2. Modifying existing endpoints
3. Changing request/response formats
4. Adding new authentication methods

## Issue Reporting

### Before Creating an Issue

1. **Search existing issues** to avoid duplicates
2. **Check if it's already fixed** in the latest version
3. **Gather information** about your environment

### Issue Template

When creating an issue, include:

```markdown
## Bug Report / Feature Request

### Description
Brief description of the issue or feature request.

### Environment
- OS: [e.g., Ubuntu 20.04]
- Python Version: [e.g., 3.9.7]
- Node.js Version: [e.g., 16.14.0]
- Database: [e.g., PostgreSQL 13]
- Redis: [e.g., 6.2.7]

### Steps to Reproduce (for bugs)
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

### Expected Behavior
What you expected to happen.

### Actual Behavior
What actually happened.

### Screenshots
If applicable, add screenshots.

### Additional Context
Any other context about the problem.
```

### Bug Reports

For bug reports, include:
- Clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Environment details
- Error messages and logs
- Screenshots if applicable

### Feature Requests

For feature requests, include:
- Clear description of the feature
- Use case and motivation
- Proposed implementation (if you have ideas)
- Alternative solutions considered
- Additional context

## Pull Request Process

### Before Submitting

1. **Ensure tests pass**:
   ```bash
   # Backend
   cd backend && python -m pytest
   
   # Frontend
   cd frontend && npm test
   ```

2. **Check code style**:
   ```bash
   # Python
   black backend/ && flake8 backend/
   
   # JavaScript
   cd frontend && npm run lint && npm run format
   ```

3. **Update documentation** if needed
4. **Add tests** for new functionality
5. **Update CHANGELOG.md** if applicable

### Pull Request Template

```markdown
## Description
Brief description of changes.

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Code refactoring

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed
- [ ] New tests added for new functionality

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes (or breaking changes documented)
- [ ] Tests added/updated
- [ ] All CI checks pass

## Related Issues
Fixes #(issue number)

## Additional Notes
Any additional information about the changes.
```

### Review Process

1. **Automated checks** must pass
2. **Code review** by maintainers
3. **Testing** on different environments
4. **Documentation** review
5. **Approval** from at least one maintainer

### After Approval

1. **Squash commits** if requested
2. **Update branch** with latest main
3. **Merge** by maintainers
4. **Delete feature branch** after merge

## Development Workflow

### Daily Workflow

1. **Start your day**:
   ```bash
   git fetch upstream
   git checkout main
   git merge upstream/main
   ```

2. **Create feature branch**:
   ```bash
   git checkout -b feature/your-feature
   ```

3. **Make changes and commit**:
   ```bash
   git add .
   git commit -m "Add feature: description"
   ```

4. **Push and create PR**:
   ```bash
   git push origin feature/your-feature
   ```

### Release Process

1. **Update version** in `__init__.py` and `package.json`
2. **Update CHANGELOG.md**
3. **Create release branch** from main
4. **Run full test suite**
5. **Create release** on GitHub
6. **Deploy** to production

## Getting Help

### Community Support

- **GitHub Discussions**: For questions and general discussion
- **GitHub Issues**: For bug reports and feature requests
- **Discord/Slack**: For real-time chat (if available)

### Code Review

- **Be constructive** in feedback
- **Explain the why** behind suggestions
- **Be respectful** of different approaches
- **Ask questions** if something is unclear

### Mentorship

- **New contributors**: Look for issues labeled `good first issue`
- **Experienced contributors**: Help mentor newcomers
- **Maintainers**: Available for guidance and questions

## Recognition

Contributors are recognized in:
- **CONTRIBUTORS.md** file
- **Release notes** for significant contributions
- **GitHub contributor graph**
- **Project documentation**

Thank you for contributing to biRun! 🚀
