$folders = @(
    "frontend/public",
    "frontend/src/assets",
    "frontend/src/components/common",
    "frontend/src/components/charts",
    "frontend/src/components/forms",
    "frontend/src/pages/auth",
    "frontend/src/pages/applicant",
    "frontend/src/pages/officer",
    "frontend/src/pages/admin",
    "frontend/src/layouts",
    "frontend/src/routes",
    "frontend/src/services",
    "frontend/src/hooks",
    "frontend/src/context",
    "frontend/src/store",
    "frontend/src/utils",
    "frontend/src/styles",
    "backend/src/config",
    "backend/src/routes",
    "backend/src/controllers",
    "backend/src/services",
    "backend/src/models",
    "backend/src/middlewares",
    "backend/src/validators",
    "backend/src/utils",
    "backend/src/jobs",
    "backend/tests/unit",
    "backend/tests/integration",
    "ml-service/data/raw",
    "ml-service/data/processed",
    "ml-service/data/external",
    "ml-service/notebooks",
    "ml-service/src/preprocessing",
    "ml-service/src/training",
    "ml-service/src/evaluation",
    "ml-service/src/explainability",
    "ml-service/src/fairness",
    "ml-service/src/fraud",
    "ml-service/src/inference",
    "ml-service/src/monitoring",
    "ml-service/models",
    "ml-service/api",
    "ml-service/tests",
    "docs",
    ".github/workflows"
)

foreach ($folder in $folders) {
    New-Item -ItemType Directory -Force -Path $folder | Out-Null
}

$files = @(
    "docker-compose.yml",
    ".gitignore",
    "README.md",
    ".env.example",
    "frontend/package.json",
    "frontend/vite.config.js",
    "frontend/.env.example",
    "frontend/src/App.jsx",
    "frontend/src/main.jsx",
    "backend/package.json",
    "backend/server.js",
    "backend/src/app.js",
    "backend/.env.example",
    "ml-service/requirements.txt",
    "ml-service/Dockerfile",
    "ml-service/.env.example",
    "ml-service/api/main.py",
    "ml-service/api/schemas.py",
    "ml-service/api/routes.py",
    "docs/api-documentation.md",
    "docs/setup-guide.md"
)

foreach ($file in $files) {
    New-Item -ItemType File -Force -Path $file | Out-Null
}
