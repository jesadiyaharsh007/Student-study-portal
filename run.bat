@echo off
echo Starting Django Development Server...
if exist "Harsh\Scripts\python.exe" (
    echo Using 'Harsh' virtual environment...
    "Harsh\Scripts\python.exe" manage.py runserver
) else (
    echo Using global Python environment...
    python manage.py runserver
)
pause
