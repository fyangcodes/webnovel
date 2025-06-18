# Web Novel Platform

A Django-based web platform for managing and translating web novels.

## Features

- Web novel management system
- Translation management
- LLM integration for assistance
- Book organization and tracking

## Prerequisites

- Python 3.8+
- Django
- Virtual Environment

## Installation

1. Clone the repository:
```bash
git clone <your-repository-url>
cd 00_novel
```

2. Create and activate virtual environment:
```bash
python -m venv .venv
# On Windows
.venv\Scripts\activate
# On Unix or MacOS
source .venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Apply database migrations:
```bash
python manage.py migrate
```

5. Create a superuser (optional):
```bash
python manage.py createsuperuser
```

6. Run the development server:
```bash
python manage.py runserver
```

## Project Structure

- `webnovel/` - Main Django project directory
  - `llm_integration/` - LLM integration components
  - `books/` - Book management application
  - `translations/` - Translation management system
  - `webnovel/` - Project settings and configuration

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 