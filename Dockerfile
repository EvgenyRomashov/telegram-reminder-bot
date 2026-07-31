# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# Set the working directory in the container
WORKDIR /app

# Install any needed packages specified in pyproject.toml
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy the rest of the application code
COPY . .

# Run main.py as a module when the container launches
CMD ["python", "-m", "reminder_bot.main"]
